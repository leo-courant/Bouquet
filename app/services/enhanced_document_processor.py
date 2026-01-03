"""Enhanced document processor with semantic chunking and chunk relationships."""

import asyncio
from datetime import datetime
from typing import AsyncGenerator, Optional

import psutil
from loguru import logger

from app.domain import Chunk, ChunkRelationType, Document, EntityMention, EntityRole
from app.repositories import Neo4jRepository
from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import EmbeddingService
from app.services.entity_disambiguator import EntityDisambiguator
from app.services.entity_extractor import EntityExtractor
from app.services.semantic_chunker import SemanticChunker


class EnhancedDocumentProcessor:
    """Enhanced document processor with semantic chunking and advanced features."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        entity_extractor: EntityExtractor,
        entity_disambiguator: EntityDisambiguator,
        use_semantic_chunking: bool = True,
        min_chunk_size: int = 200,
        max_chunk_size: int = 2000,
        semantic_threshold: float = 0.5,
        create_chunk_relationships: bool = True,
        enable_entity_disambiguation: bool = True,
    ) -> None:
        """Initialize enhanced document processor."""
        self.embedding_service = embedding_service
        self.entity_extractor = entity_extractor
        self.entity_disambiguator = entity_disambiguator
        
        # Create semantic chunker if enabled
        self.semantic_chunker = None
        if use_semantic_chunking:
            self.semantic_chunker = SemanticChunker(
                embedding_service=embedding_service,
                min_chunk_size=min_chunk_size,
                max_chunk_size=max_chunk_size,
                semantic_threshold=semantic_threshold,
            )
        
        # Fallback to standard processor
        self.standard_processor = DocumentProcessor(
            embedding_service=embedding_service,
            entity_extractor=entity_extractor,
            chunk_size=1000,
            chunk_overlap=200,
        )
        
        self.create_chunk_relationships = create_chunk_relationships
        self.enable_entity_disambiguation = enable_entity_disambiguation
        
        logger.info(
            f"Initialized EnhancedDocumentProcessor "
            f"(semantic_chunking={use_semantic_chunking}, "
            f"chunk_relationships={create_chunk_relationships}, "
            f"disambiguation={enable_entity_disambiguation})"
        )

    async def process_document(
        self,
        document: Document,
        repository: Neo4jRepository,
        extract_entities: bool = True,
    ) -> tuple[Document, int]:
        """Process document with enhanced features."""
        logger.info(f"Enhanced processing document: {document.title}")
        
        # Save document with version and summary
        document.version = 1
        document.updated_at = datetime.utcnow()
        
        # Generate document summary if content is large
        if len(document.content) > 5000:
            document.summary = await self.entity_extractor.generate_summary(
                document.content[:5000], max_length=200
            )
        
        await repository.create_document(document)
        logger.info(f"Document saved: {document.id}")
        
        # Create chunks using semantic chunking
        if self.semantic_chunker:
            chunks = await self.semantic_chunker.chunk_by_semantic_similarity(
                document.content, document.id
            )
        else:
            chunks = self.standard_processor.create_chunks(document)
        
        logger.info(f"Created {len(chunks)} chunks")
        
        # Process each chunk
        all_entities = []
        for i, chunk in enumerate(chunks):
            # Save chunk
            await repository.create_chunk(chunk)
            
            # Generate embedding
            embedding = await self.embedding_service.generate_embedding(chunk.content)
            await repository.set_chunk_embedding(chunk.id, embedding)
            
            # Generate chunk summary for long chunks
            if len(chunk.content) > 500 and not chunk.summary:
                chunk.summary = await self.entity_extractor.generate_summary(
                    chunk.content, max_length=100
                )
            
            # Extract entities if requested
            if extract_entities:
                entities, relationships = await self.entity_extractor.extract_entities_and_relationships(
                    chunk.content
                )
                
                # Process entities with mentions
                for entity in entities:
                    # Track entity timing
                    entity.first_seen = datetime.utcnow()
                    entity.last_seen = datetime.utcnow()
                    
                    saved_entity = await repository.create_entity(entity)
                    all_entities.append(saved_entity)
                    
                    # Create rich entity mention
                    # Determine role (simple heuristic)
                    role = EntityRole.CONTEXT
                    if entity.name.lower() in chunk.content[:100].lower():
                        role = EntityRole.SUBJECT
                    
                    # Calculate salience (position-based)
                    position = chunk.content.lower().find(entity.name.lower())
                    salience = 1.0 - (position / len(chunk.content)) if position >= 0 else 0.5
                    
                    await repository.create_entity_mention(
                        entity_id=saved_entity.id,
                        chunk_id=chunk.id,
                        mention_text=entity.name,
                        role=role.value,
                        salience=salience,
                        position=position,
                    )
                    
                    # Also create legacy link for compatibility
                    await repository.link_chunk_to_entity(chunk.id, saved_entity.id)
                
                # Create relationships
                for relationship in relationships:
                    # Add temporal tracking
                    relationship.temporal_start = datetime.utcnow()
                    await repository.create_relationship(relationship)
            
            # Log progress
            if (i + 1) % 10 == 0:
                logger.info(f"Processed {i + 1}/{len(chunks)} chunks")
        
        # Create chunk relationships
        if self.create_chunk_relationships:
            await self._create_chunk_relationships(chunks, repository, document.id)
        
        # Entity disambiguation
        if extract_entities and self.enable_entity_disambiguation and all_entities:
            await self._disambiguate_entities(all_entities, document.content, repository)
        
        # Generate entity summaries
        if extract_entities and all_entities:
            await self._generate_entity_summaries(all_entities, repository)
        
        logger.info(
            f"Successfully processed document: {document.title} - "
            f"{len(chunks)} chunks, {len(all_entities)} entities"
        )
        
        return document, len(chunks)

    async def _create_chunk_relationships(
        self,
        chunks: list[Chunk],
        repository: Neo4jRepository,
        document_id,
    ) -> None:
        """Create semantic relationships between chunks."""
        logger.info("Creating semantic chunk relationships...")
        
        # Sequential FOLLOWS relationships
        await repository.link_sequential_chunks(document_id)
        
        # Get embeddings for all chunks to compute semantic similarity
        chunk_embeddings = {}
        for chunk in chunks:
            embedding = await repository.get_chunk_embedding(chunk.id)
            if embedding:
                chunk_embeddings[chunk.id] = embedding
        
        # Analyze relationships between chunks
        for i, chunk1 in enumerate(chunks):
            if chunk1.id not in chunk_embeddings:
                continue
                
            entities1 = await repository.get_entities_for_chunk(chunk1.id)
            entity_names1 = {e.name.lower() for e in entities1}
            
            # Check nearby chunks for semantic relationships
            for j, chunk2 in enumerate(chunks[i+1:i+10], start=i+1):  # Check next 9 chunks
                if chunk2.id not in chunk_embeddings:
                    continue
                
                # Compute semantic similarity
                similarity = self._cosine_similarity(
                    chunk_embeddings[chunk1.id],
                    chunk_embeddings[chunk2.id]
                )
                
                # Get entities for semantic analysis
                entities2 = await repository.get_entities_for_chunk(chunk2.id)
                entity_names2 = {e.name.lower() for e in entities2}
                shared_entities = entity_names1 & entity_names2
                
                # Determine relationship type and whether to create it
                relation_type, weight, description = await self._classify_chunk_relationship(
                    chunk1, chunk2, similarity, shared_entities
                )
                
                if relation_type and weight > 0.3:  # Only create meaningful relationships
                    await repository.create_chunk_relationship(
                        chunk1.id,
                        chunk2.id,
                        relation_type,
                        weight=weight,
                        description=description,
                    )
        
        logger.info("Semantic chunk relationships created")
    
    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        import math
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        return dot_product / (magnitude1 * magnitude2)
    
    async def _classify_chunk_relationship(
        self,
        chunk1: Chunk,
        chunk2: Chunk,
        similarity: float,
        shared_entities: set[str],
    ) -> tuple[Optional[str], float, str]:
        """Classify the relationship between two chunks based on content and semantics."""
        # High similarity with shared entities -> ELABORATES
        if similarity > 0.75 and shared_entities:
            return (
                ChunkRelationType.ELABORATES.value,
                similarity,
                f"Elaborates on {', '.join(list(shared_entities)[:3])}"
            )
        
        # Moderate similarity with shared entities -> REFERENCES
        if 0.4 < similarity <= 0.75 and shared_entities:
            return (
                ChunkRelationType.REFERENCES.value,
                similarity * 0.8,
                f"References {', '.join(list(shared_entities)[:3])}"
            )
        
        # Look for contradiction indicators
        contradiction_terms = {
            'however', 'but', 'although', 'despite', 'conversely', 
            'on the contrary', 'in contrast', 'nevertheless', 'yet',
            'whereas', 'unlike', 'contradicts', 'disagrees'
        }
        
        chunk2_lower = chunk2.content.lower()
        has_contradiction = any(term in chunk2_lower for term in contradiction_terms)
        
        # Shared entities but low similarity or contradiction terms -> CONTRADICTS
        if shared_entities and (similarity < 0.4 or has_contradiction):
            # Check if chunk2 mentions chunk1 entities in a contradictory way
            if has_contradiction:
                return (
                    ChunkRelationType.CONTRADICTS.value,
                    0.7,
                    f"Contradicts claims about {', '.join(list(shared_entities)[:2])}"
                )
        
        # Look for support indicators
        support_terms = {
            'supports', 'confirms', 'validates', 'proves', 'demonstrates',
            'shows', 'evidence', 'furthermore', 'moreover', 'additionally',
            'similarly', 'likewise', 'also', 'agrees'
        }
        
        has_support = any(term in chunk2_lower for term in support_terms)
        
        # Shared entities with support terms -> SUPPORTS
        if shared_entities and has_support and similarity > 0.5:
            return (
                ChunkRelationType.SUPPORTS.value,
                similarity * 0.9,
                f"Supports claims about {', '.join(list(shared_entities)[:2])}"
            )
        
        # Moderate to high similarity without shared entities -> REFERENCES
        if similarity > 0.5 and not shared_entities:
            return (
                ChunkRelationType.REFERENCES.value,
                similarity * 0.6,
                "Semantically related content"
            )
        
        # No meaningful relationship
        return None, 0.0, ""

    async def _disambiguate_entities(
        self,
        entities: list,
        context: str,
        repository: Neo4jRepository,
    ) -> None:
        """Disambiguate entities and update database."""
        logger.info("Disambiguating entities...")
        
        try:
            # Get canonical mapping
            canonical_mapping = await self.entity_disambiguator.disambiguate_entities(
                entities, context
            )
            
            # Merge entities and update
            merged_entities = self.entity_disambiguator.merge_entities(
                entities, canonical_mapping
            )
            
            # Update database with disambiguation info
            for entity in merged_entities:
                await repository.update_entity_with_disambiguation(
                    entity.id,
                    entity.canonical_name or entity.name,
                    entity.aliases,
                    entity.confidence,
                )
            
            logger.info(f"Disambiguated {len(entities)} entities into {len(merged_entities)} canonical entities")
            
        except Exception as e:
            logger.error(f"Error disambiguating entities: {e}")

    async def _generate_entity_summaries(
        self,
        entities: list,
        repository: Neo4jRepository,
    ) -> None:
        """Generate summaries for entities from their mentions."""
        logger.info("Generating entity summaries...")
        
        for entity in entities[:20]:  # Limit to avoid too many API calls
            try:
                summary = await repository.get_entity_summary_from_chunks(entity.id)
                if summary:
                    entity.summary = summary
                    # Update in DB (would need new method)
                    logger.debug(f"Generated summary for entity: {entity.name}")
            except Exception as e:
                logger.warning(f"Error generating summary for {entity.name}: {e}")
        
        logger.info("Entity summaries generated")

    async def process_text(
        self,
        text: str,
        title: str,
        repository: Neo4jRepository,
        source: Optional[str] = None,
        extract_entities: bool = True,
    ) -> tuple[Document, int]:
        """Process raw text as a document."""
        document = Document(
            title=title,
            content=text,
            source=source,
        )
        return await self.process_document(document, repository, extract_entities)
