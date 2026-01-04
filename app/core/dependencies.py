"""Core dependency injection for FastAPI."""

from functools import lru_cache
from typing import AsyncGenerator

from fastapi import Depends
from loguru import logger

from app.core.config import Settings, get_settings
from app.repositories.neo4j_repository import Neo4jRepository
from app.services.active_learner import ActiveLearner
from app.services.advanced_query_engine import AdvancedQueryEngine
from app.services.cache_service import CacheService, EmbeddingCache, QueryCache
from app.services.citation_extractor import CitationExtractor
from app.services.confidence_scorer import ConfidenceScorer
from app.services.conflict_resolver import ConflictResolver
from app.services.context_compressor import ContextCompressor
from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import EmbeddingService
from app.services.enhanced_document_processor import EnhancedDocumentProcessor
from app.services.entity_disambiguator import EntityDisambiguator
from app.services.entity_extractor import EntityExtractor
from app.services.factuality_verifier import FactualityVerifier
from app.services.feedback_service import FeedbackService
from app.services.graph_builder import GraphBuilder
from app.services.hyde_service import HyDEService
from app.services.iterative_refiner import IterativeRefiner
from app.services.query_engine import QueryEngine
from app.services.query_intent_classifier import QueryIntentClassifier
from app.services.query_reformulator import QueryReformulator
from app.services.rag_evaluator import RAGEvaluator
from app.services.self_consistency import SelfConsistencyService
from app.services.temporal_ranker import TemporalRanker
from app.services.ultra_advanced_query_engine import UltraAdvancedQueryEngine
from app.services.cross_document_synthesizer import CrossDocumentSynthesizer
from app.services.comparative_analyzer import ComparativeAnalyzer
from app.services.reasoning_chain_builder import ReasoningChainBuilder
from app.services.citation_validator import CitationValidator
from app.services.query_complexity_analyzer import QueryComplexityAnalyzer


# Caching instances
@lru_cache()
def get_cache_service() -> CacheService:
    """Get cache service singleton."""
    settings = get_settings()
    return CacheService(
        redis_url=settings.redis_url,
        ttl=settings.cache_ttl,
    )


@lru_cache()
def get_embedding_cache() -> EmbeddingCache:
    """Get embedding cache singleton."""
    cache_service = get_cache_service()
    return EmbeddingCache(cache_service)


@lru_cache()
def get_query_cache() -> QueryCache:
    """Get query cache singleton."""
    cache_service = get_cache_service()
    return QueryCache(cache_service)


async def get_neo4j_repository() -> AsyncGenerator[Neo4jRepository, None]:
    """Get Neo4j repository instance."""
    logger.debug(f"[DEBUG] get_neo4j_repository called")
    try:
        settings = get_settings()
        logger.debug(f"[DEBUG] Creating Neo4jRepository with uri={settings.neo4j_uri}")
        repository = Neo4jRepository(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
            database=settings.neo4j_database,
        )
        logger.debug(f"[DEBUG] Connecting to Neo4j")
        await repository.connect()
        logger.debug(f"[DEBUG] Neo4j connected successfully")
        
        # Create vector indexes if enabled
        if settings.use_hnsw_index:
            try:
                logger.debug(f"[DEBUG] Creating HNSW vector indexes")
                await repository.create_vector_index(embedding_dimension=1536)
                await repository.create_community_vector_index(embedding_dimension=1536)
                logger.debug(f"[DEBUG] Vector indexes created successfully")
            except Exception as e:
                # Non-critical, just log
                logger.warning(f"[WARNING] Failed to create vector indexes: {type(e).__name__}: {str(e)}")
                pass
        
        try:
            yield repository
        finally:
            logger.debug(f"[DEBUG] Closing Neo4j repository")
            await repository.close()
    except Exception as e:
        logger.error(f"[ERROR] Failed to get Neo4j repository: {type(e).__name__}: {str(e)}")
        logger.exception(f"[EXCEPTION] Neo4j repository error:")
        raise


