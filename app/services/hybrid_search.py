"""Hybrid search combining vector similarity and BM25."""

from typing import Optional

import numpy as np
from loguru import logger
from rank_bm25 import BM25Okapi

from app.domain import Chunk, SearchResult


class HybridSearchEngine:
    """Service for hybrid search combining vector and lexical retrieval."""

    def __init__(
        self,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
    ) -> None:
        """Initialize hybrid search engine."""
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.bm25_index: Optional[BM25Okapi] = None
        self.indexed_chunks: list[Chunk] = []
        logger.info(
            f"Initialized HybridSearchEngine (vector_weight={vector_weight}, bm25_weight={bm25_weight})"
        )

    def build_bm25_index(self, chunks: list[Chunk]) -> None:
        """Build BM25 index from chunks."""
        self.indexed_chunks = chunks
        
        # Tokenize chunks
        tokenized_corpus = [chunk.content.lower().split() for chunk in chunks]
        
        # Build BM25 index
        self.bm25_index = BM25Okapi(tokenized_corpus)
        logger.info(f"Built BM25 index with {len(chunks)} chunks")

    def search_bm25(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        """Search using BM25."""
        if not self.bm25_index or not self.indexed_chunks:
            logger.warning("BM25 index not built")
            return []

        tokenized_query = query.lower().split()
        scores = self.bm25_index.get_scores(tokenized_query)
        
        # Get top-k indices and scores
        top_indices = np.argsort(scores)[::-1][:top_k]
        results = [(int(idx), float(scores[idx])) for idx in top_indices if scores[idx] > 0]
        
        logger.debug(f"BM25 search returned {len(results)} results")
        return results

    def combine_scores(
        self,
        vector_results: list[tuple[Chunk, float]],
        bm25_results: list[tuple[int, float]],
        normalize: bool = True,
    ) -> list[tuple[Chunk, float, dict]]:
        """Combine vector and BM25 scores using weighted sum."""
        # Create score dictionaries
        vector_scores = {chunk.id: score for chunk, score in vector_results}
        
        # Map BM25 indices to chunks
        bm25_scores = {}
        for idx, score in bm25_results:
            if idx < len(self.indexed_chunks):
                chunk = self.indexed_chunks[idx]
                bm25_scores[chunk.id] = score

        # Normalize scores if requested
        if normalize and vector_scores:
            max_vector = max(vector_scores.values()) if vector_scores else 1.0
            vector_scores = {k: v / max_vector for k, v in vector_scores.items()}
        
        if normalize and bm25_scores:
            max_bm25 = max(bm25_scores.values()) if bm25_scores else 1.0
            bm25_scores = {k: v / max_bm25 for k, v in bm25_scores.items()}

        # Combine scores
        combined = {}
        all_chunk_ids = set(vector_scores.keys()) | set(bm25_scores.keys())
        
        for chunk_id in all_chunk_ids:
            v_score = vector_scores.get(chunk_id, 0.0)
            b_score = bm25_scores.get(chunk_id, 0.0)
            
            combined_score = (
                self.vector_weight * v_score + self.bm25_weight * b_score
            )
            combined[chunk_id] = {
                'combined': combined_score,
                'vector': v_score,
                'bm25': b_score,
            }

        # Get chunks and sort by combined score
        chunk_map = {chunk.id: chunk for chunk, _ in vector_results}
        for idx, _ in bm25_results:
            if idx < len(self.indexed_chunks):
                chunk = self.indexed_chunks[idx]
                if chunk.id not in chunk_map:
                    chunk_map[chunk.id] = chunk

        results = [
            (chunk_map[chunk_id], scores['combined'], scores)
            for chunk_id, scores in combined.items()
            if chunk_id in chunk_map
        ]
        
        results.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"Combined {len(vector_results)} vector + {len(bm25_results)} BM25 results into {len(results)} hybrid results")
        return results

    def reciprocal_rank_fusion(
        self,
        vector_results: list[tuple[Chunk, float]],
        bm25_results: list[tuple[int, float]],
        k: int = 60,
    ) -> list[tuple[Chunk, float]]:
        """Combine results using Reciprocal Rank Fusion (RRF)."""
        rrf_scores = {}
        
        # Add vector results
        for rank, (chunk, _) in enumerate(vector_results, start=1):
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0) + 1 / (k + rank)
        
        # Add BM25 results
        chunk_map = {}
        for rank, (idx, _) in enumerate(bm25_results, start=1):
            if idx < len(self.indexed_chunks):
                chunk = self.indexed_chunks[idx]
                chunk_map[chunk.id] = chunk
                rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0) + 1 / (k + rank)
        
        # Add chunks from vector results to map
        for chunk, _ in vector_results:
            chunk_map[chunk.id] = chunk
        
        # Sort by RRF score
        results = [
            (chunk_map[chunk_id], score)
            for chunk_id, score in rrf_scores.items()
            if chunk_id in chunk_map
        ]
        results.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"RRF fusion produced {len(results)} results")
        return results
