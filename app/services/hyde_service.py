"""HyDE (Hypothetical Document Embeddings) for improved retrieval."""

from typing import Optional

import openai
from loguru import logger


class HyDEService:
    """Generates hypothetical documents to improve retrieval quality."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
        enable_hyde: bool = True,
    ) -> None:
        """Initialize HyDE service."""
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        self.enable_hyde = enable_hyde
        logger.info(f"Initialized HyDE service (enabled={enable_hyde})")

    async def generate_hypothetical_document(
        self,
        query: str,
        num_documents: int = 1,
    ) -> list[str]:
        """Generate hypothetical documents that would answer the query.
        
        HyDE improves retrieval by embedding what a good answer would look like,
        rather than the question itself.
        """
        if not self.enable_hyde:
            return [query]
        
        try:
            prompt = f"""Generate a concise, informative passage that would directly answer this question:

Question: {query}

Write a single paragraph (2-4 sentences) that provides a clear, factual answer. Focus on key information that would be in a relevant document."""

            if num_documents > 1:
                prompt += f"\n\nGenerate {num_documents} different variations, separated by '---'."

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that generates concise, factual passages."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,  # Some variation for multiple docs
                max_tokens=200,
            )

            content = response.choices[0].message.content or ""
            
            if num_documents > 1:
                documents = [doc.strip() for doc in content.split("---")]
            else:
                documents = [content.strip()]
            
            logger.debug(f"Generated {len(documents)} hypothetical documents for: {query[:50]}...")
            return documents

        except Exception as e:
            logger.warning(f"HyDE generation failed: {e}, falling back to original query")
            return [query]

    async def generate_hypothetical_answer(self, query: str) -> str:
        """Generate a single hypothetical answer (simpler interface)."""
        docs = await self.generate_hypothetical_document(query, num_documents=1)
        return docs[0] if docs else query
