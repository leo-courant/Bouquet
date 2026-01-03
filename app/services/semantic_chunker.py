"""Semantic chunking service for adaptive text segmentation."""

import re
from typing import Optional

import nltk
import numpy as np
from loguru import logger
from sklearn.metrics.pairwise import cosine_similarity

from app.domain import Chunk
from app.services.embedding_service import EmbeddingService

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)


class SemanticChunker:
    """Service for semantic-aware text chunking."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        min_chunk_size: int = 200,
        max_chunk_size: int = 2000,
        semantic_threshold: float = 0.5,
    ) -> None:
        """Initialize semantic chunker."""
        self.embedding_service = embedding_service
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.semantic_threshold = semantic_threshold
        logger.info(
            f"Initialized SemanticChunker (min={min_chunk_size}, max={max_chunk_size}, threshold={semantic_threshold})"
        )

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences using NLTK."""
        sentences = nltk.sent_tokenize(text)
        return [s.strip() for s in sentences if s.strip()]

    async def chunk_by_semantic_similarity(
        self, text: str, document_id
    ) -> list[Chunk]:
        """Chunk text based on semantic similarity between sentences."""
        sentences = self._split_into_sentences(text)
        
        if len(sentences) <= 1:
            # Single sentence, create one chunk
            return [
                Chunk(
                    document_id=document_id,
                    content=text,
                    chunk_index=0,
                    start_char=0,
                    end_char=len(text),
                    semantic_density=1.0,
                )
            ]

        # Generate embeddings for sentences
        logger.debug(f"Generating embeddings for {len(sentences)} sentences")
        embeddings = await self.embedding_service.generate_embeddings(sentences)
        
        # Calculate semantic similarity between consecutive sentences
        similarities = []
        for i in range(len(embeddings) - 1):
            sim = cosine_similarity(
                [embeddings[i]], [embeddings[i + 1]]
            )[0][0]
            similarities.append(sim)

        # Find split points where similarity drops below threshold
        split_indices = [0]
        current_chunk_start = 0
        current_size = len(sentences[0])
        
        for i, sim in enumerate(similarities):
            current_size += len(sentences[i + 1])
            
            # Split if similarity is low AND chunk is large enough
            # OR if chunk is getting too large
            if (sim < self.semantic_threshold and current_size >= self.min_chunk_size) or \
               current_size >= self.max_chunk_size:
                split_indices.append(i + 1)
                current_chunk_start = i + 1
                current_size = 0
        
        if split_indices[-1] != len(sentences):
            split_indices.append(len(sentences))

        # Create chunks
        chunks = []
        char_position = 0
        
        for idx in range(len(split_indices) - 1):
            start_idx = split_indices[idx]
            end_idx = split_indices[idx + 1]
            
            chunk_sentences = sentences[start_idx:end_idx]
            chunk_text = " ".join(chunk_sentences)
            
            # Calculate semantic density (average similarity within chunk)
            if len(chunk_sentences) > 1:
                chunk_embeddings = embeddings[start_idx:end_idx]
                intra_similarities = []
                for i in range(len(chunk_embeddings) - 1):
                    sim = cosine_similarity(
                        [chunk_embeddings[i]], [chunk_embeddings[i + 1]]
                    )[0][0]
                    intra_similarities.append(sim)
                semantic_density = float(np.mean(intra_similarities))
            else:
                semantic_density = 1.0
            
            # Determine topic from first sentence or most central sentence
            topic = self._extract_topic(chunk_sentences)
            
            chunk = Chunk(
                document_id=document_id,
                content=chunk_text,
                chunk_index=idx,
                start_char=char_position,
                end_char=char_position + len(chunk_text),
                semantic_density=semantic_density,
                topic=topic,
            )
            chunks.append(chunk)
            
            # Update position (account for spaces between sentences)
            char_position += len(chunk_text) + 1

        logger.info(f"Created {len(chunks)} semantic chunks from {len(sentences)} sentences")
        return chunks

    def _extract_topic(self, sentences: list[str]) -> str:
        """Extract main topic from sentences (simplified)."""
        if not sentences:
            return "unknown"
        
        # Use first sentence up to first verb or 50 chars
        first_sentence = sentences[0]
        words = first_sentence.split()[:10]  # First 10 words
        topic = " ".join(words)
        
        if len(topic) > 50:
            topic = topic[:47] + "..."
        
        return topic.lower()

    async def create_hierarchical_chunks(
        self, text: str, document_id, levels: int = 2
    ) -> list[Chunk]:
        """Create hierarchical chunks with parent-child relationships."""
        # Level 0: Fine-grained chunks
        base_chunks = await self.chunk_by_semantic_similarity(text, document_id)
        
        if levels == 1 or len(base_chunks) <= 2:
            return base_chunks
        
        # Level 1: Merge chunks into larger semantic groups
        all_chunks = base_chunks.copy()
        parent_chunks = []
        
        i = 0
        while i < len(base_chunks):
            # Merge 2-4 consecutive chunks into parent
            merge_size = min(3, len(base_chunks) - i)
            
            merged_chunks = base_chunks[i:i + merge_size]
            merged_content = " ".join([c.content for c in merged_chunks])
            
            parent_chunk = Chunk(
                document_id=document_id,
                content=merged_content,
                chunk_index=len(parent_chunks),
                start_char=merged_chunks[0].start_char,
                end_char=merged_chunks[-1].end_char,
                semantic_density=float(np.mean([c.semantic_density for c in merged_chunks])),
                topic=merged_chunks[0].topic,
            )
            parent_chunks.append(parent_chunk)
            
            # Set parent references
            for child_chunk in merged_chunks:
                child_chunk.parent_chunk_id = parent_chunk.id
            
            i += merge_size
        
        all_chunks.extend(parent_chunks)
        logger.info(f"Created hierarchical chunks: {len(base_chunks)} base + {len(parent_chunks)} parent")
        
        return all_chunks
