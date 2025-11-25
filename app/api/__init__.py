"""API router initialization."""

from fastapi import APIRouter

from app.api import documents, graph, query

api_router = APIRouter()

# Include all sub-routers
api_router.include_router(documents.router)
api_router.include_router(query.router)
api_router.include_router(graph.router)

__all__ = ["api_router"]