async def get_embedding_service() -> EmbeddingService:
    """Get embedding service instance with caching."""
    logger.debug(f"[DEBUG] get_embedding_service called")
    try:
        settings = get_settings()
        embedding_cache = get_embedding_cache() if settings.enable_embedding_cache else None
        logger.debug(f"[DEBUG] Creating EmbeddingService with model={settings.openai_embedding_model}, cache={'enabled' if embedding_cache else 'disabled'}")
        service = EmbeddingService(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
            embedding_cache=embedding_cache,
            dimensions=1536,  # Use 1536 dimensions to stay within Neo4j's 2048 limit
        )
        logger.debug(f"[DEBUG] EmbeddingService created successfully")
        return service
    except Exception as e:
        logger.error(f"[ERROR] Failed to get embedding service: {type(e).__name__}: {str(e)}")
        logger.exception(f"[EXCEPTION] Embedding service error:")
        raise


async def get_entity_extractor() -> EntityExtractor:
    """Get entity extractor instance."""
    settings = get_settings()
    return EntityExtractor(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_entities=settings.max_entities_per_chunk,
    )


async def get_entity_disambiguator() -> EntityDisambiguator:
    """Get entity disambiguator instance."""
    settings = get_settings()
    return EntityDisambiguator(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        threshold=settings.disambiguation_threshold,
    )


async def get_feedback_service() -> FeedbackService:
    """Get feedback service instance."""
    settings = get_settings()
    return FeedbackService(
        learning_rate=settings.feedback_learning_rate,
    )


async def get_document_processor() -> DocumentProcessor:
    """Get document processor instance (legacy)."""
    settings = get_settings()
    embedding_service = await get_embedding_service()
    entity_extractor = await get_entity_extractor()

    return DocumentProcessor(
        embedding_service=embedding_service,
        entity_extractor=entity_extractor,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        batch_size=settings.embedding_batch_size,
    )


async def get_enhanced_document_processor() -> EnhancedDocumentProcessor:
    """Get enhanced document processor instance."""
    settings = get_settings()
    embedding_service = await get_embedding_service()
    entity_extractor = await get_entity_extractor()
    entity_disambiguator = await get_entity_disambiguator()

    return EnhancedDocumentProcessor(
        embedding_service=embedding_service,
        entity_extractor=entity_extractor,
        entity_disambiguator=entity_disambiguator,
        use_semantic_chunking=settings.use_semantic_chunking,
        min_chunk_size=settings.min_chunk_size,
        max_chunk_size=settings.max_chunk_size,
        semantic_threshold=settings.semantic_threshold,
        create_chunk_relationships=True,
        enable_entity_disambiguation=settings.enable_entity_disambiguation,
    )


async def get_graph_builder(
    repository: Neo4jRepository = Depends(get_neo4j_repository),
) -> GraphBuilder:
    """Get graph builder instance."""
    settings = get_settings()
    return GraphBuilder(
        repository=repository,
        min_community_size=settings.min_community_size,
        max_levels=settings.max_hierarchy_levels,
        similarity_threshold=settings.similarity_threshold,
    )


async def get_query_engine(
    repository: Neo4jRepository = Depends(get_neo4j_repository),
) -> QueryEngine:
    """Get query engine instance (legacy)."""
    settings = get_settings()
    embedding_service = await get_embedding_service()

    return QueryEngine(
        repository=repository,
        embedding_service=embedding_service,
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        top_k=settings.top_k_retrieval,
        rerank_top_k=settings.rerank_top_k,
        max_context_length=settings.max_context_length,
        min_similarity_threshold=settings.min_similarity_threshold,
    )


