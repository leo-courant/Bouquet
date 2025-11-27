"""Document processing service for chunking and processing documents."""

import asyncio
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
        batch_size: int = 20,  # Process embeddings in batches
    ) -> None:
        """Initialize document processor."""
        self.embedding_service = embedding_service
        self.entity_extractor = entity_extractor
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.batch_size = batch_size
        logger.info(
            f"Initialized DocumentProcessor (chunk_size={chunk_size}, overlap={chunk_overlap}, batch_size={batch_size})"
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
        self, document: Document, repository: Neo4jRepository, extract_entities: bool = True
    ) -> Document:
        """Process a document: create chunks, generate embeddings, extract entities.
        
        Args:
            document: Document to process
            repository: Neo4j repository
            extract_entities: If False, only creates chunks and embeddings (much faster)
        """
        logger.info(f"Processing document: {document.title} (extract_entities={extract_entities})")

        # Save document
        await repository.create_document(document)

        # Create chunks
        chunks = self.create_chunks(document)
        
        if not chunks:
            logger.warning(f"No chunks created for document {document.title}")
            return document

        # Save all chunks first (fast operation)
        logger.info(f"Saving {len(chunks)} chunks to database...")
        for chunk in chunks:
            await repository.create_chunk(chunk)
        
        # Generate embeddings in batches (much faster than one-by-one)
        logger.info(f"Generating embeddings for {len(chunks)} chunks in batches of {self.batch_size}...")
        await self._process_embeddings_batch(chunks, repository)
        
        # Extract entities only if requested (slow operation)
        if extract_entities:
            logger.info(f"Extracting entities from {len(chunks)} chunks...")
            await self._process_entities_batch(chunks, repository)
        else:
            logger.info("Skipping entity extraction (extract_entities=False)")

        logger.info(f"Successfully processed document: {document.title}")
        return document
    
    async def _process_embeddings_batch(
        self, chunks: list[Chunk], repository: Neo4jRepository
    ) -> None:
        """Generate embeddings for all chunks in batches."""
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i + self.batch_size]
            batch_texts = [chunk.content for chunk in batch]
            
            try:
                # Generate embeddings for the entire batch at once
                embeddings = await self.embedding_service.generate_embeddings(batch_texts)
                
                # Save embeddings
                for chunk, embedding in zip(batch, embeddings):
                    await repository.set_chunk_embedding(chunk.id, embedding)
                
                logger.info(f"Processed embeddings for chunks {i} to {i + len(batch)}")
            except Exception as e:
                logger.error(f"Error processing embedding batch {i}-{i + len(batch)}: {e}")
                # Fallback to individual processing for this batch
                logger.info("Falling back to individual embedding generation...")
                for chunk in batch:
                    try:
                        embedding = await self.embedding_service.generate_embedding(chunk.content)
                        await repository.set_chunk_embedding(chunk.id, embedding)
                    except Exception as e2:
                        logger.error(f"Error generating embedding for chunk {chunk.chunk_index}: {e2}")
                        raise
    
    async def _process_entities_batch(
        self, chunks: list[Chunk], repository: Neo4jRepository
    ) -> None:
        """Extract entities from chunks (optionally in parallel)."""
        # Process entity extraction with limited concurrency to avoid overwhelming the API
        max_concurrent = 3
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_chunk_entities(chunk: Chunk) -> None:
            async with semaphore:
                try:
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

                    logger.debug(f"Processed entities for chunk {chunk.chunk_index}")
                except Exception as e:
                    logger.error(f"Error processing entities for chunk {chunk.chunk_index}: {e}")
                    # Don't raise - continue with other chunks
        
        # Process all chunks concurrently (with semaphore limiting)
        await asyncio.gather(*[process_chunk_entities(chunk) for chunk in chunks], return_exceptions=True)

    async def process_text(
        self, text: str, title: str, repository: Neo4jRepository, source: Optional[str] = None, extract_entities: bool = True
    ) -> Document:
        """Process raw text as a document."""
        document = Document(
            title=title,
            content=text,
            source=source,
        )
        return await self.process_document(document, repository, extract_entities)
