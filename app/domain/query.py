"""Domain models for query and retrieval."""

from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RetrievalStrategy(str, Enum):
    """Strategy for retrieving chunks."""
    VECTOR_ONLY = "vector_only"
    HYBRID = "hybrid"  # Vector + BM25
    ENTITY_AWARE = "entity_aware"  # Entity-guided
    GRAPH_TRAVERSAL = "graph_traversal"  # Multi-hop with semantic relationships
    SEMANTIC_RELATIONSHIP = "semantic_relationship"  # Follow ELABORATES, SUPPORTS, etc.
    COMMUNITY_BASED = "community_based"  # Community-aware
    ADAPTIVE = "adaptive"  # Auto-select best strategy


class QueryType(str, Enum):
    """Type of query for routing."""
    FACTUAL = "factual"  # Simple fact lookup
    ANALYTICAL = "analytical"  # Requires reasoning
    COMPARATIVE = "comparative"  # Compare entities
    EXPLORATORY = "exploratory"  # Broad discovery
    TEMPORAL = "temporal"  # Time-based queries


class QueryRequest(BaseModel):
    """Request model for querying the RAG system."""

    query: str
    top_k: Optional[int] = None
    filters: dict[str, Any] = Field(default_factory=dict)
    include_sources: bool = True
    max_context_length: Optional[int] = None
    
    # New advanced options
    strategy: RetrievalStrategy = RetrievalStrategy.ADAPTIVE
    use_reranking: bool = True
    use_entity_expansion: bool = True
    use_community_context: bool = True
    max_hops: int = 2  # For graph traversal
    enable_feedback: bool = True  # Track for feedback loop


class SearchResult(BaseModel):
    """Single search result."""

    chunk_id: UUID
    document_id: UUID
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    entities: list[str] = Field(default_factory=list)
    
    # New enhanced fields
    rerank_score: Optional[float] = None
    vector_score: Optional[float] = None
    bm25_score: Optional[float] = None
    entity_overlap_score: Optional[float] = None
    community_ids: list[UUID] = Field(default_factory=list)
    related_chunks: list[UUID] = Field(default_factory=list)
    reasoning_path: Optional[list[dict]] = None  # For multi-hop

    class Config:
        json_encoders = {UUID: str}


class QueryResponse(BaseModel):
    """Response model for query results."""

    answer: str
    sources: list[SearchResult] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    # New fields
    query_type: Optional[QueryType] = None
    decomposed_queries: list[str] = Field(default_factory=list)
    retrieved_entities: list[dict] = Field(default_factory=list)
    confidence: Optional[float] = None

    class Config:
        json_encoders = {UUID: str}
        # Ensure model can be serialized
        use_enum_values = True


class SearchRequest(BaseModel):
    """Request model for semantic search without generation."""

    query: str
    top_k: Optional[int] = None
    filters: dict[str, Any] = Field(default_factory=dict)
    strategy: RetrievalStrategy = RetrievalStrategy.ADAPTIVE


class SearchResponse(BaseModel):
    """Response model for search results."""

    results: list[SearchResult]
    total_results: int
    query: str
    strategy_used: Optional[RetrievalStrategy] = None


class FeedbackRequest(BaseModel):
    """Request model for relevance feedback."""
    
    query: str
    chunk_id: UUID
    helpful: bool
    rating: Optional[int] = Field(None, ge=1, le=5)  # 1-5 star rating
    feedback_text: Optional[str] = None


class SubQuery(BaseModel):
    """Decomposed sub-query."""
    
    query: str
    query_type: QueryType
    dependencies: list[int] = Field(default_factory=list)  # Indices of dependent queries
    priority: int = 1