async def get_advanced_query_engine(
    repository: Neo4jRepository = Depends(get_neo4j_repository),
) -> AdvancedQueryEngine:
    """Get advanced query engine instance with all enhancements."""
    settings = get_settings()
    embedding_service = await get_embedding_service()
    
    # Get new services if enabled
    hyde_service = None
    if settings.enable_hyde:
        hyde_service = await get_hyde_service()
    
    query_reformulator = None
    if settings.enable_query_reformulation:
        query_reformulator = await get_query_reformulator()
    
    context_compressor = None
    if settings.enable_context_compression:
        context_compressor = await get_context_compressor()
    
    query_cache = None
    if settings.enable_query_cache:
        query_cache = get_query_cache()

    return AdvancedQueryEngine(
        repository=repository,
        embedding_service=embedding_service,
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        top_k=settings.top_k_retrieval,
        rerank_top_k=settings.rerank_top_k,
        max_context_length=settings.max_context_length,
        min_similarity_threshold=settings.min_similarity_threshold,
        enable_reranking=settings.enable_reranking,
        enable_entity_expansion=settings.enable_entity_expansion,
        enable_query_decomposition=settings.enable_query_decomposition,
        enable_feedback=settings.enable_feedback_loop,
        hyde_service=hyde_service,
        query_reformulator=query_reformulator,
        context_compressor=context_compressor,
        query_cache=query_cache,
    )


async def get_hyde_service() -> HyDEService:
    """Get HyDE service instance."""
    settings = get_settings()
    return HyDEService(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        enable_hyde=settings.enable_hyde,
    )


async def get_query_reformulator() -> QueryReformulator:
    """Get query reformulator instance."""
    settings = get_settings()
    return QueryReformulator(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        enable_reformulation=settings.enable_query_reformulation,
    )


async def get_context_compressor() -> ContextCompressor:
    """Get context compressor instance."""
    settings = get_settings()
    return ContextCompressor(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        compression_ratio=settings.context_compression_ratio,
    )


