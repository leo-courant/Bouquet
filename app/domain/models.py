"""Domain models for documents, chunks, and metadata."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ChunkRelationType(str, Enum):
    """Types of relationships between chunks."""
    FOLLOWS = "FOLLOWS"  # Sequential chunks
    REFERENCES = "REFERENCES"  # Cross-references
    CONTRADICTS = "CONTRADICTS"  # Conflicting information
    ELABORATES = "ELABORATES"  # Detailed explanation
    SUPPORTS = "SUPPORTS"  # Supporting evidence
    PRECEDES = "PRECEDES"  # Temporal precedence


class EntityRole(str, Enum):
    """Role of entity in a chunk."""
    SUBJECT = "SUBJECT"  # Main subject
    OBJECT = "OBJECT"  # Object of action
    CONTEXT = "CONTEXT"  # Contextual mention
    ATTRIBUTE = "ATTRIBUTE"  # Attribute or property


class Document(BaseModel):
    """Represents a source document."""

    id: UUID = Field(default_factory=uuid4)
    title: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None
    summary: Optional[str] = None  # Document-level summary
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = 1  # For versioning

    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }


class Chunk(BaseModel):
    """Represents a text chunk from a document."""

    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    content: str
    embedding: Optional[list[float]] = None
    chunk_index: int
    start_char: int
    end_char: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # New fields for advanced features
    summary: Optional[str] = None  # Chunk summary
    topic: Optional[str] = None  # Main topic
    parent_chunk_id: Optional[UUID] = None  # For hierarchical chunks
    semantic_density: float = 1.0  # Content density score
    
    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }


class ChunkRelationship(BaseModel):
    """Represents a relationship between two chunks."""
    
    id: UUID = Field(default_factory=uuid4)
    source_chunk_id: UUID
    target_chunk_id: UUID
    relation_type: ChunkRelationType
    weight: float = 1.0
    description: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {UUID: str}


class Entity(BaseModel):
    """Represents a named entity extracted from text."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    entity_type: str
    description: Optional[str] = None
    chunk_ids: list[UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    # New fields for disambiguation and tracking
    canonical_name: Optional[str] = None  # Standardized name
    aliases: list[str] = Field(default_factory=list)  # Alternative names
    confidence: float = 1.0  # Extraction confidence
    disambiguation_context: Optional[str] = None  # Context for disambiguation
    summary: Optional[str] = None  # Aggregated entity summary
    first_seen: Optional[datetime] = None  # Temporal tracking
    last_seen: Optional[datetime] = None

    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }


class EntityMention(BaseModel):
    """Represents a specific mention of an entity in a chunk."""
    
    id: UUID = Field(default_factory=uuid4)
    entity_id: UUID
    chunk_id: UUID
    mention_text: str  # Actual text in chunk
    role: EntityRole = EntityRole.CONTEXT
    salience: float = 0.5  # Importance score (0-1)
    sentiment: Optional[float] = None  # Sentiment (-1 to 1)
    position: int = 0  # Position in chunk
    confidence: float = 1.0
    
    class Config:
        json_encoders = {UUID: str}


class Relationship(BaseModel):
    """Represents a relationship between two entities."""

    id: UUID = Field(default_factory=uuid4)
    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: str
    description: Optional[str] = None
    weight: float = 1.0
    chunk_ids: list[UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    # New fields for advanced relationships
    confidence: float = 1.0
    temporal_start: Optional[datetime] = None
    temporal_end: Optional[datetime] = None
    bidirectional: bool = False
    attributes: dict[str, Any] = Field(default_factory=dict)  # For n-ary relations

    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }
