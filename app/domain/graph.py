"""Domain models for graph structures."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    """Represents a node in the knowledge graph."""

    id: UUID = Field(default_factory=uuid4)
    node_type: str  # entity, chunk, community, etc.
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[list[float]] = None
    level: int = 0  # Hierarchy level in graph-of-graphs
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }


class GraphEdge(BaseModel):
    """Represents an edge in the knowledge graph."""

    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    target_id: UUID
    edge_type: str
    weight: float = 1.0
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }


class Community(BaseModel):
    """Represents a detected community in the graph."""

    id: UUID = Field(default_factory=uuid4)
    level: int  # Hierarchy level
    members: list[UUID]  # Node IDs in this community
    summary: Optional[str] = None
    embedding: Optional[list[float]] = None
    parent_community_id: Optional[UUID] = None
    child_community_ids: list[UUID] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }


class GraphStats(BaseModel):
    """Statistics about the knowledge graph."""

    total_nodes: int = 0
    total_edges: int = 0
    total_communities: int = 0
    nodes_by_type: dict[str, int] = Field(default_factory=dict)
    edges_by_type: dict[str, int] = Field(default_factory=dict)
    communities_by_level: dict[int, int] = Field(default_factory=dict)
    avg_degree: float = 0.0
    density: float = 0.0
