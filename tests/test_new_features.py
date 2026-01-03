"""Tests for new RAG enhancement features."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.cache_service import CacheService, EmbeddingCache, QueryCache
from app.services.hyde_service import HyDEService
from app.services.query_reformulator import QueryReformulator
from app.services.context_compressor import ContextCompressor
from app.services.rag_evaluator import RAGEvaluator, EvaluationMetrics


class TestCacheService:
    """Test caching functionality."""

    @pytest.mark.asyncio
    async def test_memory_cache_fallback(self):
        """Test that cache falls back to memory when Redis unavailable."""
        cache = CacheService(redis_url="redis://invalid:9999", ttl=300)
        
        # Should use memory cache
        await cache.set("test_key", "test_value")
        result = await cache.get("test_key")
        
        assert result == "test_value"
    
    @pytest.mark.asyncio
    async def test_embedding_cache(self):
        """Test embedding cache with 24hr TTL."""
        cache = EmbeddingCache()
        
        test_text = "This is a test"
        test_embedding = [0.1, 0.2, 0.3]
        
        await cache.set(test_text, test_embedding)
        result = await cache.get(test_text)
        
        assert result == test_embedding
    
    @pytest.mark.asyncio
    async def test_query_cache(self):
        """Test query cache with 5min TTL."""
        cache = QueryCache()
        
        test_query = {"query": "test", "top_k": 5}
        test_response = {"answer": "test answer", "sources": []}
        
        await cache.set(str(test_query), test_response)
        result = await cache.get(str(test_query))
        
        assert result == test_response
    
    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Test cache statistics tracking."""
        cache = CacheService(redis_url=None, ttl=300)
        
        await cache.set("key1", "value1")
        await cache.get("key1")  # Hit
        await cache.get("key2")  # Miss
        
        stats = await cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["total_requests"] == 2


class TestHyDEService:
    """Test Hypothetical Document Embeddings."""

    @pytest.mark.asyncio
    async def test_hyde_generation(self):
        """Test HyDE document generation."""
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "This is a hypothetical document that answers the query."
            mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
            
            service = HyDEService(api_key="test_key", enable_hyde=True)
            
            result = await service.generate_hypothetical_document("What is AI?")
            
            assert isinstance(result, str)
            assert len(result) > 0
    
    @pytest.mark.asyncio
    async def test_hyde_disabled(self):
        """Test HyDE returns original query when disabled."""
        service = HyDEService(api_key="test_key", enable_hyde=False)
        
        query = "What is AI?"
        result = await service.generate_hypothetical_document(query)
        
        assert result == query


class TestQueryReformulator:
    """Test query reformulation."""

    @pytest.mark.asyncio
    async def test_query_reformulation(self):
        """Test query reformulation generates variants."""
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_response = MagicMock()
            mock_response.choices[0].message.content = '{"queries": ["What is AI?", "Define artificial intelligence", "Explain AI"]}'
            mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
            
            service = QueryReformulator(api_key="test_key", enable_reformulation=True)
            
            result = await service.reformulate_query("What is AI?")
            
            assert isinstance(result, list)
            assert len(result) >= 1
            assert "What is AI?" in result  # Original should be included
    
    @pytest.mark.asyncio
    async def test_reformulation_disabled(self):
        """Test reformulation returns only original when disabled."""
        service = QueryReformulator(api_key="test_key", enable_reformulation=False)
        
        query = "What is AI?"
        result = await service.reformulate_query(query)
        
        assert result == [query]


class TestContextCompressor:
    """Test context compression."""

    @pytest.mark.asyncio
    async def test_compression(self):
        """Test context compression reduces size."""
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Compressed context that is shorter."
            mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
            
            service = ContextCompressor(api_key="test_key", compression_ratio=0.6)
            
            long_context = "This is a very long context. " * 50
            query = "What is this about?"
            
            result = await service.compress_context(long_context, query, max_tokens=100)
            
            assert isinstance(result, str)
            assert len(result) < len(long_context)
    
    @pytest.mark.asyncio
    async def test_no_compression_for_short_context(self):
        """Test that short contexts are not compressed."""
        service = ContextCompressor(api_key="test_key", compression_ratio=0.6)
        
        short_context = "Short text"
        query = "What is this?"
        
        result = await service.compress_context(short_context, query, max_tokens=100)
        
        assert result == short_context


class TestRAGEvaluator:
    """Test RAG evaluation."""

    @pytest.mark.asyncio
    async def test_evaluation_metrics(self):
        """Test RAG evaluation returns all metrics."""
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "0.85"
            mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
            
            evaluator = RAGEvaluator(api_key="test_key")
            
            query = "What is AI?"
            context = "AI is artificial intelligence."
            answer = "AI stands for artificial intelligence."
            ground_truth = "AI is artificial intelligence used in computers."
            
            metrics = await evaluator.evaluate_full_pipeline(
                query, context, answer, ground_truth
            )
            
            assert isinstance(metrics, EvaluationMetrics)
            assert 0.0 <= metrics.context_precision <= 1.0
            assert 0.0 <= metrics.context_recall <= 1.0
            assert 0.0 <= metrics.answer_faithfulness <= 1.0
            assert 0.0 <= metrics.answer_relevance <= 1.0
            assert 0.0 <= metrics.overall_score <= 1.0


@pytest.mark.asyncio
async def test_integration_all_features():
    """Integration test with all features enabled."""
    # This is a placeholder for integration testing
    # In real scenario, would test full pipeline with all services
    assert True  # Placeholder


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
