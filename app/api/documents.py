"""API endpoints for document management."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from loguru import logger

from app.core import get_document_processor, get_neo4j_repository
from app.domain import Document
from app.repositories import Neo4jRepository
from app.services import DocumentProcessor

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=dict)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = None,
    repository: Neo4jRepository = Depends(get_neo4j_repository),
    processor: DocumentProcessor = Depends(get_document_processor),
) -> dict:
    """Upload and process a document."""
    try:
        # Read file content
        content = await file.read()
        text = content.decode("utf-8")

        # Use filename as title if not provided
        doc_title = title or file.filename or "Untitled"

        # Process document
        document = await processor.process_text(
            text=text,
            title=doc_title,
            repository=repository,
            source=file.filename,
        )

        return {
            "document_id": str(document.id),
            "title": document.title,
            "status": "processed",
            "message": "Document uploaded and processed successfully",
        }

    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File must be a valid UTF-8 encoded text file",
        )
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing document: {str(e)}",
        )


@router.post("/text", response_model=dict)
async def create_document_from_text(
    title: str,
    content: str,
    source: Optional[str] = None,
    repository: Neo4jRepository = Depends(get_neo4j_repository),
    processor: DocumentProcessor = Depends(get_document_processor),
) -> dict:
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


@router.delete("/{document_id}", response_model=dict)
async def delete_document(
    document_id: UUID,
    repository: Neo4jRepository = Depends(get_neo4j_repository),
) -> dict:
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
