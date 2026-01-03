"""Context compression service to optimize LLM input."""

from typing import Optional

import openai
from loguru import logger


class ContextCompressor:
    """Compresses retrieved context to fit more information in limited tokens."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
        compression_ratio: float = 0.6,
    ) -> None:
        """Initialize context compressor.
        
        Args:
            compression_ratio: Target ratio (0.6 = compress to 60% of original)
        """
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        self.compression_ratio = compression_ratio
        logger.info(f"Initialized ContextCompressor (ratio={compression_ratio})")

    async def compress_context(
        self,
        context: str,
        query: str,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Compress context while preserving query-relevant information.
        
        Uses LLM to intelligently remove redundant or irrelevant information.
        """
        if not context or len(context) < 500:
            return context  # Don't compress short context
        
        try:
            target_length = max_tokens or int(len(context.split()) * self.compression_ratio)
            
            prompt = f"""Compress the following context to approximately {target_length} words while preserving all information relevant to answering the query.

Query: {query}

Context to compress:
{context}

Compressed context (remove redundancy, keep facts and details relevant to the query):"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at compressing text while preserving essential information. Remove redundancy and irrelevant details, but keep all facts and details needed to answer the query."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,  # Deterministic compression
                max_tokens=max_tokens or 2000,
            )

            compressed = response.choices[0].message.content or context
            
            original_len = len(context)
            compressed_len = len(compressed)
            ratio = compressed_len / original_len if original_len > 0 else 1.0
            
            logger.info(f"Compressed context: {original_len} → {compressed_len} chars ({ratio:.2%})")
            return compressed

        except Exception as e:
            logger.warning(f"Context compression failed: {e}, using original")
            return context

    def should_compress(self, context: str, max_context_tokens: int = 4000) -> bool:
        """Determine if context should be compressed based on length."""
        # Rough estimate: 1 token ≈ 4 characters
        estimated_tokens = len(context) / 4
        return estimated_tokens > max_context_tokens * 0.8  # Compress if >80% of limit
