"""Domain models for documents, chunks, and metadata."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Document(BaseModel):
    """Represents a source document."""

    id: UUID = Field(default_factory=uuid4)
    title: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

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

    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }


class Entity(BaseModel):
    """Represents a named entity extracted from text."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    entity_type: str
    description: Optional[str] = None
    chunk_ids: list[UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

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

    class Config:
        json_encoders = {UUID: str}
