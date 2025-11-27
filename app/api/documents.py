"""API endpoints for document management."""

from typing import Optional
from uuid import UUID
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from loguru import logger

from app.core import get_document_processor, get_neo4j_repository
from app.domain import Document
from app.repositories import Neo4jRepository
from app.services import DocumentProcessor

router = APIRouter(prefix="/documents", tags=["documents"])


def extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF file."""
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
    extract_entities: bool = False,  # Default to False for faster uploads
    repository: Neo4jRepository = Depends(get_neo4j_repository),
    processor: DocumentProcessor = Depends(get_document_processor),
):
    """Upload and process a document.
    
    Args:
        file: The file to upload
        title: Optional custom title (defaults to filename)
        extract_entities: If True, extracts entities (slow). If False, only creates chunks and embeddings (fast).
    """
    try:
        # Read file content
        content = await file.read()
        
        # Determine file type and extract text
        filename = file.filename or "untitled"
        if filename.lower().endswith('.pdf'):
            logger.info(f"Processing PDF file: {filename}")
            text = extract_text_from_pdf(content)
        else:
            # Try to decode as UTF-8 text
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="File must be a valid UTF-8 text file or PDF",
                )
        
        # Validate text is not empty
        if not text or not text.strip():
            raise HTTPException(
                status_code=400,
                detail="No text could be extracted from the file",
            )

        # Use filename as title if not provided
        doc_title = title or filename

        logger.info(f"Processing document: {doc_title} ({len(text)} characters)")

        # Process document
        document = await processor.process_text(
            text=text,
            title=doc_title,
            repository=repository,
            source=filename,
            extract_entities=extract_entities,
        )

        return {
            "document_id": str(document.id),
            "title": document.title,
            "status": "processed",
            "chunks": len(document.chunks) if hasattr(document, 'chunks') else 0,
            "message": "Document uploaded and processed successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
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
        document = await processor.process_text(
            text=content,
            title=title,
            repository=repository,
            source=source,
        )

        return {
            "document_id": str(document.id),
            "title": document.title,
            "status": "processed",
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

