"""Tests for document processor."""

import pytest

from app.domain import Document
from app.services.document_processor import DocumentProcessor


@pytest.fixture
def sample_document():
    """Create a sample document."""
    return Document(
        title="Test Document",
        content="This is a test document. " * 100,  # Repeat to create multiple chunks
    )


@pytest.fixture
def document_processor(embedding_service, entity_extractor):
    """Create document processor fixture."""
    return DocumentProcessor(
        embedding_service=embedding_service,
        entity_extractor=entity_extractor,
        chunk_size=100,
        chunk_overlap=20,
    )


def test_create_chunks(document_processor, sample_document):
    """Test chunking functionality."""
    chunks = document_processor.create_chunks(sample_document)

    assert len(chunks) > 0
    assert all(chunk.document_id == sample_document.id for chunk in chunks)
    assert all(chunk.chunk_index >= 0 for chunk in chunks)
    assert chunks[0].chunk_index == 0
    assert chunks[-1].chunk_index == len(chunks) - 1
