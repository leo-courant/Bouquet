"""Integration tests for accuracy improvements."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.query_engine import QueryEngine
from app.services.advanced_query_engine import AdvancedQueryEngine
from app.domain import QueryResponse, SearchResult
from uuid import uuid4


class TestTemperatureSettings:
    """Test that temperature is set to 0.0 for deterministic answers."""

    @pytest.mark.asyncio
    async def test_query_engine_uses_zero_temperature(self):
        """Test QueryEngine uses temperature 0.0."""
        with patch('app.services.query_engine.Neo4jRepository') as mock_repo, \
             patch('app.services.query_engine.EmbeddingService') as mock_embed, \
             patch('openai.AsyncOpenAI') as mock_client:
            
            # Setup mocks
            mock_repo_instance = AsyncMock()
            mock_embed_instance = AsyncMock()
            mock_embed_instance.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
            
            # Mock search results
            search_result = SearchResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                content="Test content about AI",
                score=0.9,
                metadata={},
                entities=[]
            )
            mock_repo_instance.search_similar_chunks = AsyncMock(return_value=[(MagicMock(id=search_result.chunk_id, content=search_result.content, document_id=search_result.document_id, metadata={}), 0.9)])
            mock_repo_instance.get_entities_for_chunk = AsyncMock(return_value=[])
            
            # Mock OpenAI response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "AI is artificial intelligence [Source 1]."
            
            mock_client_instance = MagicMock()
            mock_client_instance.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_client_instance
            
            # Create engine
            engine = QueryEngine(
                repository=mock_repo_instance,
                embedding_service=mock_embed_instance,
                api_key="test_key",
                model="gpt-4-turbo-preview",
                min_similarity_threshold=0.7
            )
            
            # Execute query
            response = await engine.query("What is AI?")
            
            # Verify temperature was set to 0.0
            call_args = mock_client_instance.chat.completions.create.call_args
            assert call_args is not None
            assert call_args.kwargs['temperature'] == 0.0
            assert call_args.kwargs['max_tokens'] == 1000


class TestSimilarityThreshold:
    """Test minimum similarity threshold functionality."""

    @pytest.mark.asyncio
    async def test_rejects_low_similarity_results(self):
        """Test that results below threshold are rejected."""
        with patch('app.services.query_engine.Neo4jRepository') as mock_repo, \
             patch('app.services.query_engine.EmbeddingService') as mock_embed, \
             patch('openai.AsyncOpenAI'):
            
            mock_repo_instance = AsyncMock()
            mock_embed_instance = AsyncMock()
            mock_embed_instance.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
            
            # Mock low similarity results (below 0.7 threshold)
            search_result = SearchResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                content="Irrelevant content",
                score=0.5,  # Below threshold
                metadata={},
                entities=[]
            )
            mock_repo_instance.search_similar_chunks = AsyncMock(return_value=[(MagicMock(id=search_result.chunk_id, content=search_result.content, document_id=search_result.document_id, metadata={}), 0.5)])
            mock_repo_instance.get_entities_for_chunk = AsyncMock(return_value=[])
            
            engine = QueryEngine(
                repository=mock_repo_instance,
                embedding_service=mock_embed_instance,
                api_key="test_key",
                min_similarity_threshold=0.7
            )
            
            response = await engine.query("What is AI?")
            
            # Should return abstention message
            assert "don't have sufficient information" in response.answer.lower() or "not relevant enough" in response.answer.lower()
            assert response.metadata['reason'] == 'below_similarity_threshold'
            assert response.metadata['max_similarity'] == 0.5

    @pytest.mark.asyncio
    async def test_accepts_high_similarity_results(self):
        """Test that results above threshold are accepted."""
        with patch('app.services.query_engine.Neo4jRepository') as mock_repo, \
             patch('app.services.query_engine.EmbeddingService') as mock_embed, \
             patch('openai.AsyncOpenAI') as mock_client:
            
            mock_repo_instance = AsyncMock()
            mock_embed_instance = AsyncMock()
            mock_embed_instance.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
            
            # Mock high similarity results (above 0.7 threshold)
            search_result = SearchResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                content="AI is artificial intelligence",
                score=0.85,  # Above threshold
                metadata={},
                entities=[]
            )
            mock_repo_instance.search_similar_chunks = AsyncMock(return_value=[(MagicMock(id=search_result.chunk_id, content=search_result.content, document_id=search_result.document_id, metadata={}), 0.85)])
            mock_repo_instance.get_entities_for_chunk = AsyncMock(return_value=[])
            
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "AI is artificial intelligence [Source 1]."
            
            mock_client_instance = MagicMock()
            mock_client_instance.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_client_instance
            
            engine = QueryEngine(
                repository=mock_repo_instance,
                embedding_service=mock_embed_instance,
                api_key="test_key",
                min_similarity_threshold=0.7
            )
            
            response = await engine.query("What is AI?")
            
            # Should generate actual answer
            assert "artificial intelligence" in response.answer.lower()
            assert response.metadata.get('reason') != 'below_similarity_threshold'


class TestAnswerValidation:
    """Test answer length and quality validation."""

    @pytest.mark.asyncio
    async def test_answer_word_count_tracked(self):
        """Test that answer word count is tracked in metadata."""
        with patch('app.services.query_engine.Neo4jRepository') as mock_repo, \
             patch('app.services.query_engine.EmbeddingService') as mock_embed, \
             patch('openai.AsyncOpenAI') as mock_client:
            
            mock_repo_instance = AsyncMock()
            mock_embed_instance = AsyncMock()
            mock_embed_instance.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
            
            search_result = SearchResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                content="AI is artificial intelligence",
                score=0.9,
                metadata={},
                entities=[]
            )
            mock_repo_instance.search_similar_chunks = AsyncMock(return_value=[(MagicMock(id=search_result.chunk_id, content=search_result.content, document_id=search_result.document_id, metadata={}), 0.9)])
            mock_repo_instance.get_entities_for_chunk = AsyncMock(return_value=[])
            
            # Mock a 20-word answer
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            twenty_word_answer = "Artificial intelligence is the simulation of human intelligence processes by machines especially computer systems [Source 1]. These processes include learning reasoning and self-correction."
            mock_response.choices[0].message.content = twenty_word_answer
            
            mock_client_instance = MagicMock()
            mock_client_instance.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_client_instance
            
            engine = QueryEngine(
                repository=mock_repo_instance,
                embedding_service=mock_embed_instance,
                api_key="test_key",
            )
            
            response = await engine.query("What is AI?")
            
            # Verify word count is tracked
            assert 'answer_word_count' in response.metadata
            assert response.metadata['answer_word_count'] >= 15


class TestCitationEnforcement:
    """Test that citations are enforced in system prompts."""

    @pytest.mark.asyncio
    async def test_system_prompt_requires_citations(self):
        """Test that system prompt explicitly requires citations."""
        with patch('app.services.query_engine.Neo4jRepository') as mock_repo, \
             patch('app.services.query_engine.EmbeddingService') as mock_embed, \
             patch('openai.AsyncOpenAI') as mock_client:
            
            mock_repo_instance = AsyncMock()
            mock_embed_instance = AsyncMock()
            mock_embed_instance.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
            
            search_result = SearchResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                content="AI is artificial intelligence",
                score=0.9,
                metadata={},
                entities=[]
            )
            mock_repo_instance.search_similar_chunks = AsyncMock(return_value=[(MagicMock(id=search_result.chunk_id, content=search_result.content, document_id=search_result.document_id, metadata={}), 0.9)])
            mock_repo_instance.get_entities_for_chunk = AsyncMock(return_value=[])
            
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "AI is artificial intelligence [Source 1]."
            
            mock_client_instance = MagicMock()
            mock_client_instance.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_client_instance
            
            engine = QueryEngine(
                repository=mock_repo_instance,
                embedding_service=mock_embed_instance,
                api_key="test_key",
            )
            
            await engine.query("What is AI?")
            
            # Check that system prompt mentions citations
            call_args = mock_client_instance.chat.completions.create.call_args
            system_message = call_args.kwargs['messages'][0]['content']
            
            assert 'CRITICAL' in system_message or 'MUST' in system_message
            assert '[Source' in system_message or 'cite' in system_message.lower()


class TestConfigurationDefaults:
    """Test that configuration defaults are set correctly."""

    def test_max_context_length_increased(self):
        """Test that max_context_length default is 8000."""
        from app.core.config import Settings
        settings = Settings(
            openai_api_key="test",
            neo4j_password="test"
        )
        assert settings.max_context_length == 8000

    def test_max_tokens_set_to_1000(self):
        """Test that max_tokens default is 1000."""
        from app.core.config import Settings
        settings = Settings(
            openai_api_key="test",
            neo4j_password="test"
        )
        assert settings.openai_max_tokens == 1000

    def test_min_similarity_threshold_set(self):
        """Test that min_similarity_threshold is set to 0.7."""
        from app.core.config import Settings
        settings = Settings(
            openai_api_key="test",
            neo4j_password="test"
        )
        assert settings.min_similarity_threshold == 0.7

    def test_all_ultra_features_enabled_by_default(self):
        """Test that all ultra-advanced features are enabled."""
        from app.core.config import Settings
        settings = Settings(
            openai_api_key="test",
            neo4j_password="test"
        )
        
        assert settings.enable_self_consistency is True
        assert settings.enable_answer_confidence is True
        assert settings.enable_factuality_verification is True
        assert settings.enable_citation_extraction is True
        assert settings.enable_conflict_resolution is True
        assert settings.enable_query_intent_classification is True
        assert settings.enable_iterative_refinement is True
        assert settings.enable_temporal_ranking is True
        assert settings.enable_hyde is True
        assert settings.enable_query_reformulation is True
        assert settings.enable_context_compression is True
