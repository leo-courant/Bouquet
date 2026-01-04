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
        logger.debug(f"[DEBUG] EmbeddingService.__init__ called with model={model}, dimensions={dimensions}, cache={'enabled' if embedding_cache else 'disabled'}")
        try:
            self.client = openai.AsyncOpenAI(api_key=api_key)
            self.model = model
            self.embedding_cache = embedding_cache
            self.dimensions = dimensions
            logger.info(f"Initialized EmbeddingService with model: {model}, dimensions: {dimensions} (cache={'enabled' if embedding_cache else 'disabled'})")
            logger.debug(f"[DEBUG] EmbeddingService initialized successfully")
        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize EmbeddingService: {type(e).__name__}: {str(e)}")
            logger.exception(f"[EXCEPTION] EmbeddingService.__init__ traceback:")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text with caching."""
        logger.debug(f"[DEBUG] generate_embedding called: text_length={len(text)}")
        # Try cache first
        if self.embedding_cache:
            try:
                logger.debug(f"[DEBUG] Checking cache for embedding")
                cached = await self.embedding_cache.get_embedding(text)
                if cached:
                    logger.debug(f"Cache hit for embedding (length {len(text)})")
                    return cached
                else:
                    logger.debug(f"[DEBUG] Cache miss for embedding")
            except Exception as cache_e:
                logger.warning(f"[WARNING] Cache lookup failed: {type(cache_e).__name__}: {str(cache_e)}")
                # Continue without cache
        
        # Generate new embedding
        try:
            logger.debug(f"[DEBUG] Calling OpenAI API for embedding: model={self.model}, dimensions={self.dimensions}")
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimensions,
            )
            embedding = response.data[0].embedding
            logger.debug(f"[DEBUG] Embedding generated successfully: dimension={len(embedding)}")
            logger.debug(f"Generated embedding for text of length {len(text)}")
            
            # Cache for future use
            if self.embedding_cache:
                try:
                    logger.debug(f"[DEBUG] Caching embedding")
                    await self.embedding_cache.set_embedding(text, embedding)
                except Exception as cache_e:
                    logger.warning(f"[WARNING] Failed to cache embedding: {type(cache_e).__name__}: {str(cache_e)}")
                    # Continue even if caching fails
            
            return embedding
        except openai.APIError as api_e:
            logger.error(f"[ERROR] OpenAI API error generating embedding: {type(api_e).__name__}: {str(api_e)}")
            logger.error(f"[ERROR] API details: status_code={getattr(api_e, 'status_code', 'N/A')}, type={getattr(api_e, 'type', 'N/A')}")
            logger.error(f"[ERROR] Text length: {len(text)}, model: {self.model}")
            logger.exception(f"[EXCEPTION] Embedding generation API error:")
            raise
        except Exception as e:
            logger.error(f"[ERROR] Unexpected error generating embedding: {type(e).__name__}: {str(e)}")
            logger.error(f"[ERROR] Text length: {len(text)}, model: {self.model}")
            logger.exception(f"[EXCEPTION] Embedding generation error:")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in batch."""
        logger.debug(f"[DEBUG] generate_embeddings called: batch_size={len(texts)}")
        try:
            logger.debug(f"[DEBUG] Calling OpenAI API for batch embeddings: model={self.model}, dimensions={self.dimensions}")
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=self.dimensions,
            )
            embeddings = [item.embedding for item in response.data]
            logger.info(f"Generated {len(embeddings)} embeddings")
            logger.debug(f"[DEBUG] Batch embedding completed successfully")
            return embeddings
        except openai.APIError as api_e:
            logger.error(f"[ERROR] OpenAI API error generating batch embeddings: {type(api_e).__name__}: {str(api_e)}")
            logger.error(f"[ERROR] API details: status_code={getattr(api_e, 'status_code', 'N/A')}, type={getattr(api_e, 'type', 'N/A')}")
            logger.error(f"[ERROR] Batch size: {len(texts)}, model: {self.model}")
            logger.exception(f"[EXCEPTION] Batch embedding API error:")
            raise
        except Exception as e:
            logger.error(f"[ERROR] Unexpected error generating batch embeddings: {type(e).__name__}: {str(e)}")
            logger.error(f"[ERROR] Batch size: {len(texts)}, model: {self.model}")
            logger.exception(f"[EXCEPTION] Batch embedding error:")
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
