"""Document processing service for chunking and processing documents."""

from typing import Optional
from uuid import UUID

from loguru import logger

from app.domain import Chunk, Document
from app.repositories import Neo4jRepository
from app.services.embedding_service import EmbeddingService
from app.services.entity_extractor import EntityExtractor


class DocumentProcessor:
    """Service for processing documents into chunks and extracting knowledge."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        entity_extractor: EntityExtractor,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> None:
        """Initialize document processor."""
        self.embedding_service = embedding_service
        self.entity_extractor = entity_extractor
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        logger.info(
            f"Initialized DocumentProcessor (chunk_size={chunk_size}, overlap={chunk_overlap})"
        )

    def create_chunks(self, document: Document) -> list[Chunk]:
        """Split document into overlapping chunks."""
        text = document.content
        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            end = min(start + self.chunk_size, len(text))

            # Try to break at sentence boundary if not at end
            if end < len(text):
                # Look for sentence endings
                for delimiter in [". ", ".\n", "! ", "!\n", "? ", "?\n"]:
                    last_delimiter = text.rfind(delimiter, start, end)
                    if last_delimiter != -1:
                        end = last_delimiter + 1
                        break

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunk = Chunk(
                    document_id=document.id,
                    content=chunk_text,
                    chunk_index=chunk_index,
                    start_char=start,
                    end_char=end,
                    metadata={
                        "document_title": document.title,
                        "document_source": document.source,
                    },
                )
                chunks.append(chunk)
                chunk_index += 1

            # Move to next chunk with overlap
            start = end - self.chunk_overlap if end < len(text) else end

        logger.info(f"Created {len(chunks)} chunks from document {document.id}")
        return chunks

    async def process_document(
        self, document: Document, repository: Neo4jRepository
    ) -> Document:
        """Process a document: create chunks, generate embeddings, extract entities."""
        logger.info(f"Processing document: {document.title}")

        # Save document
        await repository.create_document(document)

        # Create chunks
        chunks = self.create_chunks(document)

        # Process chunks in parallel batches
        for chunk in chunks:
            # Save chunk
            await repository.create_chunk(chunk)

            # Generate embedding
            embedding = await self.embedding_service.generate_embedding(chunk.content)
            await repository.set_chunk_embedding(chunk.id, embedding)

            # Extract entities and relationships
            entities, relationships = await self.entity_extractor.extract_entities_and_relationships(
                chunk.content
            )

            # Save entities and link to chunk
            for entity in entities:
                saved_entity = await repository.create_entity(entity)
                await repository.link_chunk_to_entity(chunk.id, saved_entity.id)

            # Create relationships between entities
            for relationship in relationships:
                await repository.create_relationship(relationship)

            logger.debug(f"Processed chunk {chunk.chunk_index}")

        logger.info(f"Successfully processed document: {document.title}")
        return document

    async def process_text(
        self, text: str, title: str, repository: Neo4jRepository, source: Optional[str] = None
    ) -> Document:
        """Process raw text as a document."""
        document = Document(
            title=title,
            content=text,
            source=source,
        )
        return await self.process_document(document, repository)
