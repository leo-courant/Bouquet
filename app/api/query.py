"""API endpoints for querying the knowledge graph."""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from app.core import get_neo4j_repository, get_query_engine
from app.domain import QueryRequest, QueryResponse, SearchRequest, SearchResponse
from app.repositories import Neo4jRepository
from app.services import QueryEngine

router = APIRouter(prefix="/query", tags=["query"])


@router.post("/", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    query_engine: QueryEngine = Depends(get_query_engine),
) -> QueryResponse:
    """Ask a question and get an AI-generated answer with sources."""
    try:
        response = await query_engine.query(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters,
            max_context_length=request.max_context_length,
        )

        # Optionally exclude sources if requested
        if not request.include_sources:
            response.sources = []

        return response

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}",
        )


@router.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    query_engine: QueryEngine = Depends(get_query_engine),
) -> SearchResponse:
    """Search for relevant information without generating an answer."""
    try:
        results = await query_engine.search(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters,
        )

        return SearchResponse(
            results=results,
            total_results=len(results),
            query=request.query,
        )

    except Exception as e:
        logger.error(f"Error processing search: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing search: {str(e)}",
        )


@router.get("/entities/{entity_name}/related", response_model=list[dict])
async def get_related_entities(
    entity_name: str,
    max_hops: int = 2,
    query_engine: QueryEngine = Depends(get_query_engine),
) -> list[dict]:
    """Get entities related to a specific entity."""
    try:
        related = await query_engine.get_related_entities(entity_name, max_hops)
        return related

    except Exception as e:
        logger.error(f"Error getting related entities: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting related entities: {str(e)}",
        )
