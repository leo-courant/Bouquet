"""Citation extraction service for precise source attribution."""

import re
from typing import Optional

import openai
from loguru import logger

from app.domain import SearchResult


class CitationExtractor:
    """Service for extracting and formatting precise citations."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
        max_citation_length: int = 200,
    ) -> None:
        """Initialize citation extractor."""
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        self.max_citation_length = max_citation_length
        logger.info("Initialized CitationExtractor")

    async def extract_supporting_quotes(
        self,
        answer: str,
        sources: list[SearchResult],
    ) -> dict[int, list[str]]:
        """Extract specific quotes from sources that support the answer."""
        
        citations = {}
        
        for idx, source in enumerate(sources[:5], 1):  # Top 5 sources
            quotes = await self._find_supporting_quotes(
                answer,
                source.content,
                source_id=idx,
            )
            
            if quotes:
                citations[idx] = quotes
        
        logger.info(f"Extracted citations from {len(citations)} sources")
        return citations

    async def _find_supporting_quotes(
        self,
        answer: str,
        source_content: str,
        source_id: int,
    ) -> list[str]:
        """Find specific quotes from source that support the answer."""
        try:
            prompt = f"""Extract the specific sentences or phrases from the SOURCE that directly support claims in the ANSWER.

ANSWER:
{answer}

SOURCE:
{source_content}

Instructions:
- Extract EXACT quotes (word-for-word) from the source
- Only include text that directly supports claims in the answer
- Keep quotes concise (under {self.max_citation_length} chars each)
- Return 1-3 most relevant quotes
- Format: One quote per line, enclosed in quotes

If no direct support found, respond with: NONE"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at extracting precise citations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=300,
            )

            result = response.choices[0].message.content.strip()
            
            if result == "NONE":
                return []
            
            # Parse quotes
            quotes = []
            for line in result.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                # Remove quote marks if present
                line = line.strip('"').strip("'").strip()
                
                if line and len(line) > 20:  # Minimum quote length
                    quotes.append(line[:self.max_citation_length])
            
            return quotes[:3]  # Max 3 quotes per source

        except Exception as e:
            logger.warning(f"Quote extraction failed for source {source_id}: {e}")
            return []

    async def generate_cited_answer(
        self,
        answer: str,
        citations: dict[int, list[str]],
        sources: list[SearchResult],
    ) -> str:
        """Generate answer with inline citations."""
        
        if not citations:
            return answer
        
        try:
            # Build citation reference text
            citation_text = "\n\n**Sources:**\n"
            
            for source_id, quotes in citations.items():
                if source_id <= len(sources):
                    source = sources[source_id - 1]
                    citation_text += f"\n[{source_id}] "
                    
                    # Add document reference if available
                    if source.metadata and 'filename' in source.metadata:
                        citation_text += f"From {source.metadata['filename']}: "
                    
                    # Add quotes
                    for i, quote in enumerate(quotes):
                        if i > 0:
                            citation_text += " ... "
                        citation_text += f'"{quote}"'
            
            # Combine answer with citations
            cited_answer = f"{answer}\n{citation_text}"
            
            return cited_answer

        except Exception as e:
            logger.error(f"Failed to generate cited answer: {e}")
            return answer

    def add_inline_citations(
        self,
        answer: str,
        citations: dict[int, list[str]],
    ) -> str:
        """Add inline citation markers to answer text."""
        # This is a simple version - could be enhanced with NLP matching
        
        modified_answer = answer
        
        # Try to match sentences in answer to citations
        sentences = re.split(r'(?<=[.!?])\s+', answer)
        
        # For now, just append citation numbers at the end of sentences
        # A more sophisticated approach would use semantic matching
        
        if citations:
            source_nums = sorted(citations.keys())
            citation_marker = " [" + ", ".join(map(str, source_nums)) + "]"
            
            # Add to end of answer if not already present
            if not re.search(r'\[\d+\]', modified_answer):
                modified_answer = modified_answer.rstrip() + citation_marker
        
        return modified_answer

    async def verify_citation_accuracy(
        self,
        claim: str,
        citation: str,
    ) -> tuple[bool, float]:
        """Verify if a citation actually supports a claim."""
        try:
            prompt = f"""Does this citation support this claim?

CLAIM: {claim}

CITATION: {citation}

Rate support level (0.0 to 1.0):
- 1.0: Directly supports
- 0.7-0.9: Partially supports
- 0.4-0.6: Weakly related
- 0.0-0.3: Does not support

Respond with ONLY a number."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a fact-checker. Respond with only a number."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=10,
            )

            score = float(response.choices[0].message.content.strip())
            is_supported = score >= 0.6
            
            return is_supported, score

        except Exception as e:
            logger.warning(f"Citation verification failed: {e}")
            return True, 0.5
