"""Comparative analysis service for structured comparisons."""

from typing import Optional

import openai
from loguru import logger

from app.domain import SearchResult


class ComparativeAnalyzer:
    """Service for performing structured comparative analysis."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
    ) -> None:
        """Initialize comparative analyzer."""
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        logger.info("Initialized ComparativeAnalyzer")

    async def analyze_comparison_query(
        self,
        query: str,
        sources: list[SearchResult],
    ) -> dict:
        """
        Detect if query is asking for comparison and extract comparison targets.
        
        Examples:
        - "Compare X and Y"
        - "What's the difference between X and Y"
        - "X vs Y"
        - "How does X differ from Y"
        """
        
        comparison_keywords = [
            'compare', 'contrast', 'difference', 'differ', 'vs', 'versus',
            'between', 'distinguish', 'similar', 'alike', 'unlike'
        ]
        
        query_lower = query.lower()
        is_comparison = any(keyword in query_lower for keyword in comparison_keywords)
        
        if not is_comparison:
            return {
                'is_comparison': False,
                'targets': [],
            }
        
        # Extract comparison targets using LLM
        targets = await self._extract_comparison_targets(query)
        
        return {
            'is_comparison': True,
            'targets': targets,
            'query_type': self._classify_comparison_type(query_lower),
        }

    async def _extract_comparison_targets(self, query: str) -> list[str]:
        """Extract the entities/concepts being compared."""
        
        prompt = f"""Extract the two main things being compared in this question.

Question: {query}

Respond with just the two items, one per line:
Item 1:
Item 2:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You extract comparison targets from questions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=100,
            )

            result = response.choices[0].message.content.strip()
            
            targets = []
            for line in result.split('\n'):
                if ':' in line:
                    target = line.split(':', 1)[1].strip()
                    if target:
                        targets.append(target)
            
            return targets[:2]  # Max 2 targets
            
        except Exception as e:
            logger.error(f"Failed to extract comparison targets: {e}")
            return []

    def _classify_comparison_type(self, query_lower: str) -> str:
        """Classify the type of comparison being requested."""
        
        if any(word in query_lower for word in ['similar', 'alike', 'common']):
            return 'similarity'
        elif any(word in query_lower for word in ['differ', 'difference', 'unlike', 'contrast']):
            return 'difference'
        elif 'vs' in query_lower or 'versus' in query_lower:
            return 'versus'
        else:
            return 'general_comparison'

    async def generate_structured_comparison(
        self,
        query: str,
        target1: str,
        target2: str,
        sources: list[SearchResult],
    ) -> dict:
        """
        Generate a structured comparison between two targets.
        
        Returns comparison with clear categories: similarities, differences, pros/cons, etc.
        """
        
        # Split sources by relevance to each target
        target1_sources = []
        target2_sources = []
        shared_sources = []
        
        for source in sources:
            content_lower = source.content.lower()
            has_target1 = target1.lower() in content_lower
            has_target2 = target2.lower() in content_lower
            
            if has_target1 and has_target2:
                shared_sources.append(source)
            elif has_target1:
                target1_sources.append(source)
            elif has_target2:
                target2_sources.append(source)
            else:
                # Add to both if neither explicitly mentioned (general context)
                shared_sources.append(source)
        
        # Build context
        context_parts = []
        
        if shared_sources:
            context_parts.append(f"=== Information about both {target1} and {target2} ===")
            for i, src in enumerate(shared_sources[:3], 1):
                context_parts.append(f"[Source {i}] {src.content[:300]}")
        
        if target1_sources:
            context_parts.append(f"\n=== Specific information about {target1} ===")
            for i, src in enumerate(target1_sources[:3], len(shared_sources) + 1):
                context_parts.append(f"[Source {i}] {src.content[:300]}")
        
        if target2_sources:
            context_parts.append(f"\n=== Specific information about {target2} ===")
            for i, src in enumerate(target2_sources[:3], len(shared_sources) + len(target1_sources) + 1):
                context_parts.append(f"[Source {i}] {src.content[:300]}")
        
        context = "\n\n".join(context_parts)
        
        # Generate comparison
        comparison = await self._generate_comparison(
            query, target1, target2, context
        )
        
        return {
            'comparison': comparison,
            'target1': target1,
            'target2': target2,
            'target1_sources': len(target1_sources),
            'target2_sources': len(target2_sources),
            'shared_sources': len(shared_sources),
        }

    async def _generate_comparison(
        self,
        query: str,
        target1: str,
        target2: str,
        context: str,
    ) -> str:
        """Generate the actual comparison text."""
        
        prompt = f"""Compare and contrast {target1} and {target2} based on the provided information.

Context:
{context}

Question: {query}

Provide a structured comparison:

**OVERVIEW**
[Brief summary of both items]

**SIMILARITIES**
- [Key points where {target1} and {target2} are similar]
- Cite sources with [Source N]

**DIFFERENCES**
- [Key points where {target1} and {target2} differ]
- Be specific and cite sources with [Source N]

**{target1.upper()} - UNIQUE CHARACTERISTICS**
- [What's unique or distinctive about {target1}]
- Cite sources

**{target2.upper()} - UNIQUE CHARACTERISTICS**
- [What's unique or distinctive about {target2}]
- Cite sources

**SUMMARY**
[Brief conclusion synthesizing the comparison]

Answer:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at structured comparative analysis. Always cite sources."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=1000,
            )

            comparison = response.choices[0].message.content.strip()
            
            logger.info(f"Generated structured comparison: {target1} vs {target2}")
            
            return comparison
            
        except Exception as e:
            logger.error(f"Failed to generate comparison: {e}")
            return f"Error generating comparison: {str(e)}"

    async def generate_multi_aspect_comparison(
        self,
        query: str,
        targets: list[str],
        sources: list[SearchResult],
        aspects: Optional[list[str]] = None,
    ) -> dict:
        """
        Generate comparison across multiple aspects/dimensions.
        
        Useful for complex comparisons like "Compare X, Y, and Z in terms of A, B, and C"
        """
        
        if aspects is None:
            # Extract aspects from query or use defaults
            aspects = await self._extract_comparison_aspects(query)
        
        if not aspects:
            aspects = ['characteristics', 'advantages', 'limitations']
        
        # Build comparison table
        comparison_table = {}
        
        for aspect in aspects:
            comparison_table[aspect] = {}
            
            for target in targets:
                info = await self._extract_aspect_info(
                    target, aspect, sources
                )
                comparison_table[aspect][target] = info
        
        # Format as structured output
        formatted = self._format_comparison_table(comparison_table, targets, aspects)
        
        return {
            'comparison_table': comparison_table,
            'formatted': formatted,
            'targets': targets,
            'aspects': aspects,
        }

    async def _extract_comparison_aspects(self, query: str) -> list[str]:
        """Extract comparison aspects/dimensions from query."""
        
        prompt = f"""What aspects or dimensions should be compared in this question?

