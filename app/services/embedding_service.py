"""Embedding service for generating vector embeddings."""

from typing import Optional

import openai
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential


class EmbeddingService:
    """Service for generating embeddings using OpenAI."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-large",
        embedding_cache: Optional[any] = None,
        dimensions: int = 1536,  # Neo4j limit is 2048, 1536 is safe and efficient
    ) -> None:
        """Initialize embedding service."""
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        self.embedding_cache = embedding_cache
        self.dimensions = dimensions
        logger.info(f"Initialized EmbeddingService with model: {model}, dimensions: {dimensions} (cache={'enabled' if embedding_cache else 'disabled'})")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text with caching."""
        # Try cache first
        if self.embedding_cache:
            cached = await self.embedding_cache.get_embedding(text)
            if cached:
                logger.debug(f"Cache hit for embedding (length {len(text)})")
                return cached
        
        # Generate new embedding
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimensions,
            )
            embedding = response.data[0].embedding
            logger.debug(f"Generated embedding for text of length {len(text)}")
            
            # Cache for future use
            if self.embedding_cache:
                await self.embedding_cache.set_embedding(text, embedding)
            
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in batch."""
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=self.dimensions,
            )
            embeddings = [item.embedding for item in response.data]
            logger.info(f"Generated {len(embeddings)} embeddings")
            return embeddings
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            raise

    async def compute_similarity(self, embedding1: list[float], embedding2: list[float]) -> float:
        """Compute cosine similarity between two embeddings."""
        import numpy as np

        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)
        return float(similarity)
