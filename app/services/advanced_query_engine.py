"""Advanced query engine with all state-of-the-art RAG features."""

from typing import Optional

import openai
from loguru import logger

from app.domain import Chunk, QueryResponse, SearchResult
from app.domain.query import QueryType, RetrievalStrategy, SubQuery
from app.repositories import Neo4jRepository
from app.services.embedding_service import EmbeddingService
from app.services.entity_disambiguator import EntityDisambiguator
from app.services.feedback_service import FeedbackService
from app.services.hybrid_search import HybridSearchEngine
from app.services.query_decomposer import QueryDecomposer
from app.services.reranker import RerankerService
from app.services.hyde_service import HyDEService
from app.services.query_reformulator import QueryReformulator
from app.services.context_compressor import ContextCompressor
from app.services.cache_service import QueryCache


class AdvancedQueryEngine:
    """Advanced query engine with multi-strategy retrieval and reasoning."""

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
        enable_reranking: bool = True,
        enable_entity_expansion: bool = True,
        enable_query_decomposition: bool = True,
        enable_feedback: bool = True,
        hyde_service: Optional[HyDEService] = None,
        query_reformulator: Optional[QueryReformulator] = None,
        context_compressor: Optional[ContextCompressor] = None,
        query_cache: Optional[QueryCache] = None,
    ) -> None:
        """Initialize advanced query engine."""
        self.repository = repository
        self.embedding_service = embedding_service
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
        self.top_k = top_k
        self.rerank_top_k = rerank_top_k
        self.min_similarity_threshold = min_similarity_threshold
        self.max_context_length = max_context_length
        
        # Initialize advanced components
        self.hybrid_search = HybridSearchEngine()
        
        self.reranker = None
        if enable_reranking:
            self.reranker = RerankerService()
        
        self.query_decomposer = None
        if enable_query_decomposition:
            self.query_decomposer = QueryDecomposer(api_key=api_key, model=model)
        
        self.entity_disambiguator = EntityDisambiguator(api_key=api_key, model=model)
        
        self.feedback_service = None
        if enable_feedback:
            self.feedback_service = FeedbackService()
        
        # New services for enhanced RAG
        self.hyde_service = hyde_service
        self.query_reformulator = query_reformulator
        self.context_compressor = context_compressor
        self.query_cache = query_cache
        
        self.enable_entity_expansion = enable_entity_expansion
        
        logger.info(f"Initialized AdvancedQueryEngine with model: {model}")
        if hyde_service:
            logger.info("HyDE service enabled for improved retrieval")
        if query_reformulator:
            logger.info("Query reformulation enabled for better coverage")
        if context_compressor:
            logger.info("Context compression enabled for efficiency")
        if query_cache:
            logger.info("Query caching enabled for speed")

    async def query(
        self,
        query: str,
        top_k: Optional[int] = None,
        strategy: RetrievalStrategy = RetrievalStrategy.ADAPTIVE,
        use_reranking: bool = True,
        use_entity_expansion: bool = True,
        use_community_context: bool = True,
        max_hops: int = 2,
        enable_feedback: bool = True,
    ) -> QueryResponse:
        """Execute advanced query with multiple strategies."""
        logger.info(f"Processing advanced query: {query}")
        
        if top_k is None:
            top_k = self.top_k
        
        # Check query cache first
        if self.query_cache:
            cache_key = f"query:{query}:{top_k}:{strategy.value}"
            cached_response = await self.query_cache.get(cache_key)
            if cached_response:
                logger.info(f"Cache hit for query: {query[:50]}...")
                return cached_response
        
        # Step 1: Query reformulation (if enabled)
        query_variants = [query]
        if self.query_reformulator:
            query_variants = await self.query_reformulator.reformulate_query(query)
            logger.info(f"Generated {len(query_variants)} query variants")
        
        # Step 2: Query decomposition (if complex)
        subqueries = [SubQuery(query=query, query_type=QueryType.FACTUAL, priority=1)]
        if self.query_decomposer and self.query_decomposer.should_decompose(query):
            subqueries = await self.query_decomposer.decompose_query(query)
            logger.info(f"Decomposed into {len(subqueries)} sub-queries")
        
        # Step 3: Retrieve for each sub-query and query variant
        all_results = []
        for subquery in subqueries:
            for query_variant in query_variants:
                # Use HyDE if enabled
                search_query = query_variant
                if self.hyde_service:
                    hyde_doc = await self.hyde_service.generate_hypothetical_document(query_variant)
                    if hyde_doc != query_variant:  # HyDE generated something different
                        search_query = hyde_doc
                        logger.debug(f"Using HyDE document for search: {hyde_doc[:100]}...")
                
                results = await self._retrieve(
                    search_query,
                    top_k,
                    strategy,
                    use_entity_expansion,
                    use_community_context,
                    max_hops,
                )
                all_results.extend(results)
        
        # Deduplicate results
        seen_chunks = set()
        unique_results = []
        for result in all_results:
            if result.chunk_id not in seen_chunks:
                seen_chunks.add(result.chunk_id)
                unique_results.append(result)
        
        if not unique_results:
            empty_response = QueryResponse(
                answer="I couldn't find any relevant information to answer your question.",
                sources=[],
                metadata={"query": query, "total_sources": 0, "reason": "no_results"},
            )
            # Cache empty response too
            if self.query_cache:
                await self.query_cache.set(cache_key, empty_response)
            return empty_response
        
        # Check similarity threshold
        high_quality_results = [r for r in unique_results if r.score >= self.min_similarity_threshold]
        
        if not high_quality_results:
            logger.warning(f"No results above similarity threshold {self.min_similarity_threshold}")
            # If threshold is 0, use all results; otherwise return insufficient info
            if self.min_similarity_threshold > 0:
                low_quality_response = QueryResponse(
                    answer="I don't have sufficient information to answer this question accurately. The available information is not relevant enough to provide a reliable answer.",
                    sources=[],
                    metadata={
                        "query": query,
                        "total_sources": len(unique_results),
                        "reason": "below_similarity_threshold",
                        "max_similarity": max(r.score for r in unique_results) if unique_results else 0.0,
                    },
                )
                if self.query_cache:
                    await self.query_cache.set(cache_key, low_quality_response)
                return low_quality_response
            else:
                high_quality_results = unique_results
        
        unique_results = high_quality_results
        
        # Step 4: Reranking
        if use_reranking and self.reranker:
            unique_results = self.reranker.rerank_search_results(
                query, unique_results, top_k=self.rerank_top_k
            )
        
        # Step 5: Apply feedback scores
        if enable_feedback and self.feedback_service:
            # Convert to tuple format for feedback
            results_tuples = [(self._result_to_chunk(r), r.rerank_score or r.score) for r in unique_results]
            adjusted = self.feedback_service.apply_feedback_to_scores(results_tuples)
            
            # Update results with adjusted scores
            for i, (chunk, adj_score) in enumerate(adjusted):
                if i < len(unique_results):
                    unique_results[i].score = adj_score
        
        # Step 6: Build context and compress if needed
        context = self._build_context(unique_results)
        
        # Compress context if it's too long and compressor is available
        if self.context_compressor and len(context) > self.max_context_length:
            logger.info(f"Compressing context from {len(context)} characters")
            compressed = await self.context_compressor.compress_context(
                context, query, max_tokens=self.max_context_length // 4
            )
            if compressed:
                context = compressed
                logger.info(f"Compressed to {len(context)} characters")
        
        # Step 7: Generate answer
        answer = await self._generate_answer(query, context, subqueries)
        
        # Validate answer length
        word_count = len(answer.split())
        if word_count < 10:
            logger.warning(f"Answer too short ({word_count} words), may be incomplete")
            if "don't" in answer.lower() or "cannot" in answer.lower() or "insufficient" in answer.lower():
                # It's a legitimate "I don't know" response
                pass
            else:
                logger.error("Suspiciously short answer that's not a proper abstention")
        
        # Step 8: Extract entities for metadata
        query_type = subqueries[0].query_type if subqueries else QueryType.FACTUAL
        
        response = QueryResponse(
            answer=answer,
            sources=unique_results[:self.rerank_top_k],
            metadata={
                "query": query,
                "total_sources": len(unique_results),
                "answer_word_count": word_count,
                "context_length": len(context),
                "strategy": strategy.value,
                "query_variants": len(query_variants) if len(query_variants) > 1 else None,
                "hyde_used": self.hyde_service is not None,
                "compressed": self.context_compressor is not None and len(context) < self.max_context_length,
            },
            query_type=query_type,
            decomposed_queries=[sq.query for sq in subqueries] if len(subqueries) > 1 else [],
        )
        
        # Cache the response
        if self.query_cache:
            await self.query_cache.set(cache_key, response)
        
        logger.info(f"Generated answer with {len(unique_results)} sources")
        return response

    async def _retrieve(
        self,
        query: str,
        top_k: int,
        strategy: RetrievalStrategy,
        use_entity_expansion: bool,
        use_community_context: bool,
        max_hops: int,
    ) -> list[SearchResult]:
        """Retrieve chunks using specified strategy."""
        
        # Auto-select strategy if adaptive
        if strategy == RetrievalStrategy.ADAPTIVE:
            strategy = await self._select_strategy(query)
        
        results = []
        
        if strategy == RetrievalStrategy.VECTOR_ONLY:
            results = await self._vector_search(query, top_k)
        
        elif strategy == RetrievalStrategy.HYBRID:
            results = await self._hybrid_search(query, top_k)
        
        elif strategy == RetrievalStrategy.ENTITY_AWARE:
            results = await self._entity_aware_search(query, top_k, max_hops)
        
        elif strategy == RetrievalStrategy.GRAPH_TRAVERSAL:
            results = await self._graph_traversal_search(query, top_k, max_hops)
        
        elif strategy == RetrievalStrategy.SEMANTIC_RELATIONSHIP:
            results = await self._semantic_relationship_search(query, top_k)
        
        elif strategy == RetrievalStrategy.COMMUNITY_BASED:
            results = await self._community_based_search(query, top_k)
        
        logger.info(f"Retrieved {len(results)} results using strategy: {strategy.value}")
        return results

    async def _select_strategy(self, query: str) -> RetrievalStrategy:
        """Auto-select best retrieval strategy based on query."""
        # Simple heuristic-based selection
        query_lower = query.lower()
        
        # Entity-heavy queries
        if any(word in query_lower for word in ['who', 'what is', 'define', 'about']):
            return RetrievalStrategy.ENTITY_AWARE
        
        # Relationship queries
        if any(word in query_lower for word in ['relate', 'connect', 'between', 'link']):
            return RetrievalStrategy.GRAPH_TRAVERSAL
        
        # Broad queries
        if any(word in query_lower for word in ['overview', 'summary', 'tell me about']):
            return RetrievalStrategy.COMMUNITY_BASED
        
        # Default to hybrid
        return RetrievalStrategy.HYBRID

    async def _vector_search(self, query: str, top_k: int) -> list[SearchResult]:
        """Pure vector similarity search."""
        query_embedding = await self.embedding_service.generate_embedding(query)
        
        # Try HNSW index first
        try:
            chunk_results = await self.repository.search_with_vector_index(query_embedding, top_k)
        except Exception:
            chunk_results = await self.repository.search_similar_chunks(query_embedding, top_k)
        
        return await self._chunks_to_results(chunk_results, vector_only=True)

    async def _hybrid_search(self, query: str, top_k: int) -> list[SearchResult]:
        """Hybrid vector + BM25 search."""
        # Vector search
        query_embedding = await self.embedding_service.generate_embedding(query)
        vector_results = await self.repository.search_similar_chunks(query_embedding, top_k * 2)
        
        # BM25 search - need to build index
        # For now, use fulltext search as alternative
        bm25_chunks = await self.repository.fulltext_search_chunks(query, top_k)
        bm25_results = [(i, 1.0) for i in range(len(bm25_chunks))]
        
        # Build BM25 index with all chunks
        self.hybrid_search.indexed_chunks = bm25_chunks
        
        # Combine scores
        combined = self.hybrid_search.reciprocal_rank_fusion(vector_results, bm25_results)
        
        results = []
        for chunk, score in combined[:top_k]:
            entities = await self.repository.get_entities_for_chunk(chunk.id)
            result = SearchResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                content=chunk.content,
                score=score,
                metadata=chunk.metadata,
                entities=[e.name for e in entities],
                vector_score=dict(vector_results).get(chunk, {1: 0.0})[1] if isinstance(vector_results, list) else 0.0,
            )
            results.append(result)
        
        return results

    async def _entity_aware_search(
        self, query: str, top_k: int, max_hops: int
    ) -> list[SearchResult]:
        """Search with entity expansion."""
        # First get base results
        base_results = await self._vector_search(query, top_k // 2)
        
        # Extract entities from query
        query_entities = await self._extract_query_entities(query)
        
        # Find chunks mentioning these entities
        if query_entities:
            entity_chunks = await self.repository.get_chunks_by_entities(
                [e['name'] for e in query_entities], top_k // 2
            )
            
            # Convert to results
            for chunk in entity_chunks:
                entities = await self.repository.get_entities_for_chunk(chunk.id)
                result = SearchResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    score=0.8,  # Fixed score for entity matches
                    metadata=chunk.metadata,
                    entities=[e.name for e in entities],
                    entity_overlap_score=1.0,
                )
                base_results.append(result)
        
        # Deduplicate
        seen = set()
        unique = []
        for r in base_results:
            if r.chunk_id not in seen:
                seen.add(r.chunk_id)
                unique.append(r)
        
        return unique[:top_k]

    async def _graph_traversal_search(
        self, query: str, top_k: int, max_hops: int
    ) -> list[SearchResult]:
        """Multi-hop graph traversal search using semantic chunk relationships."""
        # Get initial results
        initial_results = await self._vector_search(query, top_k // 3)
        
        all_results = list(initial_results)
        
        # For each result, traverse graph using BOTH entity links AND semantic relationships
        for result in initial_results[:3]:  # Traverse from top 3
            # Get related chunks via semantic relationships (ELABORATES, SUPPORTS, etc.)
            semantic_related = await self.repository.get_related_chunks_via_relationships(
                result.chunk_id,
                relation_types=None,  # All types
                min_weight=0.5,  # Higher threshold for quality
                limit=5
            )
            
            for chunk, rel_type, weight, description in semantic_related:
                chunk_entities = await self.repository.get_entities_for_chunk(chunk.id)
                reasoning_path = [{
                    "type": "semantic_relationship",
                    "relation": rel_type,
                    "weight": weight,
                    "description": description
                }]
                
                # Boost certain relationship types
                relationship_boost = 1.0
                if rel_type == "ELABORATES":
                    relationship_boost = 1.2  # Elaborations are highly relevant
                elif rel_type == "SUPPORTS":
                    relationship_boost = 1.15  # Supporting evidence is valuable
                elif rel_type == "CONTRADICTS":
                    relationship_boost = 0.9  # Still relevant but penalize slightly
                
                search_result = SearchResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    score=result.score * weight * relationship_boost,
                    metadata=chunk.metadata,
                    entities=[e.name for e in chunk_entities],
                    reasoning_path=reasoning_path,
                )
                all_results.append(search_result)
            
            # Also traverse via entity relationships for comprehensive coverage
            entity_related = await self.repository.get_related_chunks_via_entities(
                result.chunk_id, max_hops=max_hops, limit=3
            )
            
            for chunk, entities in entity_related:
                reasoning_path = [{"type": "entity", "names": entities}]
                
                search_result = SearchResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    score=result.score * 0.7,  # Lower score than semantic relationships
                    metadata=chunk.metadata,
                    entities=entities,
                    reasoning_path=reasoning_path,
                )
                all_results.append(search_result)
        
        # Deduplicate and sort by score
        seen = set()
        unique_results = []
        for r in sorted(all_results, key=lambda x: x.score, reverse=True):
            if r.chunk_id not in seen:
                seen.add(r.chunk_id)
                unique_results.append(r)
        
        return unique_results[:top_k]
    
    async def _semantic_relationship_search(
        self, query: str, top_k: int
    ) -> list[SearchResult]:
        """Search prioritizing semantic chunk relationships (ELABORATES, SUPPORTS, etc.)."""
        # Get initial seed chunks
        seed_results = await self._vector_search(query, max(3, top_k // 3))
        
        all_results = list(seed_results)
        relationship_chain = []
        
        # For each seed, find chunks connected by meaningful relationships
        for seed_result in seed_results:
            # Prioritize ELABORATES and SUPPORTS relationships
            for relation_types, boost in [
                (["ELABORATES"], 1.3),
                (["SUPPORTS"], 1.2),
                (["REFERENCES"], 1.0),
                (["CONTRADICTS"], 0.95),  # Include contradictions for completeness
            ]:
                related = await self.repository.get_related_chunks_via_relationships(
                    seed_result.chunk_id,
                    relation_types=relation_types,
                    min_weight=0.4,
                    limit=3
                )
                
                for chunk, rel_type, weight, description in related:
                    chunk_entities = await self.repository.get_entities_for_chunk(chunk.id)
                    
                    # Build reasoning chain
                    reasoning = [{
                        "type": "semantic_chain",
                        "from_chunk": str(seed_result.chunk_id),
                        "relation": rel_type,
                        "weight": weight,
                        "description": description,
                        "boost": boost
                    }]
                    
                    search_result = SearchResult(
                        chunk_id=chunk.id,
                        document_id=chunk.document_id,
                        content=chunk.content,
                        score=seed_result.score * weight * boost,
                        metadata=chunk.metadata,
                        entities=[e.name for e in chunk_entities],
                        reasoning_path=reasoning,
                    )
                    all_results.append(search_result)
        
        # Deduplicate and sort by score
        seen = set()
        unique_results = []
        for r in sorted(all_results, key=lambda x: x.score, reverse=True):
            if r.chunk_id not in seen:
                seen.add(r.chunk_id)
                unique_results.append(r)
        
        logger.info(f"Semantic relationship search found {len(unique_results)} unique chunks")
        return unique_results[:top_k]

    async def _community_based_search(
        self, query: str, top_k: int
    ) -> list[SearchResult]:
        """Community-aware retrieval."""
        # Find relevant communities first (using vector search on community summaries)
        query_embedding = await self.embedding_service.generate_embedding(query)
        
        # Get all communities and their embeddings (simplified)
        # In production, use community vector index
        
        # For now, get chunks from all communities
        # This is a simplified version
        results = await self._vector_search(query, top_k)
        
        # Enhance with community information
        # This would involve finding which communities chunks belong to
        
        return results

    async def _extract_query_entities(self, query: str) -> list[dict]:
        """Extract entities from query text."""
        system_prompt = """Extract named entities from the query. Return JSON array of entities with name and type.
Example: [{"name": "Apple", "type": "ORGANIZATION"}, {"name": "iPhone", "type": "PRODUCT"}]"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            
            import json
            content = response.choices[0].message.content
            data = json.loads(content)
            
            if isinstance(data, dict) and 'entities' in data:
                return data['entities']
            elif isinstance(data, list):
                return data
            
        except Exception as e:
            logger.warning(f"Error extracting query entities: {e}")
        
        return []

    async def _chunks_to_results(
        self, chunk_results: list[tuple[Chunk, float]], vector_only: bool = False
    ) -> list[SearchResult]:
        """Convert chunk tuples to SearchResult objects."""
        results = []
        for chunk, score in chunk_results:
            entities = await self.repository.get_entities_for_chunk(chunk.id)
            result = SearchResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                content=chunk.content,
                score=score,
                metadata=chunk.metadata,
                entities=[e.name for e in entities],
                vector_score=score if vector_only else None,
            )
            results.append(result)
        return results

    def _result_to_chunk(self, result: SearchResult) -> Chunk:
        """Convert SearchResult back to Chunk."""
        return Chunk(
            id=result.chunk_id,
            document_id=result.document_id,
            content=result.content,
            chunk_index=0,  # Not tracked in SearchResult
            start_char=0,
            end_char=len(result.content),
            metadata=result.metadata,
        )

    def _build_context(self, results: list[SearchResult]) -> str:
        """Build context string from search results."""
        context_parts = []
        current_length = 0

        for i, result in enumerate(results, 1):
            # Include entities if available
            entity_info = f" [Entities: {', '.join(result.entities)}]" if result.entities else ""
            chunk_text = f"[Source {i}]{entity_info}\n{result.content}\n"

            if current_length + len(chunk_text) > self.max_context_length:
                break

            context_parts.append(chunk_text)
            current_length += len(chunk_text)

        return "\n".join(context_parts)

    async def _generate_answer(
        self, query: str, context: str, subqueries: list[SubQuery]
    ) -> str:
        """Generate answer using LLM with retrieved context."""
        system_prompt = """You are a helpful AI assistant that answers questions based on the provided context.

Guidelines:
- Answer the question using ONLY information from the provided context
- If the context doesn't contain enough information to answer fully, say so explicitly
- Be concise but comprehensive
- CRITICAL: Every factual claim MUST cite a source using [Source N] format
- Example: "AI transforms technology [Source 1]. Machine learning enables learning from data [Source 2]."
- If multiple sources provide relevant information, synthesize them coherently
- Pay attention to entity relationships mentioned in the sources
- Do not make up information not present in the context
- Be precise and factual - this is more important than being creative
"""

        # Include sub-queries if decomposed
        query_text = query
        if len(subqueries) > 1:
            sub_q_text = "\n".join([f"- {sq.query}" for sq in subqueries])
            query_text = f"{query}\n\nSub-questions:\n{sub_q_text}"

        user_prompt = f"""Context:
{context}

Question: {query_text}

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
            return answer

        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return "I encountered an error while generating the answer. Please try again."

    async def stream_answer(
        self,
        query: str,
        context: str,
        subqueries: list[SubQuery],
    ):
        """Stream answer generation token by token."""
        system_prompt = """You are a helpful AI assistant that answers questions based on the provided context.

Guidelines:
- Answer the question using ONLY information from the provided context
- If the context doesn't contain enough information to answer fully, say so
- Be concise but comprehensive
- Cite specific sources when possible (e.g., "According to Source 1...")
- If multiple sources provide relevant information, synthesize them
- Pay attention to entity relationships mentioned in the sources
- Do not make up information not present in the context
"""

        # Include sub-queries if decomposed
        query_text = query
        if len(subqueries) > 1:
            sub_q_text = "\n".join([f"- {sq.query}" for sq in subqueries])
            query_text = f"{query}\n\nSub-questions:\n{sub_q_text}"

        user_prompt = f"""Context:
{context}

Question: {query_text}

Answer:"""

        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=500,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Error streaming answer: {e}")
            yield "I encountered an error while generating the answer. Please try again."
