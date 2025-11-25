"""Domain models for query and retrieval."""

from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request model for querying the RAG system."""

    query: str
    top_k: Optional[int] = None
    filters: dict[str, Any] = Field(default_factory=dict)
    include_sources: bool = True
    max_context_length: Optional[int] = None


class SearchResult(BaseModel):
    """Single search result."""

    chunk_id: UUID
    document_id: UUID
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    entities: list[str] = Field(default_factory=list)

    class Config:
        json_encoders = {UUID: str}


class QueryResponse(BaseModel):
    """Response model for query results."""

    answer: str
    sources: list[SearchResult] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchRequest(BaseModel):
    """Request model for semantic search without generation."""

    query: str
    top_k: Optional[int] = None
    filters: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Response model for search results."""

    results: list[SearchResult]
    total_results: int
    query: str
