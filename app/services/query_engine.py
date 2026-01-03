"""Query engine for RAG-based question answering."""

from typing import Optional

import openai
from loguru import logger

from app.domain import QueryResponse, SearchResult
from app.repositories import Neo4jRepository
from app.services.embedding_service import EmbeddingService


class QueryEngine:
    """Service for querying the knowledge graph and generating answers."""

    def __init__(
        self,
        repository: Neo4jRepository,
        embedding_service: EmbeddingService,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
        top_k: int = 10,
        rerank_top_k: int = 5,
        max_context_length: int = 8000,
        min_similarity_threshold: float = 0.7,
    ) -> None:
        """Initialize query engine."""
        self.repository = repository
        self.embedding_service = embedding_service
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        self.top_k = top_k
        self.rerank_top_k = rerank_top_k
        self.max_context_length = max_context_length
        self.min_similarity_threshold = min_similarity_threshold
        logger.info(f"Initialized QueryEngine with model: {model}, min_similarity: {min_similarity_threshold}")

    async def search(
        self, query: str, top_k: Optional[int] = None, filters: Optional[dict] = None
    ) -> list[SearchResult]:
        """Semantic search for relevant chunks."""
        if top_k is None:
            top_k = self.top_k

        # Generate query embedding
        query_embedding = await self.embedding_service.generate_embedding(query)

        # Search for similar chunks
        chunk_results = await self.repository.search_similar_chunks(query_embedding, top_k)

        # Convert to SearchResult objects
        search_results = []
        for chunk, score in chunk_results:
            # Get entities for this chunk
            entities = await self.repository.get_entities_for_chunk(chunk.id)
            entity_names = [e.name for e in entities]

            search_result = SearchResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                content=chunk.content,
                score=score,
                metadata=chunk.metadata,
                entities=entity_names,
            )
            search_results.append(search_result)

        logger.info(f"Found {len(search_results)} results for query: {query[:50]}...")
        return search_results

    async def rerank(
        self, query: str, results: list[SearchResult], top_k: Optional[int] = None
    ) -> list[SearchResult]:
        """Re-rank search results using cross-encoder or LLM."""
        if top_k is None:
            top_k = self.rerank_top_k

        # Simple re-ranking: already sorted by similarity score
        # Could be enhanced with cross-encoder models or LLM-based reranking
        reranked = sorted(results, key=lambda x: x.score, reverse=True)[:top_k]

        logger.info(f"Re-ranked to top {len(reranked)} results")
        return reranked

    def _build_context(self, results: list[SearchResult]) -> str:
        """Build context string from search results."""
        context_parts = []
        current_length = 0

        for i, result in enumerate(results, 1):
            chunk_text = f"[Source {i}]\n{result.content}\n"

            # Check if adding this chunk would exceed max length
            if current_length + len(chunk_text) > self.max_context_length:
                break

            context_parts.append(chunk_text)
            current_length += len(chunk_text)

        context = "\n".join(context_parts)
        logger.debug(f"Built context of {len(context)} characters from {len(context_parts)} sources")
        return context

    async def query(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[dict] = None,
        max_context_length: Optional[int] = None,
    ) -> QueryResponse:
        """Query the knowledge graph and generate an answer."""
        logger.info(f"Processing query: {query}")

        # Override defaults if provided
        if max_context_length:
            self.max_context_length = max_context_length

        # Search for relevant chunks
        search_results = await self.search(query, top_k, filters)

        if not search_results:
            return QueryResponse(
                answer="I couldn't find any relevant information to answer your question.",
                sources=[],
                metadata={"query": query, "total_sources": 0, "reason": "no_results"},
            )

        # Check if results meet minimum similarity threshold
        high_quality_results = [r for r in search_results if r.score >= self.min_similarity_threshold]
        
        if not high_quality_results:
            logger.warning(f"No results above similarity threshold {self.min_similarity_threshold}")
            # If threshold is 0, use all results; otherwise return insufficient info
            if self.min_similarity_threshold > 0:
                return QueryResponse(
                    answer="I don't have sufficient information to answer this question accurately. The available information is not relevant enough to provide a reliable answer.",
                    sources=[],
                    metadata={
                        "query": query,
                        "total_sources": len(search_results),
                        "reason": "below_similarity_threshold",
                        "max_similarity": max(r.score for r in search_results) if search_results else 0.0,
                    },
                )
            else:
                high_quality_results = search_results

        # Re-rank results
        reranked_results = await self.rerank(query, high_quality_results)

        # Build context from top results
        context = self._build_context(reranked_results)

        # Generate answer using LLM
        answer = await self._generate_answer(query, context)
        
        # Validate answer length
        word_count = len(answer.split())
        if word_count < 10:
            logger.warning(f"Answer too short ({word_count} words), may be incomplete")
            if "don't" in answer.lower() or "cannot" in answer.lower() or "insufficient" in answer.lower():
                # It's a legitimate "I don't know" response
                pass
            else:
                logger.error("Suspiciously short answer that's not a proper abstention")

        response = QueryResponse(
            answer=answer,
            sources=reranked_results,
            metadata={
                "query": query,
                "total_sources": len(reranked_results),
                "context_length": len(context),
                "answer_word_count": word_count,
            },
        )

        logger.info(f"Generated answer with {len(reranked_results)} sources")
        return response

    async def _generate_answer(self, query: str, context: str) -> str:
        """Generate answer using LLM with retrieved context."""
        system_prompt = """You are a helpful AI assistant that answers questions based on the provided context.

Guidelines:
- Answer the question using ONLY information from the provided context
- If you don't have sufficient information to answer the question, say "I don't have sufficient information to answer this question."
- Be concise but comprehensive
- CRITICAL: Every factual claim MUST cite a source using [Source N] format
- Example: "AI transforms technology [Source 1]. Machine learning enables learning from data [Source 2]."
- If multiple sources provide relevant information, synthesize them
- Do not make up information not present in the context
- Be precise and factual - this is more important than being creative
"""

        user_prompt = f"""Context:
{context}

Question: {query}

Answer:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=1000,
            )

            answer = response.choices[0].message.content.strip()
            logger.debug(f"Generated answer: {answer[:100]}...")
            return answer

        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return "I encountered an error while generating the answer. Please try again."

    async def get_related_entities(self, entity_name: str, max_hops: int = 2) -> list[dict]:
        """Get entities related to a given entity through graph traversal."""
        query = """
        MATCH (e:Entity {name: $name})
        CALL apoc.path.subgraphNodes(e, {
            relationshipFilter: 'RELATED',
            maxLevel: $max_hops
        })
        YIELD node
        RETURN DISTINCT node.name as name, node.entity_type as type, node.description as description
        LIMIT 20
        """

        related = []
        async with self.repository._driver.session(
            database=self.repository.database
        ) as session:
            try:
                result = await session.run(
                    query, {"name": entity_name, "max_hops": max_hops}
                )
                async for record in result:
                    related.append({
                        "name": record["name"],
                        "type": record["type"],
                        "description": record.get("description"),
                    })
            except Exception as e:
                logger.warning(f"APOC not available or error: {e}")
                # Fallback to simple query
                simple_query = """
                MATCH (e1:Entity {name: $name})-[r:RELATED*1..2]-(e2:Entity)
                RETURN DISTINCT e2.name as name, e2.entity_type as type, e2.description as description
                LIMIT 20
                """
                result = await session.run(simple_query, {"name": entity_name})
                async for record in result:
                    related.append({
                        "name": record["name"],
                        "type": record["type"],
                        "description": record.get("description"),
                    })

        logger.info(f"Found {len(related)} related entities for: {entity_name}")
        return related
