"""API endpoints for querying the knowledge graph."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
import json
from typing import Optional
from pydantic import BaseModel

from app.core import (
    get_advanced_query_engine,
    get_feedback_service,
    get_neo4j_repository,
    get_query_engine,
    get_ultra_advanced_query_engine,
    get_active_learner,
)
from app.domain import QueryRequest, QueryResponse, SearchRequest, SearchResponse
from app.domain.query import FeedbackRequest, RetrievalStrategy, QueryType, SubQuery
from app.repositories import Neo4jRepository
from app.services import QueryEngine
from app.services.advanced_query_engine import AdvancedQueryEngine
from app.services.ultra_advanced_query_engine import UltraAdvancedQueryEngine
from app.services.feedback_service import FeedbackService
from app.services.active_learner import ActiveLearner

router = APIRouter(prefix="/query", tags=["query"])


@router.post("/", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    query_engine: QueryEngine = Depends(get_query_engine),
) -> QueryResponse:
    """Ask a question and get an AI-generated answer with sources (legacy endpoint)."""
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


@router.post("/advanced", response_model=QueryResponse)
async def advanced_query(
    request: QueryRequest,
    query_engine: AdvancedQueryEngine = Depends(get_advanced_query_engine),
) -> QueryResponse:
    """Ask a question using advanced retrieval strategies."""
    try:
        response = await query_engine.query(
            query=request.query,
            top_k=request.top_k,
            strategy=request.strategy,
            use_reranking=request.use_reranking,
            use_entity_expansion=request.use_entity_expansion,
            use_community_context=request.use_community_context,
            max_hops=request.max_hops,
            enable_feedback=request.enable_feedback,
        )

        # Optionally exclude sources if requested
        if not request.include_sources:
            response.sources = []

        return response

    except Exception as e:
        logger.error(f"Error processing advanced query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing advanced query: {str(e)}",
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


@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    feedback_service: FeedbackService = Depends(get_feedback_service),
) -> dict:
    """Submit relevance feedback for a query result."""
    try:
        feedback_service.record_feedback(
            query=request.query,
            chunk_id=request.chunk_id,
            helpful=request.helpful,
            rating=request.rating,
            feedback_text=request.feedback_text,
        )
        
        return {
            "status": "success",
            "message": "Feedback recorded successfully",
        }

    except Exception as e:
        logger.error(f"Error recording feedback: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error recording feedback: {str(e)}",
        )


@router.get("/feedback/stats")
async def get_feedback_stats(
    feedback_service: FeedbackService = Depends(get_feedback_service),
) -> dict:
    """Get feedback statistics."""
    try:
        return feedback_service.get_statistics()
    except Exception as e:
        logger.error(f"Error getting feedback stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting feedback stats: {str(e)}",
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


@router.post("/stream")
async def stream_query(
    request: QueryRequest,
    query_engine: AdvancedQueryEngine = Depends(get_advanced_query_engine),
):
    """Stream answer generation for a query using Server-Sent Events."""
    try:
        async def generate():
            """Generator for streaming response."""
            # Step 1: Retrieve context (same as regular query but without caching)
            subqueries = [SubQuery(query=request.query, query_type=QueryType.FACTUAL, priority=1)]
            if query_engine.query_decomposer and query_engine.query_decomposer.should_decompose(request.query):
                subqueries = await query_engine.query_decomposer.decompose_query(request.query)
            
            # Step 2: Query reformulation
            query_variants = [request.query]
            if query_engine.query_reformulator:
                query_variants = await query_engine.query_reformulator.reformulate_query(request.query)
            
            # Step 3: Retrieve results
            all_results = []
            for subquery in subqueries:
                for query_variant in query_variants:
                    search_query = query_variant
                    if query_engine.hyde_service:
                        hyde_doc = await query_engine.hyde_service.generate_hypothetical_document(query_variant)
                        if hyde_doc != query_variant:
                            search_query = hyde_doc
                    
                    results = await query_engine._retrieve(
                        search_query,
                        request.top_k or query_engine.top_k,
                        request.strategy or RetrievalStrategy.ADAPTIVE,
                        request.use_entity_expansion,
                        request.use_community_context,
                        request.max_hops or 2,
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
                yield f"data: {json.dumps({'error': 'No relevant information found'})}\n\n"
                return
            
            # Reranking
            if request.use_reranking and query_engine.reranker:
                unique_results = query_engine.reranker.rerank_search_results(
                    request.query, unique_results, top_k=query_engine.rerank_top_k
                )
            
            # Build context
            context = query_engine._build_context(unique_results)
            
            # Compress if needed
            if query_engine.context_compressor and len(context) > query_engine.max_context_length:
                compressed = await query_engine.context_compressor.compress_context(
                    context, request.query, max_tokens=query_engine.max_context_length // 4
                )
                if compressed:
                    context = compressed
            
            # Send sources first
            sources_data = {
                "type": "sources",
                "sources": [
                    {
                        "chunk_id": str(r.chunk_id),
                        "content": r.content[:200] + "..." if len(r.content) > 200 else r.content,
                        "score": r.score,
                        "entities": r.entities,
                    }
                    for r in unique_results[:query_engine.rerank_top_k]
                ]
            }
            yield f"data: {json.dumps(sources_data)}\n\n"
            
            # Stream answer tokens
            async for token in query_engine.stream_answer(request.query, context, subqueries):
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
            
            # Send completion signal
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    
    except Exception as e:
        logger.error(f"Error streaming query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error streaming query: {str(e)}",
        )


@router.post("/ultra", response_model=QueryResponse)
async def ultra_advanced_query(
    request: QueryRequest,
    query_engine: UltraAdvancedQueryEngine = Depends(get_ultra_advanced_query_engine),
) -> QueryResponse:
    """
    Ask a question using ultra-advanced query engine with maximum accuracy features.
    
    This endpoint includes:
    - Self-consistency verification
    - Answer confidence scoring
    - Temporal-aware ranking
    - Precise citation extraction
    - Factuality verification
    - Conflict resolution
    - Query intent classification
    - Iterative refinement
    - Active learning
    """
    try:
        response = await query_engine.query(
            query=request.query,
            top_k=request.top_k,
            strategy=request.strategy,
            use_reranking=request.use_reranking,
            use_entity_expansion=request.use_entity_expansion,
            use_community_context=request.use_community_context,
            max_hops=request.max_hops,
            enable_feedback=request.enable_feedback,
        )

        # Optionally exclude sources if requested
        if not request.include_sources:
            response.sources = []

        return response

    except Exception as e:
        logger.error(f"Error processing ultra-advanced query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing ultra-advanced query: {str(e)}",
        )


class UserFeedback(BaseModel):
    """User feedback for a query response."""
    query: str
    rating: int  # 1-5 scale
    helpful: bool
    feedback_text: Optional[str] = None
    response_metadata: dict  # Metadata from the query response


@router.post("/feedback")
async def submit_feedback(
    feedback: UserFeedback,
    query_engine: UltraAdvancedQueryEngine = Depends(get_ultra_advanced_query_engine),
    active_learner: ActiveLearner = Depends(get_active_learner),
) -> dict:
    """
    Submit user feedback for active learning.
    
    This helps the system learn which strategies and entities work best.
    """
    try:
        # Create a mock response object for recording feedback
        from app.domain import QueryResponse
        
        response = QueryResponse(
            answer="",  # Not needed for feedback
            sources=[],
            metadata=feedback.response_metadata,
        )
        
        # Record feedback
        await query_engine.record_feedback(
            query=feedback.query,
            response=response,
            rating=feedback.rating,
            helpful=feedback.helpful,
            feedback_text=feedback.feedback_text,
        )
        
        logger.info(f"Feedback recorded: rating={feedback.rating}, helpful={feedback.helpful}")
        
        return {
            "status": "success",
            "message": "Feedback recorded successfully"
        }
    
    except Exception as e:
        logger.error(f"Error recording feedback: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error recording feedback: {str(e)}",
        )


@router.get("/learning/report")
async def get_learning_report(
    active_learner: ActiveLearner = Depends(get_active_learner),
) -> dict:
    """
    Get performance report from active learning.
    
    Shows which strategies, entities, and query patterns perform best.
    """
    try:
        report = active_learner.get_performance_report()
        return {
            "status": "success",
            "report": report
        }
    
    except Exception as e:
        logger.error(f"Error generating learning report: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating learning report: {str(e)}",
        )
