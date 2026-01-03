"""Reranking service using cross-encoder models."""

from typing import Optional

from loguru import logger
from sentence_transformers import CrossEncoder

from app.domain import Chunk, SearchResult


class RerankerService:
    """Service for reranking search results using cross-encoder models."""

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    ) -> None:
        """Initialize reranker service."""
        self.model_name = model_name
        self._model: Optional[CrossEncoder] = None
        logger.info(f"Initialized RerankerService with model: {model_name}")

    def _load_model(self) -> CrossEncoder:
        """Lazy load the cross-encoder model."""
        if self._model is None:
            logger.info(f"Loading cross-encoder model: {self.model_name}")
            self._model = CrossEncoder(self.model_name, max_length=512)
        return self._model

    def rerank(
        self,
        query: str,
        chunks: list[Chunk],
        top_k: Optional[int] = None,
    ) -> list[tuple[Chunk, float]]:
        """Rerank chunks using cross-encoder."""
        if not chunks:
            return []

        model = self._load_model()
        
        # Prepare pairs for cross-encoder
        pairs = [[query, chunk.content] for chunk in chunks]
        
        # Get scores
        scores = model.predict(pairs)
        
        # Sort by score
        results = list(zip(chunks, scores))
        results.sort(key=lambda x: x[1], reverse=True)
        
        if top_k:
            results = results[:top_k]
        
        logger.info(f"Reranked {len(chunks)} chunks, returning top {len(results)}")
        return results

    def rerank_with_diversity(
        self,
        query: str,
        chunks: list[Chunk],
        top_k: int = 5,
        diversity_weight: float = 0.3,
    ) -> list[tuple[Chunk, float]]:
        """Rerank with diversity promotion (MMR-like)."""
        if not chunks:
            return []

        model = self._load_model()
        
        # Get initial scores
        pairs = [[query, chunk.content] for chunk in chunks]
        scores = model.predict(pairs)
        
        # MMR-like selection
        selected = []
        remaining = list(zip(chunks, scores))
        remaining.sort(key=lambda x: x[1], reverse=True)
        
        # Always take the top result
        selected.append(remaining.pop(0))
        
        while len(selected) < top_k and remaining:
            best_score = -float('inf')
            best_idx = 0
            
            for idx, (chunk, score) in enumerate(remaining):
                # Calculate diversity penalty
                max_similarity = 0
                for selected_chunk, _ in selected:
                    # Simple word overlap as diversity measure
                    words1 = set(chunk.content.lower().split())
                    words2 = set(selected_chunk.content.lower().split())
                    similarity = len(words1 & words2) / max(len(words1 | words2), 1)
                    max_similarity = max(max_similarity, similarity)
                
                # MMR score: relevance - diversity penalty
                mmr_score = (1 - diversity_weight) * score - diversity_weight * max_similarity
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx
            
            selected.append(remaining.pop(best_idx))
        
        logger.info(f"Reranked with diversity: {len(selected)} results")
        return selected

    def rerank_search_results(
        self,
        query: str,
        results: list[SearchResult],
        top_k: Optional[int] = None,
    ) -> list[SearchResult]:
        """Rerank SearchResult objects."""
        if not results:
            return []

        model = self._load_model()
        
        # Prepare pairs
        pairs = [[query, result.content] for result in results]
        
        # Get rerank scores
        rerank_scores = model.predict(pairs)
        
        # Update results with rerank scores
        for result, rerank_score in zip(results, rerank_scores):
            result.rerank_score = float(rerank_score)
        
        # Sort by rerank score
        results.sort(key=lambda x: x.rerank_score or 0, reverse=True)
        
        if top_k:
            results = results[:top_k]
        
        logger.info(f"Reranked {len(results)} search results")
        return results