Question: {query}

List 2-4 comparison aspects (e.g., "cost", "performance", "ease of use"):"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You identify comparison dimensions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=100,
            )

            result = response.choices[0].message.content.strip()
            
            # Parse aspects
            aspects = []
            for line in result.split('\n'):
                line = line.strip('- •').strip()
                if line and len(line) < 50:  # Reasonable aspect name
                    aspects.append(line.lower())
            
            return aspects[:4]  # Max 4 aspects
            
        except Exception as e:
            logger.error(f"Failed to extract aspects: {e}")
            return []

    async def _extract_aspect_info(
        self,
        target: str,
        aspect: str,
        sources: list[SearchResult],
    ) -> str:
        """Extract information about a specific aspect of a target."""
        
        # Find relevant sources
        relevant_context = []
        for src in sources:
            if target.lower() in src.content.lower():
                relevant_context.append(src.content[:200])
            if len(relevant_context) >= 3:
                break
        
        if not relevant_context:
            return "No information available"
        
        context = "\n\n".join(relevant_context)
        
        prompt = f"""What information is provided about {aspect} for {target}?

Context:
{context}

Provide a brief (1-2 sentences) answer focusing on {aspect}:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You extract specific aspect information."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=100,
            )

            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Failed to extract aspect info: {e}")
            return "Error extracting information"

    def _format_comparison_table(
        self,
        comparison_table: dict,
        targets: list[str],
        aspects: list[str],
    ) -> str:
        """Format comparison table as readable text."""
        
        lines = ["## COMPARATIVE ANALYSIS\n"]
        
        for aspect in aspects:
            lines.append(f"### {aspect.upper()}")
            
            for target in targets:
                info = comparison_table[aspect].get(target, "N/A")
                lines.append(f"**{target}**: {info}")
            
            lines.append("")
        
        return "\n".join(lines)
