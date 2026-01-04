"""Core configuration settings for the Smart RAG application."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="Smart RAG", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # OpenAI
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4-turbo-preview", alias="OPENAI_MODEL")
    openai_embedding_model: str = Field(
        default="text-embedding-3-large", alias="OPENAI_EMBEDDING_MODEL"
    )
    openai_temperature: float = Field(default=0.0, alias="OPENAI_TEMPERATURE")
    openai_max_tokens: int = Field(default=1000, alias="OPENAI_MAX_TOKENS")

    # Neo4j
    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(..., alias="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", alias="NEO4J_DATABASE")

    # Document Processing
    chunk_size: int = Field(default=1000, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, alias="CHUNK_OVERLAP")
    max_entities_per_chunk: int = Field(default=50, alias="MAX_ENTITIES_PER_CHUNK")
    embedding_batch_size: int = Field(default=20, alias="EMBEDDING_BATCH_SIZE")

    # Graph Construction
    min_community_size: int = Field(default=3, alias="MIN_COMMUNITY_SIZE")
    max_hierarchy_levels: int = Field(default=3, alias="MAX_HIERARCHY_LEVELS")
    similarity_threshold: float = Field(default=0.7, alias="SIMILARITY_THRESHOLD")

    # RAG Settings
    top_k_retrieval: int = Field(default=10, alias="TOP_K_RETRIEVAL")
    rerank_top_k: int = Field(default=5, alias="RERANK_TOP_K")
    max_context_length: int = Field(default=8000, alias="MAX_CONTEXT_LENGTH")
    min_similarity_threshold: float = Field(default=0.7, alias="MIN_SIMILARITY_THRESHOLD")  # 0.7 = require decent similarity, 0.0 = return top_k regardless
    
    # Advanced Retrieval Settings
    use_hnsw_index: bool = Field(default=True, alias="USE_HNSW_INDEX")
    hnsw_m: int = Field(default=16, alias="HNSW_M")  # Number of connections
    hnsw_ef_construction: int = Field(default=200, alias="HNSW_EF_CONSTRUCTION")
    hnsw_ef_search: int = Field(default=100, alias="HNSW_EF_SEARCH")
    
    enable_hybrid_search: bool = Field(default=True, alias="ENABLE_HYBRID_SEARCH")
    bm25_weight: float = Field(default=0.3, alias="BM25_WEIGHT")
    vector_weight: float = Field(default=0.7, alias="VECTOR_WEIGHT")
    
    enable_entity_expansion: bool = Field(default=True, alias="ENABLE_ENTITY_EXPANSION")
    entity_expansion_hops: int = Field(default=2, alias="ENTITY_EXPANSION_HOPS")
    
    enable_reranking: bool = Field(default=True, alias="ENABLE_RERANKING")
    reranker_model: str = Field(default="BAAI/bge-reranker-large", alias="RERANKER_MODEL")
    
    enable_query_decomposition: bool = Field(default=True, alias="ENABLE_QUERY_DECOMPOSITION")
    max_subqueries: int = Field(default=3, alias="MAX_SUBQUERIES")
    
    # Semantic chunking
    use_semantic_chunking: bool = Field(default=True, alias="USE_SEMANTIC_CHUNKING")
    semantic_threshold: float = Field(default=0.5, alias="SEMANTIC_THRESHOLD")
    min_chunk_size: int = Field(default=200, alias="MIN_CHUNK_SIZE")
    max_chunk_size: int = Field(default=2000, alias="MAX_CHUNK_SIZE")
    
    # Entity disambiguation
    enable_entity_disambiguation: bool = Field(default=True, alias="ENABLE_ENTITY_DISAMBIGUATION")
    disambiguation_threshold: float = Field(default=0.8, alias="DISAMBIGUATION_THRESHOLD")
    
    # Feedback and learning
    enable_feedback_loop: bool = Field(default=True, alias="ENABLE_FEEDBACK_LOOP")
    feedback_learning_rate: float = Field(default=0.1, alias="FEEDBACK_LEARNING_RATE")
    
    # Caching
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")
    cache_ttl: int = Field(default=3600, alias="CACHE_TTL")
    enable_query_cache: bool = Field(default=True, alias="ENABLE_QUERY_CACHE")
    enable_embedding_cache: bool = Field(default=True, alias="ENABLE_EMBEDDING_CACHE")
    
    # Advanced retrieval features
    enable_hyde: bool = Field(default=True, alias="ENABLE_HYDE")
    enable_query_reformulation: bool = Field(default=True, alias="ENABLE_QUERY_REFORMULATION")
    enable_context_compression: bool = Field(default=True, alias="ENABLE_CONTEXT_COMPRESSION")
    context_compression_ratio: float = Field(default=0.6, alias="CONTEXT_COMPRESSION_RATIO")
    
    # Streaming
    enable_streaming: bool = Field(default=True, alias="ENABLE_STREAMING")
    
    # Advanced accuracy features
    enable_self_consistency: bool = Field(default=True, alias="ENABLE_SELF_CONSISTENCY")
    self_consistency_samples: int = Field(default=3, alias="SELF_CONSISTENCY_SAMPLES")
    
    enable_answer_confidence: bool = Field(default=True, alias="ENABLE_ANSWER_CONFIDENCE")
    min_confidence_threshold: float = Field(default=0.5, alias="MIN_CONFIDENCE_THRESHOLD")
    
    enable_temporal_ranking: bool = Field(default=True, alias="ENABLE_TEMPORAL_RANKING")
    temporal_decay_factor: float = Field(default=0.95, alias="TEMPORAL_DECAY_FACTOR")
    
    enable_citation_extraction: bool = Field(default=True, alias="ENABLE_CITATION_EXTRACTION")
    max_citation_length: int = Field(default=200, alias="MAX_CITATION_LENGTH")
    
    enable_factuality_verification: bool = Field(default=True, alias="ENABLE_FACTUALITY_VERIFICATION")
    
    enable_conflict_resolution: bool = Field(default=True, alias="ENABLE_CONFLICT_RESOLUTION")
    
    enable_query_intent_classification: bool = Field(default=True, alias="ENABLE_QUERY_INTENT_CLASSIFICATION")
    
    enable_iterative_refinement: bool = Field(default=True, alias="ENABLE_ITERATIVE_REFINEMENT")
    max_refinement_iterations: int = Field(default=2, alias="MAX_REFINEMENT_ITERATIONS")
    
    enable_active_learning: bool = Field(default=True, alias="ENABLE_ACTIVE_LEARNING")
    learning_rate: float = Field(default=0.01, alias="LEARNING_RATE")
    
    # Complex reasoning features
    enable_cross_document_synthesis: bool = Field(default=True, alias="ENABLE_CROSS_DOCUMENT_SYNTHESIS")
    enable_comparative_analysis: bool = Field(default=True, alias="ENABLE_COMPARATIVE_ANALYSIS")
    enable_reasoning_chains: bool = Field(default=True, alias="ENABLE_REASONING_CHAINS")
    enable_citation_validation: bool = Field(default=True, alias="ENABLE_CITATION_VALIDATION")
    citation_validation_threshold: float = Field(default=0.8, alias="CITATION_VALIDATION_THRESHOLD")

    # API
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default=["*"])


# Cache the settings instance at module level
# This provides caching but will be reloaded when uvicorn reloads the module
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get settings instance with module-level caching."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
