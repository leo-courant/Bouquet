"""Query intent classification service for better retrieval strategy selection."""

import re
from typing import Optional

import openai
from loguru import logger

from app.domain.query import QueryType, RetrievalStrategy


class QueryIntentClassifier:
    """Service for classifying query intent and selecting optimal strategies."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
    ) -> None:
        """Initialize query intent classifier."""
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        logger.info("Initialized QueryIntentClassifier")

    async def classify_query(self, query: str) -> dict:
        """Classify query intent and characteristics."""
        
        # Quick heuristic check for very simple queries to avoid LLM calls
        query_lower = query.strip().lower()
        if len(query_lower) < 10:
            # Very short query, likely simple
            return {
                'query_type': 'exploratory',
                'complexity': 'simple',
                'question_type': 'open_ended',
                'entities': [],
                'optimal_strategy': 'community_based',
                'requires_multi_hop': False,
                'requires_aggregation': False,
            }
        
        # Parallel classification
        import asyncio
        
        query_type, complexity, question_type, entities = await asyncio.gather(
            self._classify_query_type(query),
            self._assess_complexity(query),
            self._identify_question_type(query),
            self._extract_query_entities(query),
        )
        
        # Determine optimal retrieval strategy
        optimal_strategy = self._select_retrieval_strategy(
            query_type,
            complexity,
            question_type,
        )
        
        classification = {
            'query_type': query_type,
            'complexity': complexity,
            'question_type': question_type,
            'entities': entities,
            'optimal_strategy': optimal_strategy,
            'requires_multi_hop': complexity in ['high', 'very_high'],
            'requires_aggregation': question_type in ['how_many', 'list'],
        }
        
        logger.info(f"Classified query: type={query_type}, complexity={complexity}, strategy={optimal_strategy}")
        return classification

    async def _classify_query_type(self, query: str) -> str:
        """Classify the type of query."""
        try:
            prompt = f"""Classify this query into ONE category:

Query: {query}

Categories:
- FACTUAL: Looking for specific facts or information
- ANALYTICAL: Requires reasoning, analysis, or comparison
- COMPARATIVE: Comparing two or more entities
- EXPLORATORY: Broad, open-ended discovery
- TEMPORAL: About time, dates, or chronology
- OPINION: Asking for opinions or perspectives
- PROCEDURAL: How-to or step-by-step questions

Respond with ONLY the category name."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at classifying questions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=20,
            )

            result = response.choices[0].message.content.strip().upper()
            
            # Map to QueryType enum
            type_mapping = {
                'FACTUAL': 'factual',
                'ANALYTICAL': 'analytical',
                'COMPARATIVE': 'comparative',
                'EXPLORATORY': 'exploratory',
                'TEMPORAL': 'temporal',
                'OPINION': 'factual',  # Treat as factual
                'PROCEDURAL': 'analytical',
            }
            
            return type_mapping.get(result, 'factual')

        except Exception as e:
            logger.warning(f"Query type classification failed: {e}")
            return 'factual'

    async def _assess_complexity(self, query: str) -> str:
        """Assess query complexity."""
        # Simple heuristics first
        word_count = len(query.split())
        
        # Look for complexity indicators
        complexity_indicators = {
            'simple': ['what is', 'who is', 'when was', 'where is'],
            'medium': ['how does', 'why does', 'explain', 'describe'],
            'high': ['compare', 'analyze', 'relationship between', 'how are', 'what is the difference'],
            'very_high': ['synthesize', 'evaluate', 'multiple', 'complex', 'comprehensive'],
        }
        
        query_lower = query.lower()
        detected_complexity = 'simple'
        
        for complexity, indicators in complexity_indicators.items():
            if any(ind in query_lower for ind in indicators):
                detected_complexity = complexity
        
        # Adjust based on length
        if word_count > 20:
            complexity_levels = ['simple', 'medium', 'high', 'very_high']
            current_idx = complexity_levels.index(detected_complexity)
            detected_complexity = complexity_levels[min(current_idx + 1, 3)]
        
        return detected_complexity

    async def _identify_question_type(self, query: str) -> str:
        """Identify the question type (who, what, when, where, why, how)."""
        query_lower = query.lower().strip()
        
        question_types = {
            'who': r'\bwho\b',
            'what': r'\bwhat\b',
            'when': r'\bwhen\b',
            'where': r'\bwhere\b',
            'why': r'\bwhy\b',
            'how': r'\bhow\b',
            'how_many': r'\bhow many\b|\bhow much\b',
            'which': r'\bwhich\b',
            'list': r'\blist\b|\benumerate\b|\bname all\b',
            'yes_no': r'\bis\b|\bcan\b|\bdoes\b|\bwill\b|\bshould\b',
        }
        
        for q_type, pattern in question_types.items():
            if re.search(pattern, query_lower):
                return q_type
        
        return 'what'  # Default

    async def _extract_query_entities(self, query: str) -> list[str]:
        """Extract named entities from query."""
        try:
            prompt = f"""Extract all named entities (people, places, organizations, concepts) from this query.

Query: {query}

List them one per line. If none found, respond with: NONE"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at named entity recognition."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=100,
            )

            result = response.choices[0].message.content.strip()
            
            if result == "NONE":
                return []
            
            entities = [
                line.strip().strip('-•*').strip()
                for line in result.split('\n')
                if line.strip() and len(line.strip()) > 2
            ]
            
            return entities[:10]  # Max 10 entities

        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            return []

    def _select_retrieval_strategy(
        self,
        query_type: str,
        complexity: str,
        question_type: str,
    ) -> str:
        """Select optimal retrieval strategy based on classification."""
        
        # Rule-based strategy selection
        if query_type == 'temporal':
            return RetrievalStrategy.HYBRID.value
        
        if query_type == 'comparative' or complexity in ['high', 'very_high']:
            return RetrievalStrategy.GRAPH_TRAVERSAL.value
        
        if query_type == 'analytical':
            return RetrievalStrategy.ENTITY_AWARE.value
        
        if query_type == 'exploratory':
            return RetrievalStrategy.COMMUNITY_BASED.value
        
        # Default to adaptive for simple factual queries
        return RetrievalStrategy.ADAPTIVE.value

    async def enhance_query_understanding(
        self,
        query: str,
        classification: dict,
    ) -> dict:
        """Generate enhanced query understanding for better retrieval."""
        try:
            prompt = f"""Enhance understanding of this query for better information retrieval.

Query: {query}
Type: {classification['query_type']}
Complexity: {classification['complexity']}

Provide:
1. KEY_CONCEPTS: Main concepts to search for (comma-separated)
2. SYNONYMS: Alternative terms or synonyms (comma-separated)
3. FOCUS: What's the core information need? (one sentence)

Format:
KEY_CONCEPTS: [concepts]
SYNONYMS: [synonyms]
FOCUS: [one sentence]"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at query understanding."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=150,
            )

            result = response.choices[0].message.content.strip()
            
            # Parse result
            enhancement = {}
            for line in result.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower().replace('_', '_')
                    value = value.strip()
                    enhancement[key] = value
            
            return enhancement

        except Exception as e:
            logger.warning(f"Query enhancement failed: {e}")
            return {}
