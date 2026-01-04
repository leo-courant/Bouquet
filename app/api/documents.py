"""API endpoints for document management."""

from typing import Optional
from uuid import UUID
import io
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from loguru import logger

from app.core import (
    get_document_processor,
    get_enhanced_document_processor,
    get_neo4j_repository,
)
from app.domain import Document
from app.repositories import Neo4jRepository
from app.services import DocumentProcessor
from app.services.enhanced_document_processor import EnhancedDocumentProcessor

router = APIRouter(prefix="/documents", tags=["documents"])


# Memory safety constants
MAX_FILE_SIZE_MB = 50  # Reject files larger than 50MB
STREAM_CHUNK_SIZE = 256 * 1024  # 256KB chunks for streaming


async def extract_text_from_pdf_streaming(file: UploadFile) -> str:
    """Extract text from PDF file using streaming to avoid loading entire file into memory.
    
    Uses SpooledTemporaryFile to keep small files in memory but large ones on disk.
    """
    logger.debug(f"[DEBUG] extract_text_from_pdf_streaming called")
    try:
        from pypdf import PdfReader
        logger.debug(f"[DEBUG] pypdf imported successfully")
    except ImportError as import_e:
        logger.error(f"[ERROR] pypdf not installed: {str(import_e)}")
        raise HTTPException(
            status_code=500,
            detail="PDF support not installed. Install pypdf package.",
        )
    
    try:
        logger.debug(f"[DEBUG] Creating SpooledTemporaryFile for PDF processing")
        # Use SpooledTemporaryFile - keeps data in memory up to max_size, then spills to disk
        # This prevents loading huge PDFs entirely into RAM
        with tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024) as temp_file:  # 10MB threshold
            logger.debug(f"[DEBUG] Streaming PDF file content in chunks")
            chunk_count = 0
            # Stream file content in chunks instead of reading all at once
            while True:
                chunk = await file.read(STREAM_CHUNK_SIZE)  # 256KB chunks
                if not chunk:
                    logger.debug(f"[DEBUG] PDF streaming complete: {chunk_count} chunks read")
                    break
                temp_file.write(chunk)
                chunk_count += 1
                if chunk_count % 10 == 0:
                    logger.debug(f"[DEBUG] Streamed {chunk_count} chunks")
            
            # Reset file pointer for reading
            temp_file.seek(0)
            logger.debug(f"[DEBUG] Creating PdfReader")
            
            # Process PDF from temporary file
            try:
                reader = PdfReader(temp_file)
                page_count = len(reader.pages)
                logger.debug(f"[DEBUG] PDF has {page_count} pages")
            except Exception as pdf_read_e:
                logger.error(f"[ERROR] Failed to read PDF: {type(pdf_read_e).__name__}: {str(pdf_read_e)}")
                logger.exception(f"[EXCEPTION] PDF reading error:")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to read PDF file: {str(pdf_read_e)}",
                )
            
            # Extract text page by page (don't accumulate all pages)
            text_parts = []
            for page_num, page in enumerate(reader.pages):
                try:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                    
                    # Check memory every 10 pages for large PDFs
                    if page_num > 0 and page_num % 10 == 0:
                        logger.info(f"Processed {page_num + 1} pages from PDF")
                        logger.debug(f"[DEBUG] Processed {page_num + 1}/{page_count} pages")
                except Exception as page_e:
                    logger.error(f"[ERROR] Failed to extract text from page {page_num + 1}: {type(page_e).__name__}: {str(page_e)}")
                    logger.warning(f"[WARNING] Skipping page {page_num + 1}")
                    # Continue with other pages
            
            result_text = "\n\n".join(text_parts)
            logger.debug(f"[DEBUG] PDF extraction complete: {len(result_text)} characters from {len(text_parts)} pages")
            return result_text
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Unexpected error during PDF extraction: {type(e).__name__}: {str(e)}")
        logger.exception(f"[EXCEPTION] PDF extraction error:")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to extract text from PDF: {str(e)}",
        )


def extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF file.
    
    DEPRECATED: Use extract_text_from_pdf_streaming instead.
    This function loads entire PDF into memory.
    """
    try:
        from pypdf import PdfReader
        
        pdf_file = io.BytesIO(content)
        reader = PdfReader(pdf_file)
        
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        
        return "\n\n".join(text_parts)
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="PDF support not installed. Install pypdf package.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to extract text from PDF: {str(e)}",
        )


@router.post("/upload", response_model=None)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = None,
    extract_entities: bool = True,  # Default to True so documents appear in graph
    repository: Neo4jRepository = Depends(get_neo4j_repository),
    processor: DocumentProcessor = Depends(get_document_processor),
):
    """Upload and process a document with memory-safe streaming.
    
    Args:
        file: The file to upload
        title: Optional custom title (defaults to filename)
        extract_entities: If True, extracts entities (slow). If False, only creates chunks and embeddings (fast).
    """
    try:
        filename = file.filename or "untitled"
        logger.info(f"Receiving file upload: {filename}")
        logger.debug(f"[DEBUG] upload_document called: filename={filename}, title={title}, extract_entities={extract_entities}")
        logger.debug(f"[DEBUG] File details: content_type={file.content_type}, size={getattr(file, 'size', 'unknown')}")
        
        # Check file size if available (before reading)
        if hasattr(file, 'size') and file.size:
            file_size_mb = file.size / 1024 / 1024
            logger.debug(f"[DEBUG] File size: {file_size_mb:.2f}MB")
            if file_size_mb > MAX_FILE_SIZE_MB:
                logger.error(f"[ERROR] File too large: {file_size_mb:.1f}MB exceeds limit of {MAX_FILE_SIZE_MB}MB")
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large: {file_size_mb:.1f}MB (max {MAX_FILE_SIZE_MB}MB)",
                )
        
        # Extract text using streaming based on file type
        if filename.lower().endswith('.pdf'):
            logger.info(f"Processing PDF file with streaming: {filename}")
            logger.debug(f"[DEBUG] Calling extract_text_from_pdf_streaming")
            try:
                text = await extract_text_from_pdf_streaming(file)
                logger.debug(f"[DEBUG] PDF extraction successful: {len(text)} characters")
            except Exception as pdf_e:
                logger.error(f"[ERROR] PDF extraction failed: {type(pdf_e).__name__}: {str(pdf_e)}")
                logger.exception(f"[EXCEPTION] PDF extraction error:")
                raise
        else:
            # For text files, stream in chunks instead of using .read()
            logger.info(f"Processing text file with streaming: {filename}")
            logger.debug(f"[DEBUG] Starting text file streaming with chunk size {STREAM_CHUNK_SIZE}")
            text_chunks = []
            total_size = 0
            chunk_count = 0
            
            try:
                while True:
                    chunk = await file.read(STREAM_CHUNK_SIZE)  # 256KB at a time
                    if not chunk:
                        logger.debug(f"[DEBUG] End of file reached after {chunk_count} chunks")
                        break
                    
                    chunk_count += 1
                    # Check size limit as we stream
                    total_size += len(chunk)
                    if total_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                        logger.error(f"[ERROR] File size exceeded limit during streaming: {total_size} bytes > {MAX_FILE_SIZE_MB}MB")
                        raise HTTPException(
                            status_code=413,
                            detail=f"File exceeds {MAX_FILE_SIZE_MB}MB limit",
                        )
                    
                    text_chunks.append(chunk)
                    
                    if chunk_count % 10 == 0:
                        logger.debug(f"[DEBUG] Streamed {chunk_count} chunks, {total_size} bytes so far")
            except Exception as stream_e:
                logger.error(f"[ERROR] File streaming failed at chunk {chunk_count}: {type(stream_e).__name__}: {str(stream_e)}")
                logger.exception(f"[EXCEPTION] File streaming error:")
                raise
            
            # Decode all chunks at once (unavoidable for text files)
            try:
                logger.debug(f"[DEBUG] Decoding {len(text_chunks)} text chunks")
                text = b"".join(text_chunks).decode("utf-8")
                logger.debug(f"[DEBUG] Text decoded successfully: {len(text)} characters")
                # Clear chunks from memory immediately
                del text_chunks
            except UnicodeDecodeError as decode_e:
                logger.error(f"[ERROR] Unicode decode error: {str(decode_e)}")
                logger.error(f"[ERROR] File may not be valid UTF-8 text")
                raise HTTPException(
                    status_code=400,
                    detail="File must be a valid UTF-8 text file or PDF",
                )
        
        # Validate text is not empty
        if not text or not text.strip():
            logger.error(f"[ERROR] No text extracted from file: {filename}")
            raise HTTPException(
                status_code=400,
                detail="No text could be extracted from the file",
            )

        # Use filename as title if not provided
        doc_title = title or filename

        logger.info(f"Processing document: {doc_title} ({len(text)} characters)")
        logger.debug(f"[DEBUG] Calling processor.process_text with title={doc_title}, text_length={len(text)}")

        # Process document (now uses streaming internally)
        try:
            document, chunk_count = await processor.process_text(
                text=text,
                title=doc_title,
                repository=repository,
                source=filename,
                extract_entities=extract_entities,
            )
            logger.debug(f"[DEBUG] Document processed: document_id={document.id}, chunk_count={chunk_count}")
        except Exception as proc_e:
            logger.error(f"[ERROR] Document processing failed: {type(proc_e).__name__}: {str(proc_e)}")
            logger.error(f"[ERROR] Document details: title={doc_title}, text_length={len(text)}, extract_entities={extract_entities}")
            logger.exception(f"[EXCEPTION] Document processing error:")
            raise
        
        logger.info(f"Document processed successfully: {document.id} with {chunk_count} chunks")

        return {
            "document_id": str(document.id),
            "title": document.title,
            "status": "processed",
            "chunks": chunk_count,
            "message": "Document uploaded and processed successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Unexpected error uploading document: {type(e).__name__}: {str(e)}")
        logger.error(f"[ERROR] File details: filename={file.filename if hasattr(file, 'filename') else 'unknown'}")
        logger.exception(f"[EXCEPTION] Upload error traceback:")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing document: {str(e)}",
        )


@router.post("/upload/enhanced", response_model=None)
async def upload_document_enhanced(
    file: UploadFile = File(...),
    title: Optional[str] = None,
    extract_entities: bool = True,
    repository: Neo4jRepository = Depends(get_neo4j_repository),
    processor: EnhancedDocumentProcessor = Depends(get_enhanced_document_processor),
):
    """Upload and process a document with enhanced features (semantic chunking, entity disambiguation, etc.)."""
    try:
        filename = file.filename or "untitled"
        logger.info(f"Enhanced processing file upload: {filename}")
        
        # Check file size
        if hasattr(file, 'size') and file.size:
            file_size_mb = file.size / 1024 / 1024
            if file_size_mb > MAX_FILE_SIZE_MB:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large: {file_size_mb:.1f}MB (max {MAX_FILE_SIZE_MB}MB)",
                )
        
        # Extract text using streaming
        if filename.lower().endswith('.pdf'):
            text = await extract_text_from_pdf_streaming(file)
        else:
            text_chunks = []
            total_size = 0
            
            while True:
                chunk = await file.read(STREAM_CHUNK_SIZE)
                if not chunk:
                    break
                
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds {MAX_FILE_SIZE_MB}MB limit",
                    )
                
                text_chunks.append(chunk)
            
            try:
                text = b"".join(text_chunks).decode("utf-8")
                del text_chunks
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="File must be a valid UTF-8 text file or PDF",
                )
        
        if not text or not text.strip():
            raise HTTPException(
                status_code=400,
                detail="No text could be extracted from the file",
            )

        doc_title = title or filename
        logger.info(f"Enhanced processing document: {doc_title} ({len(text)} characters)")

        # Process with enhanced processor
        document, chunk_count = await processor.process_text(
            text=text,
            title=doc_title,
            repository=repository,
            source=filename,
            extract_entities=extract_entities,
        )
        
        logger.info(f"Enhanced processing complete: {document.id} with {chunk_count} chunks")

        return {
            "document_id": str(document.id),
            "title": document.title,
            "status": "processed_enhanced",
            "chunks": chunk_count,
            "message": "Document uploaded and processed with enhanced features",
            "features": [
                "semantic_chunking",
                "entity_disambiguation",
                "chunk_relationships",
                "entity_mentions",
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in enhanced upload: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing document: {str(e)}",
        )


@router.post("/text", response_model=None)
async def create_document_from_text(
    title: str,
    content: str,
    source: Optional[str] = None,
    repository: Neo4jRepository = Depends(get_neo4j_repository),
    processor: DocumentProcessor = Depends(get_document_processor),
):
    """Create a document from raw text."""
    try:
        document, chunk_count = await processor.process_text(
            text=content,
            title=title,
            repository=repository,
            source=source,
        )

        return {
            "document_id": str(document.id),
            "title": document.title,
            "status": "processed",
            "chunks": chunk_count,
            "message": "Document created and processed successfully",
        }

    except Exception as e:
        logger.error(f"Error creating document: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating document: {str(e)}",
        )


@router.get("/{document_id}", response_model=Document)
async def get_document(
    document_id: UUID,
    repository: Neo4jRepository = Depends(get_neo4j_repository),
) -> Document:
    """Get a document by ID."""
    document = await repository.get_document(document_id)
    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document {document_id} not found",
        )
    return document


@router.delete("/{document_id}", response_model=None)
async def delete_document(
    document_id: UUID,
    repository: Neo4jRepository = Depends(get_neo4j_repository),
):
    """Delete a document and all associated data."""
    deleted = await repository.delete_document(document_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Document {document_id} not found",
        )

    return {
        "document_id": str(document_id),
        "status": "deleted",
        "message": "Document and associated data deleted successfully",
    }


@router.get("/", response_model=list[dict])
async def list_documents(
    limit: int = 100,
    repository: Neo4jRepository = Depends(get_neo4j_repository),
) -> list[dict]:
    """List all documents."""
    query = """
    MATCH (d:Document)
    RETURN d.id as id, d.title as title, d.source as source, d.created_at as created_at
    ORDER BY d.created_at DESC
    LIMIT $limit
    """

    documents = []
    async with repository._driver.session(database=repository.database) as session:
        result = await session.run(query, {"limit": limit})
        async for record in result:
            documents.append({
                "id": record["id"],
                "title": record["title"],
                "source": record["source"],
                "created_at": record["created_at"].isoformat() if record["created_at"] else None,
            })

    return documents


@router.post("/{document_id}/extract-entities", response_model=None)
async def extract_entities_for_document(
    document_id: UUID,
    repository: Neo4jRepository = Depends(get_neo4j_repository),
    processor: DocumentProcessor = Depends(get_document_processor),
):
    """Extract entities for a document's chunks (background job).
    
    Use this to process entities for documents uploaded with extract_entities=False.
    """
    try:
        # Get document
        document = await repository.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
        
        # Get all chunks for this document
        query = """
        MATCH (d:Document {id: $document_id})-[:HAS_CHUNK]->(c:Chunk)
        RETURN c
        ORDER BY c.chunk_index
        """
        
        chunks = []
        async with repository._driver.session(database=repository.database) as session:
            result = await session.run(query, {"document_id": str(document_id)})
            async for record in result:
                from app.repositories.neo4j_repository import neo4j_datetime_to_python
                import json
                node = record["c"]
                metadata_str = node.get("metadata", "{}")
                metadata = json.loads(metadata_str) if metadata_str else {}
                from app.domain import Chunk
                chunk = Chunk(
                    id=UUID(node["id"]),
                    document_id=document_id,
                    content=node["content"],
                    embedding=node.get("embedding"),
                    chunk_index=node["chunk_index"],
                    start_char=node["start_char"],
                    end_char=node["end_char"],
                    metadata=metadata,
                    created_at=neo4j_datetime_to_python(node["created_at"]),
                )
                chunks.append(chunk)
        
        if not chunks:
            raise HTTPException(status_code=404, detail=f"No chunks found for document {document_id}")
        
        # Process entities for all chunks
        await processor._process_entities_batch(chunks, repository)
        
        return {
            "status": "success",
            "message": f"Extracted entities for {len(chunks)} chunks",
            "document_id": str(document_id),
            "chunks_processed": len(chunks),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error extracting entities: {str(e)}",
        )

