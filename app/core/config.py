"""Core configuration settings for the Smart RAG application."""

from functools import lru_cache
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
    openai_max_tokens: int = Field(default=2000, alias="OPENAI_MAX_TOKENS")

    # Neo4j
    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(..., alias="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", alias="NEO4J_DATABASE")

    # Document Processing
    chunk_size: int = Field(default=1000, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, alias="CHUNK_OVERLAP")
    max_entities_per_chunk: int = Field(default=50, alias="MAX_ENTITIES_PER_CHUNK")

    # Graph Construction
    min_community_size: int = Field(default=3, alias="MIN_COMMUNITY_SIZE")
    max_hierarchy_levels: int = Field(default=3, alias="MAX_HIERARCHY_LEVELS")
    similarity_threshold: float = Field(default=0.7, alias="SIMILARITY_THRESHOLD")

    # RAG Settings
    top_k_retrieval: int = Field(default=10, alias="TOP_K_RETRIEVAL")
    rerank_top_k: int = Field(default=5, alias="RERANK_TOP_K")
    max_context_length: int = Field(default=4000, alias="MAX_CONTEXT_LENGTH")

    # API
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default=["*"])


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
