"""Test configuration and fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.embedding_service import EmbeddingService
from app.services.entity_extractor import EntityExtractor


@pytest.fixture
def embedding_service():
    """Mock embedding service."""
    service = MagicMock(spec=EmbeddingService)
    service.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
    service.generate_embeddings = AsyncMock(return_value=[[0.1] * 1536])
    service.compute_similarity = AsyncMock(return_value=0.8)
    return service


@pytest.fixture
def entity_extractor():
    """Mock entity extractor."""
    extractor = MagicMock(spec=EntityExtractor)
    extractor.extract_entities_and_relationships = AsyncMock(return_value=([], []))
    extractor.generate_summary = AsyncMock(return_value="Test summary")
    return extractor
