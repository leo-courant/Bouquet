"""Core module initialization."""

from app.core.config import Settings, get_settings
from app.core.dependencies import (
    get_active_learner,
    get_advanced_query_engine,
    get_document_processor,
    get_embedding_service,
    get_enhanced_document_processor,
    get_entity_disambiguator,
    get_entity_extractor,
    get_feedback_service,
    get_graph_builder,
    get_neo4j_repository,
    get_query_engine,
    get_ultra_advanced_query_engine,
    get_query_complexity_analyzer,
)
from app.core.logging import setup_logging

__all__ = [
    "Settings",
    "get_settings",
    "setup_logging",
    "get_neo4j_repository",
    "get_embedding_service",
    "get_entity_extractor",
    "get_entity_disambiguator",
    "get_document_processor",
    "get_enhanced_document_processor",
    "get_graph_builder",
    "get_query_engine",
    "get_advanced_query_engine",
    "get_ultra_advanced_query_engine",
    "get_feedback_service",
    "get_active_learner",
    "get_query_complexity_analyzer",
]
