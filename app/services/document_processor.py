"""Document processing service for chunking and processing documents."""

import asyncio
import psutil
from typing import AsyncGenerator, Iterator, Optional
from uuid import UUID

from loguru import logger

from app.domain import Chunk, Document
from app.repositories import Neo4jRepository
from app.services.embedding_service import EmbeddingService
from app.services.entity_extractor import EntityExtractor


# Memory safety constants
MAX_CHUNK_MEMORY_MB = 5  # Max memory per chunk operation
STREAM_BUFFER_SIZE = 64 * 1024  # 64KB buffer for streaming


def log_memory_usage(operation: str) -> None:
    """Log current memory usage for monitoring."""
    process = psutil.Process()
    mem_info = process.memory_info()
    mem_mb = mem_info.rss / 1024 / 1024
    logger.info(f"[MEMORY] {operation}: {mem_mb:.2f} MB RSS")


def check_memory_limit() -> None:
    """Check if memory usage is within safe limits for VM."""
    process = psutil.Process()
    mem_info = process.memory_info()
    mem_mb = mem_info.rss / 1024 / 1024
    
    # Warn if approaching 500MB (conservative limit for VM)
    if mem_mb > 500:
        logger.warning(f"[MEMORY] High memory usage detected: {mem_mb:.2f} MB")


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

    def _create_chunks_streaming(self, text: str, document: Document) -> Iterator[Chunk]:
        """Split document into overlapping chunks using streaming (generator).
        
        This yields chunks one at a time without storing all in memory.
        Never duplicates the entire text string.
        """
        start = 0
        chunk_index = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)

            # Try to break at sentence boundary if not at end
            if end < text_len:
                # Look for sentence endings
                for delimiter in [". ", ".\n", "! ", "!\n", "? ", "?\n"]:
                    last_delimiter = text.rfind(delimiter, start, end)
                    if last_delimiter != -1:
                        end = last_delimiter + 1
                        break

            # Extract chunk text (creates only one substring in memory)
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                # Log memory for first and every 10th chunk
                if chunk_index == 0 or chunk_index % 10 == 0:
                    log_memory_usage(f"Creating chunk {chunk_index}")
                
                check_memory_limit()
                
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
                
                # Yield instead of append - no list accumulation
                yield chunk
                chunk_index += 1

            # Move to next chunk with overlap
            # Ensure we always move forward, even with small chunks
            if end < text_len:
                # Move forward by at least 1 character to avoid infinite loops
                start = max(start + 1, end - self.chunk_overlap)
            else:
                start = end

        logger.info(f"Created {chunk_index} chunks from document {document.id}")

    def create_chunks(self, document: Document) -> list[Chunk]:
        """Split document into overlapping chunks.
        
        NOTE: Returns list for backward compatibility.
        Internally uses streaming to minimize memory usage.
        """
        log_memory_usage("Before create_chunks")
        
        # Use streaming generator internally
        chunks = list(self._create_chunks_streaming(document.content, document))
        
        log_memory_usage(f"After create_chunks ({len(chunks)} chunks)")
        return chunks

    async def process_document(
        self, document: Document, repository: Neo4jRepository, extract_entities: bool = True
    ) -> tuple[Document, int]:
        """Process a document: create chunks, generate embeddings, extract entities.
        
        Args:
            document: Document to process
            repository: Neo4j repository
            extract_entities: If False, only creates chunks and embeddings (much faster)
            
        Returns:
            Tuple of (document, chunk_count)
        """
        logger.info(f"Processing document: {document.title} (extract_entities={extract_entities})")
        log_memory_usage("Start process_document")

        # Save document
        await repository.create_document(document)
        logger.info(f"Document saved to database: {document.id}")

        # Create chunks using streaming generator
        chunk_count = 0
        async for chunk in self._process_chunks_streaming(document, repository, extract_entities):
            chunk_count += 1
            
            # Log progress every 10 chunks
            if chunk_count % 10 == 0:
                log_memory_usage(f"Processed {chunk_count} chunks")
                check_memory_limit()

        log_memory_usage(f"End process_document ({chunk_count} chunks)")
        logger.info(f"Successfully processed document: {document.title} - Created {chunk_count} chunks")
        
        return document, chunk_count
    
    async def _process_chunks_streaming(
        self, document: Document, repository: Neo4jRepository, extract_entities: bool
    ) -> AsyncGenerator[Chunk, None]:
        """Process chunks one at a time using streaming to minimize memory usage.
        
        This is the core memory-safe implementation:
        - Generates one chunk at a time
        - Saves to DB immediately
        - Generates embedding immediately
        - Extracts entities immediately (if requested)
        - Never accumulates chunks in memory
        """
        # Use the streaming chunk generator
        for chunk in self._create_chunks_streaming(document.content, document):
            # Save chunk to DB immediately (don't accumulate)
            await repository.create_chunk(chunk)
            
            # Generate and save embedding immediately
            try:
                log_memory_usage(f"Embedding chunk {chunk.chunk_index}")
                embedding = await self.embedding_service.generate_embedding(chunk.content)
                await repository.set_chunk_embedding(chunk.id, embedding)
                log_memory_usage(f"Embedded chunk {chunk.chunk_index}")
            except Exception as e:
                logger.error(f"Error generating embedding for chunk {chunk.chunk_index}: {e}")
                raise
            
            # Extract entities immediately (if requested)
            if extract_entities:
                try:
                    log_memory_usage(f"Extracting entities chunk {chunk.chunk_index}")
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
                    
                    log_memory_usage(f"Extracted entities chunk {chunk.chunk_index}")
                except Exception as e:
                    logger.error(f"Error processing entities for chunk {chunk.chunk_index}: {e}")
                    # Don't raise - continue with other chunks
            
            # Yield the chunk for counting purposes
            yield chunk
    
    async def _process_embeddings_batch(
        self, chunks: list[Chunk], repository: Neo4jRepository
    ) -> None:
        """Generate embeddings for all chunks in batches.
        
        NOTE: This method kept for backward compatibility with extract_entities endpoint.
        For new uploads, use _process_chunks_streaming instead.
        """
        log_memory_usage("Start _process_embeddings_batch")
        
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i + self.batch_size]
            
            # Don't build large list of texts - process in smaller batches
            for chunk in batch:
                try:
                    log_memory_usage(f"Processing embedding {i + chunk.chunk_index}")
                    embedding = await self.embedding_service.generate_embedding(chunk.content)
                    await repository.set_chunk_embedding(chunk.id, embedding)
                    check_memory_limit()
                except Exception as e:
                    logger.error(f"Error generating embedding for chunk {chunk.chunk_index}: {e}")
                    raise
            
            logger.info(f"Processed embeddings for chunks {i} to {i + len(batch)}")
        
        log_memory_usage("End _process_embeddings_batch")
    
    async def _process_entities_batch(
        self, chunks: list[Chunk], repository: Neo4jRepository
    ) -> None:
        """Extract entities from chunks with limited concurrency.
        
        NOTE: This method kept for backward compatibility with extract_entities endpoint.
        For new uploads, use _process_chunks_streaming instead.
        """
        log_memory_usage("Start _process_entities_batch")
        
        # Process entity extraction with limited concurrency to avoid overwhelming the API
        # Also limits memory usage
        max_concurrent = 2  # Reduced from 3 for VM safety
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_chunk_entities(chunk: Chunk) -> None:
            async with semaphore:
                try:
                    log_memory_usage(f"Extracting entities chunk {chunk.chunk_index}")
                    
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

                    log_memory_usage(f"Extracted entities chunk {chunk.chunk_index}")
                    check_memory_limit()
                except Exception as e:
                    logger.error(f"Error processing entities for chunk {chunk.chunk_index}: {e}")
                    # Don't raise - continue with other chunks
        
        # Process all chunks concurrently (with semaphore limiting)
        await asyncio.gather(*[process_chunk_entities(chunk) for chunk in chunks], return_exceptions=True)
        
        log_memory_usage("End _process_entities_batch")

    async def process_text(
        self, text: str, title: str, repository: Neo4jRepository, source: Optional[str] = None, extract_entities: bool = True
    ) -> tuple[Document, int]:
        """Process raw text as a document.
        
        Returns:
            Tuple of (document, chunk_count)
        """
        document = Document(
            title=title,
            content=text,
            source=source,
        )
        return await self.process_document(document, repository, extract_entities)
