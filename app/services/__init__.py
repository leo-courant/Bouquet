"""Services layer initialization."""

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
from app.services.hybrid_search import HybridSearchEngine
from app.services.hyde_service import HyDEService
from app.services.iterative_refiner import IterativeRefiner
from app.services.query_decomposer import QueryDecomposer
from app.services.query_engine import QueryEngine
from app.services.query_intent_classifier import QueryIntentClassifier
from app.services.query_reformulator import QueryReformulator
from app.services.rag_evaluator import RAGEvaluator, EvaluationMetrics
from app.services.reranker import RerankerService
from app.services.self_consistency import SelfConsistencyService
from app.services.semantic_chunker import SemanticChunker
from app.services.temporal_ranker import TemporalRanker
from app.services.ultra_advanced_query_engine import UltraAdvancedQueryEngine

__all__ = [
    "EmbeddingService",
    "EntityExtractor",
    "EntityDisambiguator",
    "DocumentProcessor",
    "EnhancedDocumentProcessor",
    "GraphBuilder",
    "QueryEngine",
    "AdvancedQueryEngine",
    "UltraAdvancedQueryEngine",
    "SemanticChunker",
    "HybridSearchEngine",
    "RerankerService",
    "QueryDecomposer",
    "FeedbackService",
    "CacheService",
    "EmbeddingCache",
    "QueryCache",
    "HyDEService",
    "QueryReformulator",
    "ContextCompressor",
    "RAGEvaluator",
    "EvaluationMetrics",
    "SelfConsistencyService",
    "ConfidenceScorer",
    "TemporalRanker",
    "CitationExtractor",
    "FactualityVerifier",
    "ConflictResolver",
    "QueryIntentClassifier",
    "IterativeRefiner",
    "ActiveLearner",
]
