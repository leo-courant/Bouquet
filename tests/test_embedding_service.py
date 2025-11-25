"""Tests for embedding service."""

import pytest

from app.services.embedding_service import EmbeddingService


@pytest.fixture
def embedding_service():
    """Create embedding service fixture."""
    return EmbeddingService(
        api_key="test-key",
        model="text-embedding-3-large",
    )


@pytest.mark.asyncio
async def test_compute_similarity(embedding_service):
    """Test similarity computation."""
    vec1 = [1.0, 0.0, 0.0]
    vec2 = [1.0, 0.0, 0.0]
    vec3 = [0.0, 1.0, 0.0]

    similarity_same = await embedding_service.compute_similarity(vec1, vec2)
    assert similarity_same == pytest.approx(1.0)

    similarity_diff = await embedding_service.compute_similarity(vec1, vec3)
    assert similarity_diff == pytest.approx(0.0)
