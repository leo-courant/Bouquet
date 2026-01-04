"""Ultra-advanced query engine with maximum accuracy features."""

from typing import Optional

import openai
from loguru import logger

from app.domain import Chunk, QueryResponse, SearchResult
from app.domain.query import QueryType, RetrievalStrategy, SubQuery
from app.repositories import Neo4jRepository
from app.services.embedding_service import EmbeddingService
from app.services.advanced_query_engine import AdvancedQueryEngine
from app.services.self_consistency import SelfConsistencyService
from app.services.confidence_scorer import ConfidenceScorer
from app.services.temporal_ranker import TemporalRanker
from app.services.citation_extractor import CitationExtractor
from app.services.factuality_verifier import FactualityVerifier
from app.services.conflict_resolver import ConflictResolver
from app.services.query_intent_classifier import QueryIntentClassifier
from app.services.iterative_refiner import IterativeRefiner
from app.services.active_learner import ActiveLearner
from app.services.cross_document_synthesizer import CrossDocumentSynthesizer
from app.services.comparative_analyzer import ComparativeAnalyzer
from app.services.reasoning_chain_builder import ReasoningChainBuilder
from app.services.citation_validator import CitationValidator


class UltraAdvancedQueryEngine(AdvancedQueryEngine):
    """Ultra-advanced query engine with all accuracy-maximizing features."""

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
        # Parent class args
        enable_reranking: bool = True,
        enable_entity_expansion: bool = True,
        enable_query_decomposition: bool = True,
        enable_feedback: bool = True,
        hyde_service=None,
        query_reformulator=None,
        context_compressor=None,
        query_cache=None,
        # New accuracy features
        self_consistency_service: Optional[SelfConsistencyService] = None,
        confidence_scorer: Optional[ConfidenceScorer] = None,
        temporal_ranker: Optional[TemporalRanker] = None,
        citation_extractor: Optional[CitationExtractor] = None,
        factuality_verifier: Optional[FactualityVerifier] = None,
        conflict_resolver: Optional[ConflictResolver] = None,
        query_intent_classifier: Optional[QueryIntentClassifier] = None,
        iterative_refiner: Optional[IterativeRefiner] = None,
        active_learner: Optional[ActiveLearner] = None,
        # Complex reasoning features
        cross_document_synthesizer: Optional[CrossDocumentSynthesizer] = None,
        comparative_analyzer: Optional[ComparativeAnalyzer] = None,
        reasoning_chain_builder: Optional[ReasoningChainBuilder] = None,
        citation_validator: Optional[CitationValidator] = None,
    ) -> None:
        """Initialize ultra-advanced query engine."""
        # Initialize parent
        super().__init__(
            repository=repository,
            embedding_service=embedding_service,
            api_key=api_key,
            model=model,
            top_k=top_k,
            rerank_top_k=rerank_top_k,
            max_context_length=max_context_length,
            min_similarity_threshold=min_similarity_threshold,
            enable_reranking=enable_reranking,
            enable_entity_expansion=enable_entity_expansion,
            enable_query_decomposition=enable_query_decomposition,
            enable_feedback=enable_feedback,
            hyde_service=hyde_service,
            query_reformulator=query_reformulator,
            context_compressor=context_compressor,
            query_cache=query_cache,
        )
        
        # New accuracy-focused services
        self.self_consistency_service = self_consistency_service
        self.confidence_scorer = confidence_scorer
        self.temporal_ranker = temporal_ranker
        self.citation_extractor = citation_extractor
        self.factuality_verifier = factuality_verifier
        self.conflict_resolver = conflict_resolver
        self.query_intent_classifier = query_intent_classifier
        self.iterative_refiner = iterative_refiner
        self.active_learner = active_learner
        
        # Complex reasoning services
        self.cross_document_synthesizer = cross_document_synthesizer
        self.comparative_analyzer = comparative_analyzer
        self.reasoning_chain_builder = reasoning_chain_builder
        self.citation_validator = citation_validator
        
        logger.info("Initialized UltraAdvancedQueryEngine with maximum accuracy features")
        if self_consistency_service:
            logger.info("Self-consistency verification enabled")
        if confidence_scorer:
            logger.info("Answer confidence scoring enabled")
        if temporal_ranker:
            logger.info("Temporal-aware ranking enabled")
        if citation_extractor:
            logger.info("Precise citation extraction enabled")
        if factuality_verifier:
            logger.info("Factuality verification enabled")
        if conflict_resolver:
            logger.info("Conflict resolution enabled")
        if query_intent_classifier:
            logger.info("Query intent classification enabled")
        if iterative_refiner:
            logger.info("Iterative answer refinement enabled")
        if active_learner:
            logger.info("Active learning from feedback enabled")
        if cross_document_synthesizer:
            logger.info("Cross-document synthesis enabled")
        if comparative_analyzer:
            logger.info("Comparative analysis enabled")
        if reasoning_chain_builder:
            logger.info("Reasoning chain building enabled")
        if citation_validator:
            logger.info("Citation validation enabled")

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
        """Execute ultra-advanced query with maximum accuracy."""
        logger.info(f"Processing ultra-advanced query: {query}")
        
        # Quick exit for simple greetings/conversational queries
        query_lower = query.strip().lower()
        greetings = {'hi', 'hello', 'hey', 'greetings', 'good morning', 'good afternoon', 'good evening'}
        if query_lower in greetings or len(query_lower) < 3:
            logger.info(f"Simple conversational query detected, returning greeting")
            return QueryResponse(
                answer="Hello! I'm your AI assistant. I can help you find information from your uploaded documents. Please upload some documents and ask me questions about them.",
                sources=[],
                metadata={"query": query, "type": "greeting", "confidence": 1.0},
            )
        
        if top_k is None:
            top_k = self.top_k
        
        # Step 0: Query intent classification
        query_classification = None
        if self.query_intent_classifier:
            query_classification = await self.query_intent_classifier.classify_query(query)
            logger.info(f"Query classified: {query_classification['query_type']}, complexity: {query_classification['complexity']}")
            
            # Override strategy if classifier recommends
            recommended_strategy = query_classification.get('optimal_strategy')
            if recommended_strategy and strategy == RetrievalStrategy.ADAPTIVE:
                strategy = RetrievalStrategy(recommended_strategy)
                logger.info(f"Using recommended strategy: {strategy.value}")
        
        # Check cache first
        if self.query_cache:
            cached_response = await self.query_cache.get_result(query, strategy.value, top_k)
            if cached_response:
                logger.info(f"Cache hit for ultra query: {query[:50]}...")
                return cached_response
        
        # Step 1: Query reformulation (inherited)
        query_variants = [query]
        if self.query_reformulator:
            query_variants = await self.query_reformulator.reformulate_query(query)
            logger.info(f"Generated {len(query_variants)} query variants")
        
        # Step 2: Query decomposition (inherited)
        subqueries = [SubQuery(query=query, query_type=QueryType.FACTUAL, priority=1)]
        if self.query_decomposer and self.query_decomposer.should_decompose(query):
            subqueries = await self.query_decomposer.decompose_query(query)
            logger.info(f"Decomposed into {len(subqueries)} sub-queries")
        
        # Step 3: Retrieve with all variants (inherited logic)
        all_results = []
        for subquery in subqueries:
            for query_variant in query_variants:
                search_query = query_variant
                if self.hyde_service:
                    hyde_doc = await self.hyde_service.generate_hypothetical_answer(query_variant)
                    if hyde_doc != query_variant:
                        search_query = hyde_doc
                        logger.debug(f"Using HyDE document")
                
                results = await self._retrieve(
                    search_query,
                    top_k,
                    strategy,
                    use_entity_expansion,
                    use_community_context,
                    max_hops,
                )
                all_results.extend(results)
        
        # Deduplicate
        seen_chunks = set()
        unique_results = []
        for result in all_results:
            if result.chunk_id not in seen_chunks:
                seen_chunks.add(result.chunk_id)
                unique_results.append(result)
        
        if not unique_results:
            empty_response = QueryResponse(
                answer="I don't have enough information in my knowledge base to answer this question accurately.",
                sources=[],
                metadata={"query": query, "total_sources": 0, "confidence": 0.0},
            )
            if self.query_cache:
                await self.query_cache.set_result(query, strategy.value, top_k, empty_response)
            return empty_response
        
        # Step 4: Temporal ranking (NEW)
        if self.temporal_ranker:
            temporal_info = self.temporal_ranker.detect_temporal_query(query)
            if temporal_info['is_temporal']:
                logger.info(f"Applying temporal ranking (prefer_recent={temporal_info['prefer_recent']})")
                unique_results = self.temporal_ranker.apply_temporal_ranking(
                    unique_results,
                    prefer_recent=temporal_info['prefer_recent']
                )
        
        # Step 5: Reranking (inherited)
        if use_reranking and self.reranker:
            unique_results = self.reranker.rerank_search_results(
                query, unique_results, top_k=self.rerank_top_k
            )
        
        # Step 6: Conflict detection and resolution (NEW)
        conflicts = []
        conflict_resolution = None
        if self.conflict_resolver:
            conflicts = await self.conflict_resolver.detect_conflicts(unique_results[:10])
            if conflicts:
                logger.warning(f"Detected {len(conflicts)} conflicts in sources")
                conflict_resolution = await self.conflict_resolver.resolve_conflicts(
                    query, unique_results, conflicts
                )
                
                # Prioritize sources by reliability
                unique_results = self.conflict_resolver.prioritize_sources_by_reliability(
                    unique_results, conflicts
                )
        
        # Step 7: Apply feedback (inherited + active learning)
        if enable_feedback and self.feedback_service:
            results_tuples = [(self._result_to_chunk(r), r.rerank_score or r.score) for r in unique_results]
            adjusted = self.feedback_service.apply_feedback_to_scores(results_tuples)
            
            for i, (chunk, adj_score) in enumerate(adjusted):
                if i < len(unique_results):
                    unique_results[i].score = adj_score
        
        # Step 8: Build context and compress
        context = self._build_context(unique_results)
        
        if self.context_compressor and len(context) > self.max_context_length:
            logger.info(f"Compressing context from {len(context)} characters")
            compressed = await self.context_compressor.compress_context(
                context, query, max_tokens=self.max_context_length // 4
            )
            if compressed:
                context = compressed
                logger.info(f"Compressed to {len(context)} characters")
        
        # Step 9: Enhanced prompt with Chain-of-Thought (NEW)
        system_prompt = self._build_enhanced_system_prompt(
            query_classification,
            conflict_resolution,
        )
        
        # Step 10: Generate answer with self-consistency (NEW)
        answer = None
        consistency_score = None
        
        if self.self_consistency_service:
            # Generate multiple answer candidates
            answers = await self.self_consistency_service.generate_multiple_answers(
                query, context, system_prompt
            )
            
            # Select most consistent
            answer, consistency_score = await self.self_consistency_service.select_most_consistent(
                query, answers
            )
            logger.info(f"Self-consistency score: {consistency_score:.3f}")
            
            # Verify answer
            is_verified, verification_note = await self.self_consistency_service.verify_answer(
                query, answer, context
            )
            if not is_verified:
                logger.warning(f"Answer not fully verified: {verification_note}")
        else:
            # Standard generation
            answer = await self._generate_answer(query, context, subqueries)
            consistency_score = 0.7  # Default
        
        # Step 11: Factuality verification (NEW)
        factuality_result = None
        if self.factuality_verifier:
            factuality_result = await self.factuality_verifier.verify_answer_factuality(
                answer, context
            )
            logger.info(f"Factuality score: {factuality_result['factuality_score']:.3f}")
            
            # If not factual, suggest correction
            if not factuality_result['is_factual']:
                logger.warning("Answer contains unverified claims, attempting correction")
                corrected = await self.factuality_verifier.suggest_corrections(
                    answer, factuality_result, context
                )
                if corrected:
                    answer = corrected
                    logger.info("Using corrected answer")
        
        # Step 12: Compute confidence score (NEW)
        confidence_data = None
        if self.confidence_scorer:
            retrieved_chunks = [r.content for r in unique_results[:10]]
            confidence_data = await self.confidence_scorer.compute_confidence(
                query,
                answer,
                context,
                retrieved_chunks,
                consistency_score=consistency_score,
            )
            logger.info(f"Overall confidence: {confidence_data['overall_confidence']:.3f} ({confidence_data['confidence_level']})")
            
            # Check if we should abstain from answering
            if confidence_data['should_abstain']:
                logger.warning("Confidence too low, returning abstention")
                answer = self.confidence_scorer.get_low_confidence_response(query, confidence_data)
        
        # Step 13: Extract precise citations (NEW)
        citations = {}
        if self.citation_extractor and confidence_data and not confidence_data.get('should_abstain', False):
            citations = await self.citation_extractor.extract_supporting_quotes(
                answer, unique_results[:5]
            )
            
            if citations:
                # Add citations to answer
                answer = await self.citation_extractor.generate_cited_answer(
                    answer, citations, unique_results
                )
        
        # Step 14: Iterative refinement if needed (NEW)
        refinement_history = []
        if self.iterative_refiner and confidence_data:
            # Only refine if confidence is medium (not too low, not perfect)
            if 0.5 < confidence_data['overall_confidence'] < 0.85:
                logger.info("Attempting iterative refinement")
                
                # Define retrieval function for refinement
                async def retrieve_more(focused_query: str):
                    return await self._retrieve(
                        focused_query, top_k=5, strategy=strategy,
                        use_entity_expansion=use_entity_expansion,
                        use_community_context=use_community_context,
                        max_hops=max_hops
                    )
                
                refinement_result = await self.iterative_refiner.refine_answer(
                    query, answer, context, unique_results, retrieve_more
                )
                
                if refinement_result['iterations'] > 1:
                    answer = refinement_result['final_answer']
                    refinement_history = refinement_result['refinement_history']
                    logger.info(f"Answer refined through {refinement_result['iterations']} iterations")
        
        # Step 15: Cross-document synthesis (NEW)
        synthesis_result = None
        if self.cross_document_synthesizer and len(unique_results) > 0:
            # Group sources by document
            sources_by_doc = self.cross_document_synthesizer.group_sources_by_document(unique_results[:10])
            
            if len(sources_by_doc) > 1:
                logger.info(f"Performing cross-document synthesis across {len(sources_by_doc)} documents")
                synthesis_result = await self.cross_document_synthesizer.synthesize_answer(
                    query, sources_by_doc, conflicts
                )
                
                if synthesis_result.get('synthesized') and synthesis_result.get('answer'):
                    # Use synthesized answer
                    original_answer = answer
                    answer = synthesis_result['answer']
                    logger.info("Using cross-document synthesized answer")
        
        # Step 16: Comparative analysis (NEW)
        comparison_result = None
        if self.comparative_analyzer:
            # Check if this is a comparison query
            comparison_analysis = await self.comparative_analyzer.analyze_comparison_query(
                query, unique_results[:10]
            )
            
            if comparison_analysis['is_comparison'] and len(comparison_analysis.get('targets', [])) >= 2:
                logger.info(f"Performing comparative analysis for comparison query")
                
                target1, target2 = comparison_analysis['targets'][:2]
                comparison_result = await self.comparative_analyzer.generate_structured_comparison(
                    query, target1, target2, unique_results[:10]
                )
                
                if comparison_result.get('comparison'):
                    # Use comparison result as answer
                    answer = comparison_result['comparison']
                    logger.info("Using comparative analysis answer")
        
        # Step 17: Build reasoning chain (NEW)
        reasoning_chain = None
        if self.reasoning_chain_builder and (subqueries and len(subqueries) > 1 or any(hasattr(r, 'reasoning_path') and r.reasoning_path for r in unique_results[:5])):
            logger.info("Building explicit reasoning chain")
            
            sub_query_list = [sq.query for sq in subqueries] if len(subqueries) > 1 else None
            
            reasoning_chain = await self.reasoning_chain_builder.build_reasoning_chain(
                query, unique_results[:10], sub_query_list
            )
            
            # Validate the chain
            chain_validation = await self.reasoning_chain_builder.validate_reasoning_chain(
                reasoning_chain['chain'], answer
            )
            
            if not chain_validation['valid']:
                logger.warning(f"Reasoning chain validation failed: confidence {chain_validation['confidence']:.2f}")
        
        # Step 18: Citation validation (NEW)
        citation_validation = None
        if self.citation_validator and confidence_data and not confidence_data.get('should_abstain', False):
            logger.info("Validating citations in answer")
            
            citation_validation = await self.citation_validator.validate_answer_citations(
                answer, unique_results[:10]
            )
            
            if not citation_validation['valid']:
                # Format percentage safely - handle 0 citations case
                total_cites = citation_validation['total_citations']
                validated_cites = citation_validation['validated_citations']
                score = citation_validation['score']
                
                if total_cites == 0:
                    logger.warning("Citation validation failed: No citations found in answer")
                else:
                    logger.warning(
                        f"Citation validation failed: {score:.2%} "
                        f"({validated_cites}/{total_cites})"
                    )
                
                # Try to fix citations
                corrected_answer = await self.citation_validator.suggest_citation_fixes(
                    answer, unique_results[:10], citation_validation
                )
                
                if corrected_answer:
                    logger.info("Applied citation corrections")
                    answer = corrected_answer
                    
                    # Re-validate
                    citation_validation = await self.citation_validator.validate_answer_citations(
                        answer, unique_results[:10]
                    )
            
            # Log final validation result
            if citation_validation['total_citations'] > 0:
                logger.info(f"Citation validation: {citation_validation['score']:.2%}")
            else:
                logger.info("Citation validation: No citations to validate")
        
        # Step 19: Build final response
        query_type = subqueries[0].query_type if subqueries else QueryType.FACTUAL
        
        response = QueryResponse(
            answer=answer,
            sources=unique_results[:self.rerank_top_k],
            metadata={
                "query": query,
                "total_sources": len(unique_results),
                "context_length": len(context),
                "strategy": strategy.value,
                "query_variants": len(query_variants) if len(query_variants) > 1 else None,
                "hyde_used": self.hyde_service is not None,
                "compressed": self.context_compressor is not None,
                # New metadata
                "confidence": confidence_data['overall_confidence'] if confidence_data else None,
                "confidence_level": confidence_data['confidence_level'] if confidence_data else None,
                "consistency_score": consistency_score,
                "factuality_score": factuality_result['factuality_score'] if factuality_result else None,
                "conflicts_detected": len(conflicts) > 0,
                "num_conflicts": len(conflicts),
                "citations_extracted": len(citations) > 0,
                "refinement_iterations": len(refinement_history),
                "query_classification": query_classification['query_type'] if query_classification else None,
                "complexity": query_classification['complexity'] if query_classification else None,
                # Complex reasoning metadata
                "cross_document_synthesis": synthesis_result is not None and synthesis_result.get('synthesized'),
                "num_documents": synthesis_result.get('num_documents') if synthesis_result else None,
                "comparative_analysis": comparison_result is not None,
                "comparison_targets": comparison_result.get('target1') + " vs " + comparison_result.get('target2') if comparison_result else None,
                "reasoning_chain_steps": reasoning_chain.get('num_steps') if reasoning_chain else None,
                "citation_validation_score": citation_validation.get('score') if citation_validation else None,
                "citation_valid": citation_validation.get('valid') if citation_validation else None,
            },
            query_type=query_type,
            decomposed_queries=[sq.query for sq in subqueries] if len(subqueries) > 1 else [],
        )
        
        # Step 20: Active learning - record for future improvement (NEW)
        if self.active_learner and confidence_data and not confidence_data['should_abstain']:
            # This will be updated when user provides feedback
            # For now, just log that we're ready for feedback
            logger.debug("Query processed and ready for feedback learning")
        
        # Cache the response
        if self.query_cache:
            await self.query_cache.set_result(query, strategy.value, top_k, response)
        
        confidence_str = f"{confidence_data['overall_confidence']:.3f}" if confidence_data else "N/A"
        logger.info(f"Generated ultra-accurate answer with confidence {confidence_str}")
        return response

    def _build_enhanced_system_prompt(
        self,
        query_classification: Optional[dict],
        conflict_resolution: Optional[dict],
    ) -> str:
        """Build enhanced system prompt with Chain-of-Thought reasoning."""
        
        base_prompt = """You are a highly accurate AI assistant that answers questions based on provided context.

**Critical Instructions:**
1. Answer ONLY using information from the provided context
2. If you don't have sufficient information to answer the question, say "I don't have sufficient information to answer this question."
3. Use step-by-step reasoning (Chain-of-Thought) for complex questions
4. Cite specific sources when making claims (e.g., "According to Source 1...")
5. If you find any uncertainty or gaps, acknowledge them
6. Do NOT make up information not present in the context
7. Be precise with facts, especially numbers and dates
8. If sources disagree, present both perspectives fairly

**Reasoning Process:**
- First, identify the key information needed to answer
- Then, locate relevant facts in the context
- Finally, synthesize a clear, accurate answer"""

        # Add query-specific guidance
        if query_classification:
            query_type = query_classification.get('query_type', '')
            complexity = query_classification.get('complexity', '')
            
            if complexity in ['high', 'very_high']:
                base_prompt += "\n\n**Note:** This is a complex question. Break it down into steps and reason through each part."
            
            if query_type == 'comparative':
                base_prompt += "\n\n**Note:** Compare the entities systematically across relevant dimensions."
            elif query_type == 'temporal':
                base_prompt += "\n\n**Note:** Pay careful attention to dates, time periods, and chronological order."
        
        # Add conflict resolution guidance
        if conflict_resolution and conflict_resolution.get('has_conflicts'):
            guidance = conflict_resolution.get('guidance', '')
            base_prompt += f"\n\n**Important:** The sources contain conflicting information. {guidance}"
        
        return base_prompt

    async def record_feedback(
        self,
        query: str,
        response: QueryResponse,
        rating: int,
        helpful: bool,
        feedback_text: Optional[str] = None,
    ) -> None:
        """Record user feedback for active learning."""
        if not self.active_learner:
            return
        
        # Extract entities from query for learning
        entities = []
        if self.query_intent_classifier:
            classification = await self.query_intent_classifier.classify_query(query)
            entities = classification.get('entities', [])
        
        # Update active learner
        strategy = response.metadata.get('strategy', 'adaptive')
        self.active_learner.update_from_feedback(
            query=query,
            strategy=strategy,
            entities=entities,
            rating=rating,
            helpful=helpful,
        )
        
        logger.info(f"Recorded feedback for active learning: rating={rating}")