async def get_rag_evaluator() -> RAGEvaluator:
    """Get RAG evaluator instance."""
    settings = get_settings()
    return RAGEvaluator(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


async def get_self_consistency_service() -> SelfConsistencyService:
    """Get self-consistency service instance."""
    settings = get_settings()
    return SelfConsistencyService(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        num_samples=settings.self_consistency_samples,
    )


async def get_confidence_scorer() -> ConfidenceScorer:
    """Get confidence scorer instance."""
    settings = get_settings()
    return ConfidenceScorer(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        min_threshold=settings.min_confidence_threshold,
    )


async def get_temporal_ranker() -> TemporalRanker:
    """Get temporal ranker instance."""
    settings = get_settings()
    return TemporalRanker(
        decay_factor=settings.temporal_decay_factor,
        enable_recency_boost=settings.enable_temporal_ranking,
    )


async def get_citation_extractor() -> CitationExtractor:
    """Get citation extractor instance."""
    settings = get_settings()
    return CitationExtractor(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_citation_length=settings.max_citation_length,
    )


async def get_factuality_verifier() -> FactualityVerifier:
    """Get factuality verifier instance."""
    settings = get_settings()
    return FactualityVerifier(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


async def get_conflict_resolver() -> ConflictResolver:
    """Get conflict resolver instance."""
    settings = get_settings()
    return ConflictResolver(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


async def get_query_intent_classifier() -> QueryIntentClassifier:
    """Get query intent classifier instance."""
    settings = get_settings()
    return QueryIntentClassifier(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


async def get_iterative_refiner() -> IterativeRefiner:
    """Get iterative refiner instance."""
    settings = get_settings()
    return IterativeRefiner(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_iterations=settings.max_refinement_iterations,
    )


@lru_cache()
def get_active_learner() -> ActiveLearner:
    """Get active learner singleton."""
    settings = get_settings()
    return ActiveLearner(
        learning_rate=settings.learning_rate,
    )


async def get_query_complexity_analyzer(
    repository: Neo4jRepository = Depends(get_neo4j_repository),
) -> QueryComplexityAnalyzer:
    """Get query complexity analyzer instance."""
    return QueryComplexityAnalyzer(
        repository=repository,
    )


async def get_cross_document_synthesizer() -> CrossDocumentSynthesizer:
    """Get cross-document synthesizer instance."""
    settings = get_settings()
    return CrossDocumentSynthesizer(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


async def get_comparative_analyzer() -> ComparativeAnalyzer:
    """Get comparative analyzer instance."""
    settings = get_settings()
    return ComparativeAnalyzer(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


async def get_reasoning_chain_builder() -> ReasoningChainBuilder:
    """Get reasoning chain builder instance."""
    settings = get_settings()
    return ReasoningChainBuilder(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


async def get_citation_validator() -> CitationValidator:
    """Get citation validator instance."""
    settings = get_settings()
    return CitationValidator(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


async def get_ultra_advanced_query_engine(
    repository: Neo4jRepository = Depends(get_neo4j_repository),
) -> UltraAdvancedQueryEngine:
    """Get ultra-advanced query engine with all accuracy features."""
    settings = get_settings()
    embedding_service = await get_embedding_service()
    
    # Get all optional services
    hyde_service = None
    if settings.enable_hyde:
        hyde_service = await get_hyde_service()
    
    query_reformulator = None
    if settings.enable_query_reformulation:
        query_reformulator = await get_query_reformulator()
    
    context_compressor = None
    if settings.enable_context_compression:
        context_compressor = await get_context_compressor()
    
    query_cache = None
    if settings.enable_query_cache:
        query_cache = get_query_cache()
    
    # New accuracy services
    self_consistency_service = None
    if settings.enable_self_consistency:
        self_consistency_service = await get_self_consistency_service()
    
    confidence_scorer = None
    if settings.enable_answer_confidence:
        confidence_scorer = await get_confidence_scorer()
    
    temporal_ranker = None
    if settings.enable_temporal_ranking:
        temporal_ranker = await get_temporal_ranker()
    
    citation_extractor = None
    if settings.enable_citation_extraction:
        citation_extractor = await get_citation_extractor()
    
    factuality_verifier = None
    if settings.enable_factuality_verification:
        factuality_verifier = await get_factuality_verifier()
    
    conflict_resolver = None
    if settings.enable_conflict_resolution:
        conflict_resolver = await get_conflict_resolver()
    
    query_intent_classifier = None
    if settings.enable_query_intent_classification:
        query_intent_classifier = await get_query_intent_classifier()
    
    iterative_refiner = None
    if settings.enable_iterative_refinement:
        iterative_refiner = await get_iterative_refiner()
    
    active_learner = None
    if settings.enable_active_learning:
        active_learner = get_active_learner()
    
    # Complex reasoning services
    cross_document_synthesizer = None
    if settings.enable_cross_document_synthesis:
        cross_document_synthesizer = await get_cross_document_synthesizer()
    
    comparative_analyzer = None
    if settings.enable_comparative_analysis:
        comparative_analyzer = await get_comparative_analyzer()
    
    reasoning_chain_builder = None
    if settings.enable_reasoning_chains:
        reasoning_chain_builder = await get_reasoning_chain_builder()
    
    citation_validator = None
    if settings.enable_citation_validation:
        citation_validator = await get_citation_validator()
    
    return UltraAdvancedQueryEngine(
        repository=repository,
        embedding_service=embedding_service,
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        top_k=settings.top_k_retrieval,
        rerank_top_k=settings.rerank_top_k,
        max_context_length=settings.max_context_length,
        min_similarity_threshold=settings.min_similarity_threshold,
        enable_reranking=settings.enable_reranking,
        enable_entity_expansion=settings.enable_entity_expansion,
        enable_query_decomposition=settings.enable_query_decomposition,
        enable_feedback=settings.enable_feedback_loop,
        hyde_service=hyde_service,
        query_reformulator=query_reformulator,
        context_compressor=context_compressor,
        query_cache=query_cache,
        self_consistency_service=self_consistency_service,
        confidence_scorer=confidence_scorer,
        temporal_ranker=temporal_ranker,
        citation_extractor=citation_extractor,
        factuality_verifier=factuality_verifier,
        conflict_resolver=conflict_resolver,
        query_intent_classifier=query_intent_classifier,
        iterative_refiner=iterative_refiner,
        active_learner=active_learner,
        cross_document_synthesizer=cross_document_synthesizer,
        comparative_analyzer=comparative_analyzer,
        reasoning_chain_builder=reasoning_chain_builder,
        citation_validator=citation_validator,
    )
