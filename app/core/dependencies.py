"""Core dependency injection for FastAPI."""

from typing import AsyncGenerator

from app.core.config import Settings, get_settings
from app.repositories.neo4j_repository import Neo4jRepository
from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import EmbeddingService
from app.services.entity_extractor import EntityExtractor
from app.services.graph_builder import GraphBuilder
from app.services.query_engine import QueryEngine


async def get_neo4j_repository() -> AsyncGenerator[Neo4jRepository, None]:
    """Get Neo4j repository instance."""
    settings = get_settings()
    repository = Neo4jRepository(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
    )
    await repository.connect()
    try:
        yield repository
    finally:
        await repository.close()


async def get_embedding_service() -> EmbeddingService:
    """Get embedding service instance."""
    settings = get_settings()
    return EmbeddingService(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
    )


async def get_entity_extractor() -> EntityExtractor:
    """Get entity extractor instance."""
    settings = get_settings()
    return EntityExtractor(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_entities=settings.max_entities_per_chunk,
    )


async def get_document_processor(
    embedding_service: EmbeddingService = None,
    entity_extractor: EntityExtractor = None,
) -> DocumentProcessor:
    """Get document processor instance."""
    settings = get_settings()
    if embedding_service is None:
        embedding_service = await get_embedding_service()
    if entity_extractor is None:
        entity_extractor = await get_entity_extractor()

    return DocumentProcessor(
        embedding_service=embedding_service,
        entity_extractor=entity_extractor,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )


async def get_graph_builder(
    repository: Neo4jRepository = None,
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
    repository: Neo4jRepository = None,
    embedding_service: EmbeddingService = None,
) -> QueryEngine:
    """Get query engine instance."""
    settings = get_settings()
    if embedding_service is None:
        embedding_service = await get_embedding_service()

    return QueryEngine(
        repository=repository,
        embedding_service=embedding_service,
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        top_k=settings.top_k_retrieval,
        rerank_top_k=settings.rerank_top_k,
        max_context_length=settings.max_context_length,
    )
