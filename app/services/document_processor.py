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
        logger.debug(f"[DEBUG] DocumentProcessor.__init__ called with chunk_size={chunk_size}, overlap={chunk_overlap}, batch_size={batch_size}")
        try:
            self.embedding_service = embedding_service
            self.entity_extractor = entity_extractor
            self.chunk_size = chunk_size
            self.chunk_overlap = chunk_overlap
            self.batch_size = batch_size
            logger.info(
                f"Initialized DocumentProcessor (chunk_size={chunk_size}, overlap={chunk_overlap}, batch_size={batch_size})"
            )
            logger.debug(f"[DEBUG] DocumentProcessor initialized successfully with embedding_service={type(embedding_service).__name__}, entity_extractor={type(entity_extractor).__name__}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize DocumentProcessor: {type(e).__name__}: {str(e)}")
            logger.exception(f"[EXCEPTION] DocumentProcessor.__init__ traceback:")
            raise

    def _create_chunks_streaming(self, text: str, document: Document) -> Iterator[Chunk]:
        """Split document into overlapping chunks using streaming (generator).
        
        This yields chunks one at a time without storing all in memory.
        Never duplicates the entire text string.
        """
        logger.debug(f"[DEBUG] _create_chunks_streaming called for document_id={document.id}, text_length={len(text)}")
        try:
            start = 0
            chunk_index = 0
            text_len = len(text)
            logger.debug(f"[DEBUG] Starting chunking: start={start}, text_len={text_len}, chunk_size={self.chunk_size}, overlap={self.chunk_overlap}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize chunking for document {document.id}: {type(e).__name__}: {str(e)}")
            logger.exception(f"[EXCEPTION] _create_chunks_streaming initialization error:")
            raise

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
            try:
                chunk_text = text[start:end].strip()
                logger.debug(f"[DEBUG] Extracted chunk_text: start={start}, end={end}, length={len(chunk_text)}")
            except Exception as e:
                logger.error(f"[ERROR] Failed to extract chunk text at start={start}, end={end}: {type(e).__name__}: {str(e)}")
                logger.exception(f"[EXCEPTION] Chunk text extraction error:")
                raise
            
            if chunk_text:
                # Log memory for first and every 10th chunk
                if chunk_index == 0 or chunk_index % 10 == 0:
                    log_memory_usage(f"Creating chunk {chunk_index}")
                
                check_memory_limit()
                
                try:
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
                    logger.debug(f"[DEBUG] Created chunk {chunk_index} for document {document.id}")
                except Exception as e:
                    logger.error(f"[ERROR] Failed to create Chunk object at index {chunk_index}: {type(e).__name__}: {str(e)}")
                    logger.error(f"[ERROR] Chunk params: document_id={document.id}, chunk_index={chunk_index}, start={start}, end={end}")
                    logger.exception(f"[EXCEPTION] Chunk creation error:")
                    raise
                
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
        logger.debug(f"[DEBUG] process_document called: document_id={document.id}, title={document.title}, content_length={len(document.content)}, extract_entities={extract_entities}")
        log_memory_usage("Start process_document")
        
        if not document.content or not document.content.strip():
            logger.error(f"[ERROR] Document has no content: document_id={document.id}, title={document.title}")
            raise ValueError(f"Document {document.id} has no content to process")

        # Save document
        try:
            logger.debug(f"[DEBUG] Attempting to save document to repository: {document.id}")
            await repository.create_document(document)
            logger.info(f"Document saved to database: {document.id}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to save document {document.id} to database: {type(e).__name__}: {str(e)}")
            logger.exception(f"[EXCEPTION] Document save error:")
            raise

        # Create chunks using streaming generator
        chunk_count = 0
        try:
            logger.debug(f"[DEBUG] Starting chunk streaming for document {document.id}")
            async for chunk in self._process_chunks_streaming(document, repository, extract_entities):
                chunk_count += 1
                
                # Log progress every 10 chunks
                if chunk_count % 10 == 0:
                    log_memory_usage(f"Processed {chunk_count} chunks")
                    check_memory_limit()
        except Exception as e:
            logger.error(f"[ERROR] Failed during chunk streaming for document {document.id} at chunk {chunk_count}: {type(e).__name__}: {str(e)}")
            logger.exception(f"[EXCEPTION] Chunk streaming error:")
            raise

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
            try:
                logger.debug(f"[DEBUG] Saving chunk {chunk.chunk_index} (id={chunk.id}) to database")
                await repository.create_chunk(chunk)
                logger.debug(f"[DEBUG] Chunk {chunk.chunk_index} saved successfully")
            except Exception as e:
                logger.error(f"[ERROR] Failed to save chunk {chunk.chunk_index} (id={chunk.id}) to database: {type(e).__name__}: {str(e)}")
                logger.exception(f"[EXCEPTION] Chunk save error:")
                raise
            
            # Generate and save embedding immediately
            try:
                log_memory_usage(f"Embedding chunk {chunk.chunk_index}")
                logger.debug(f"[DEBUG] Generating embedding for chunk {chunk.chunk_index}, content_length={len(chunk.content)}")
                embedding = await self.embedding_service.generate_embedding(chunk.content)
                logger.debug(f"[DEBUG] Embedding generated, dimension={len(embedding)}")
                await repository.set_chunk_embedding(chunk.id, embedding)
                log_memory_usage(f"Embedded chunk {chunk.chunk_index}")
                logger.debug(f"[DEBUG] Embedding saved for chunk {chunk.chunk_index}")
            except Exception as e:
                logger.error(f"[ERROR] Failed to generate/save embedding for chunk {chunk.chunk_index}: {type(e).__name__}: {str(e)}")
                logger.error(f"[ERROR] Chunk details: id={chunk.id}, content_length={len(chunk.content)}")
                logger.exception(f"[EXCEPTION] Embedding generation error:")
                raise
            
            # Extract entities immediately (if requested)
            if extract_entities:
                try:
                    log_memory_usage(f"Extracting entities chunk {chunk.chunk_index}")
                    logger.debug(f"[DEBUG] Extracting entities for chunk {chunk.chunk_index}")
                    entities, relationships = await self.entity_extractor.extract_entities_and_relationships(
                        chunk.content
                    )
                    logger.debug(f"[DEBUG] Extracted {len(entities)} entities and {len(relationships)} relationships for chunk {chunk.chunk_index}")

                    # Save entities and link to chunk
                    for idx, entity in enumerate(entities):
                        try:
                            logger.debug(f"[DEBUG] Saving entity {idx+1}/{len(entities)}: {entity.name} (type={entity.entity_type})")
                            saved_entity = await repository.create_entity(entity)
                            await repository.link_chunk_to_entity(chunk.id, saved_entity.id)
                            logger.debug(f"[DEBUG] Entity saved and linked: {saved_entity.id}")
                        except Exception as entity_e:
                            logger.error(f"[ERROR] Failed to save entity {entity.name}: {type(entity_e).__name__}: {str(entity_e)}")
                            logger.exception(f"[EXCEPTION] Entity save error:")
                            # Continue with other entities

                    # Create relationships between entities
                    for idx, relationship in enumerate(relationships):
                        try:
                            logger.debug(f"[DEBUG] Creating relationship {idx+1}/{len(relationships)}: {relationship.source_entity_id} -> {relationship.target_entity_id} ({relationship.relationship_type})")
                            await repository.create_relationship(relationship)
                        except Exception as rel_e:
                            logger.error(f"[ERROR] Failed to create relationship: {type(rel_e).__name__}: {str(rel_e)}")
                            logger.exception(f"[EXCEPTION] Relationship creation error:")
                            # Continue with other relationships
                    
                    log_memory_usage(f"Extracted entities chunk {chunk.chunk_index}")
                    logger.debug(f"[DEBUG] Entity extraction completed for chunk {chunk.chunk_index}")
                except Exception as e:
                    logger.error(f"[ERROR] Failed to process entities for chunk {chunk.chunk_index}: {type(e).__name__}: {str(e)}")
                    logger.exception(f"[EXCEPTION] Entity processing error:")
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
