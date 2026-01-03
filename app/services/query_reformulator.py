"""Query reformulation and expansion service."""

from typing import Optional

import openai
from loguru import logger


class QueryReformulator:
    """Reformulates and expands queries for better retrieval."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
        enable_reformulation: bool = True,
    ) -> None:
        """Initialize query reformulator."""
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        self.enable_reformulation = enable_reformulation
        logger.info(f"Initialized QueryReformulator (enabled={enable_reformulation})")

    async def reformulate_query(self, query: str) -> list[str]:
        """Generate multiple reformulations of the query.
        
        Returns original query plus reformulations for better coverage.
        """
        if not self.enable_reformulation:
            return [query]
        
        try:
            prompt = f"""Given this user question, generate 2-3 alternative phrasings that maintain the same meaning but use different words. This helps retrieve relevant information that might use different terminology.

Original question: {query}

Generate alternative phrasings, one per line. Be concise and maintain the core intent."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that rephrases questions while maintaining their meaning."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=150,
            )

            content = response.choices[0].message.content or ""
            reformulations = [line.strip() for line in content.split("\n") if line.strip()]
            
            # Always include original query
            all_queries = [query] + reformulations[:3]  # Max 4 total
            
            logger.debug(f"Reformulated query into {len(all_queries)} variations")
            return all_queries

        except Exception as e:
            logger.warning(f"Query reformulation failed: {e}, using original query")
            return [query]

    async def expand_query_with_synonyms(self, query: str) -> str:
        """Expand query with relevant synonyms and related terms."""
        if not self.enable_reformulation:
            return query
        
        try:
            prompt = f"""Add relevant synonyms and related terms to this query to improve search coverage. Keep it concise.

Original: {query}

Expanded query (add 2-3 synonyms or related terms):"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a search query expansion expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=100,
            )

            expanded = response.choices[0].message.content or query
            logger.debug(f"Expanded query: {query} → {expanded}")
            return expanded.strip()

        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")
            return query
