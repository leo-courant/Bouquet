"""Query decomposition and routing service."""

import json
from typing import Optional

import openai
from loguru import logger

from app.domain.query import QueryType, SubQuery


class QueryDecomposer:
    """Service for decomposing complex queries into sub-queries."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
        max_subqueries: int = 3,
    ) -> None:
        """Initialize query decomposer."""
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        self.max_subqueries = max_subqueries
        logger.info(f"Initialized QueryDecomposer with model: {model}")

    async def classify_query_type(self, query: str) -> QueryType:
        """Classify the query type."""
        system_prompt = """Classify the query into one of these types:
- factual: Simple fact lookup (What is X? Who is Y?)
- analytical: Requires reasoning and analysis (Why? How? What causes?)
- comparative: Compares entities (What's the difference? Compare X and Y)
- exploratory: Broad discovery (Tell me about X, Overview of Y)
- temporal: Time-based queries (When? What happened before/after?)

Return only the type name."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                temperature=0.0,
                max_tokens=50,
            )
            
            result = response.choices[0].message.content.strip().lower()
            
            # Map to QueryType
            for qt in QueryType:
                if qt.value in result:
                    return qt
            
            return QueryType.FACTUAL  # Default
            
        except Exception as e:
            logger.error(f"Error classifying query: {e}")
            return QueryType.FACTUAL

    async def decompose_query(self, query: str) -> list[SubQuery]:
        """Decompose a complex query into sub-queries."""
        # First check if decomposition is needed
        if len(query.split()) < 10:  # Simple queries don't need decomposition
            query_type = await self.classify_query_type(query)
            return [SubQuery(query=query, query_type=query_type, priority=1)]

        system_prompt = f"""You are a query decomposition expert. Break down complex queries into {self.max_subqueries} or fewer simpler sub-queries.

For each sub-query, provide:
1. The sub-query text
2. Type: factual, analytical, comparative, exploratory, or temporal
3. Dependencies: indices of other sub-queries this depends on (empty if none)
4. Priority: 1-3 (1=highest)

Return a JSON array of sub-queries. If the query is simple, return just one sub-query.

Example:
Query: "Compare the causes and effects of World War 1 and World War 2"
Output:
[
  {{"query": "What were the causes of World War 1?", "query_type": "factual", "dependencies": [], "priority": 1}},
  {{"query": "What were the causes of World War 2?", "query_type": "factual", "dependencies": [], "priority": 1}},
  {{"query": "What were the effects of World War 1?", "query_type": "factual", "dependencies": [0], "priority": 2}},
  {{"query": "What were the effects of World War 2?", "query_type": "factual", "dependencies": [1], "priority": 2}},
  {{"query": "Compare the causes of WW1 and WW2", "query_type": "comparative", "dependencies": [0, 1], "priority": 3}}
]"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Query: {query}"},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            
            content = response.choices[0].message.content
            data = json.loads(content)
            
            # Handle both array and object with 'subqueries' key
            if isinstance(data, dict) and 'subqueries' in data:
                subqueries_data = data['subqueries']
            elif isinstance(data, list):
                subqueries_data = data
            else:
                subqueries_data = [data]
            
            subqueries = []
            for sq_data in subqueries_data[:self.max_subqueries]:
                try:
                    query_type = QueryType(sq_data.get('query_type', 'factual'))
                except ValueError:
                    query_type = QueryType.FACTUAL
                
                subquery = SubQuery(
                    query=sq_data['query'],
                    query_type=query_type,
                    dependencies=sq_data.get('dependencies', []),
                    priority=sq_data.get('priority', 1),
                )
                subqueries.append(subquery)
            
            logger.info(f"Decomposed query into {len(subqueries)} sub-queries")
            return subqueries
            
        except Exception as e:
            logger.error(f"Error decomposing query: {e}")
            # Fallback: return original query
            query_type = await self.classify_query_type(query)
            return [SubQuery(query=query, query_type=query_type, priority=1)]

    def should_decompose(self, query: str) -> bool:
        """Determine if a query should be decomposed."""
        # Heuristics for queries that benefit from decomposition
        decomposition_keywords = [
            'compare', 'contrast', 'difference', 'versus', 'vs',
            'both', 'and', 'causes and effects', 'before and after',
            'relationship between', 'how does', 'why does',
        ]
        
        query_lower = query.lower()
        
        # Check for keywords
        has_keywords = any(keyword in query_lower for keyword in decomposition_keywords)
        
        # Check for complexity (multiple clauses)
        has_complexity = len(query.split()) > 15 or query.count(',') > 1
        
        return has_keywords or has_complexity
