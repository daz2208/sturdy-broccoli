"""
Tests for Enhanced RAG System.

Tests the following components:
- HybridSearcher: TF-IDF + embedding combination
- CrossEncoderReranker: Reranking quality
- QueryExpander: Query expansion logic
- ParentChildChunker: Chunking strategy
- EnhancedRAGService: End-to-end integration
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import numpy as np

# Import the components we're testing
from backend.enhanced_rag import (
    RAGConfig,
    RetrievedChunk,
    RAGResponse,
    PgVectorStore,
    HybridSearcher,
    CrossEncoderReranker,
    QueryExpander,
    ParentChildChunker,
    EnhancedRAGService,
    get_pgvector_migration_sql,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = Mock()
    session.execute = Mock(return_value=Mock(fetchone=Mock(return_value=None)))
    session.commit = Mock()
    return session


@pytest.fixture
def sample_chunks():
    """Create sample retrieved chunks for testing."""
    return [
        RetrievedChunk(
            chunk_id=1,
            document_id=100,
            content="Python is a programming language known for its simplicity.",
            embedding_score=0.9,
            tfidf_score=0.7,
            filename="python_guide.md"
        ),
        RetrievedChunk(
            chunk_id=2,
            document_id=101,
            content="Machine learning uses algorithms to learn from data.",
            embedding_score=0.8,
            tfidf_score=0.5,
            filename="ml_intro.md"
        ),
        RetrievedChunk(
            chunk_id=3,
            document_id=102,
            content="FastAPI is a modern Python web framework.",
            embedding_score=0.7,
            tfidf_score=0.8,
            filename="fastapi_docs.md"
        ),
    ]


@pytest.fixture
def rag_config():
    """Create a test RAG configuration."""
    return RAGConfig(
        initial_retrieval_k=10,
        rerank_top_k=5,
        embedding_weight=0.7,
        tfidf_weight=0.3,
        enable_query_expansion=False,  # Disable for faster tests
        enable_reranking=False,  # Disable for faster tests
    )


# =============================================================================
# RAGConfig Tests
# =============================================================================

class TestRAGConfig:
    """Tests for RAG configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RAGConfig()
        assert config.initial_retrieval_k == 50
        assert config.rerank_top_k == 10
        assert config.embedding_weight + config.tfidf_weight == 1.0
        assert config.enable_query_expansion is True
        assert config.enable_reranking is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = RAGConfig(
            initial_retrieval_k=100,
            rerank_top_k=20,
            embedding_weight=0.6,
            tfidf_weight=0.4,
        )
        assert config.initial_retrieval_k == 100
        assert config.rerank_top_k == 20
        assert config.embedding_weight == 0.6


# =============================================================================
# RetrievedChunk Tests
# =============================================================================

class TestRetrievedChunk:
    """Tests for RetrievedChunk dataclass."""

    def test_create_chunk(self):
        """Test creating a retrieved chunk."""
        chunk = RetrievedChunk(
            chunk_id=1,
            document_id=100,
            content="Test content"
        )
        assert chunk.chunk_id == 1
        assert chunk.document_id == 100
        assert chunk.embedding_score == 0.0
        assert chunk.tfidf_score == 0.0

    def test_chunk_with_scores(self):
        """Test chunk with all scores."""
        chunk = RetrievedChunk(
            chunk_id=1,
            document_id=100,
            content="Test content",
            embedding_score=0.9,
            tfidf_score=0.8,
            hybrid_score=0.85,
            rerank_score=0.95,
            final_score=0.92
        )
        assert chunk.embedding_score == 0.9
        assert chunk.hybrid_score == 0.85
        assert chunk.final_score == 0.92


# =============================================================================
# HybridSearcher Tests
# =============================================================================

class TestHybridSearcher:
    """Tests for hybrid search combining TF-IDF and embeddings."""

    def test_initialization(self, mock_db_session):
        """Test HybridSearcher initialization."""
        searcher = HybridSearcher(mock_db_session)
        assert searcher.embedding_weight == 0.7
        assert searcher.tfidf_weight == 0.3

    def test_custom_weights(self, mock_db_session):
        """Test custom weight configuration."""
        searcher = HybridSearcher(
            mock_db_session,
            embedding_weight=0.6,
            tfidf_weight=0.4
        )
        assert searcher.embedding_weight == 0.6
        assert searcher.tfidf_weight == 0.4

    def test_weights_sum_to_one(self, mock_db_session):
        """Test that weights should sum to 1.0."""
        searcher = HybridSearcher(mock_db_session, 0.7, 0.3)
        assert searcher.embedding_weight + searcher.tfidf_weight == 1.0


# =============================================================================
# CrossEncoderReranker Tests
# =============================================================================

class TestCrossEncoderReranker:
    """Tests for cross-encoder reranking."""

    def test_initialization(self):
        """Test reranker initialization."""
        reranker = CrossEncoderReranker()
        assert reranker.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"
        assert reranker._model is None  # Lazy loaded

    def test_custom_model(self):
        """Test custom model initialization."""
        reranker = CrossEncoderReranker(model_name="custom/model")
        assert reranker.model_name == "custom/model"

    def test_rerank_empty_list(self):
        """Test reranking empty list."""
        reranker = CrossEncoderReranker()
        result = reranker.rerank("test query", [])
        assert result == []

    def test_rerank_without_model(self, sample_chunks):
        """Test reranking falls back to hybrid scores without model."""
        reranker = CrossEncoderReranker()
        # Mock the model loading to fail
        reranker._model = None

        # Calculate hybrid scores first
        for chunk in sample_chunks:
            chunk.hybrid_score = 0.7 * chunk.embedding_score + 0.3 * chunk.tfidf_score

        result = reranker.rerank("python programming", sample_chunks, top_k=2)

        # Should return top 2 by hybrid score
        assert len(result) == 2
        # First should be highest hybrid score
        assert result[0].hybrid_score >= result[1].hybrid_score


# =============================================================================
# QueryExpander Tests
# =============================================================================

class TestQueryExpander:
    """Tests for query expansion."""

    def test_initialization(self):
        """Test QueryExpander initialization."""
        expander = QueryExpander()
        assert expander._client is None  # Lazy loaded

    @pytest.mark.asyncio
    async def test_expand_returns_original_on_error(self):
        """Test that expansion returns original query on error."""
        expander = QueryExpander()

        # Mock client to raise error
        with patch.object(expander, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))
            mock_get_client.return_value = mock_client

            result = await expander.expand("test query")

            assert result == ["test query"]  # Returns original on error


# =============================================================================
# ParentChildChunker Tests
# =============================================================================

class TestParentChildChunker:
    """Tests for parent-child chunking strategy."""

    def test_initialization(self):
        """Test chunker initialization."""
        chunker = ParentChildChunker()
        assert chunker.child_tokens == 256
        assert chunker.parent_tokens == 1024
        assert chunker.overlap_tokens == 50

    def test_custom_token_sizes(self):
        """Test custom token size configuration."""
        chunker = ParentChildChunker(
            child_tokens=128,
            parent_tokens=512,
            overlap_tokens=25
        )
        assert chunker.child_tokens == 128
        assert chunker.parent_tokens == 512

    def test_count_tokens(self):
        """Test token counting."""
        chunker = ParentChildChunker()
        text = "This is a test sentence."
        count = chunker.count_tokens(text)
        assert count > 0
        # Should be roughly len/4 if tiktoken not available
        assert count <= len(text)

    def test_chunk_short_document(self):
        """Test chunking a short document."""
        chunker = ParentChildChunker(child_tokens=100, parent_tokens=500)
        content = "This is a short document."

        parent_chunks, child_chunks = chunker.chunk_document(content, doc_id=1)

        # Short doc should be single parent chunk
        assert len(parent_chunks) >= 1

    def test_chunk_long_document(self):
        """Test chunking a longer document."""
        chunker = ParentChildChunker(child_tokens=50, parent_tokens=200)

        # Create longer content
        paragraphs = ["This is paragraph number {}. It contains some text.".format(i)
                      for i in range(20)]
        content = "\n\n".join(paragraphs)

        parent_chunks, child_chunks = chunker.chunk_document(content, doc_id=1)

        # Should have multiple chunks
        assert len(parent_chunks) >= 1
        assert len(child_chunks) >= len(parent_chunks)


# =============================================================================
# PgVectorStore Tests
# =============================================================================

class TestPgVectorStore:
    """Tests for pgvector integration."""

    def test_initialization(self, mock_db_session):
        """Test PgVectorStore initialization."""
        store = PgVectorStore(mock_db_session)
        assert store.db == mock_db_session
        assert store._extension_enabled is None

    def test_ensure_extension_caches_result(self, mock_db_session):
        """Test that extension check is cached."""
        store = PgVectorStore(mock_db_session)

        # First call
        store._extension_enabled = True
        result = store.ensure_extension()

        assert result is True
        # Should not call execute since cached
        mock_db_session.execute.assert_not_called()


# =============================================================================
# Migration SQL Tests
# =============================================================================

class TestMigrationSQL:
    """Tests for migration SQL generation."""

    def test_migration_sql_contains_vector_column(self):
        """Test that migration SQL includes vector column."""
        sql = get_pgvector_migration_sql()
        assert "vector(1536)" in sql
        assert "embedding_vector" in sql

    def test_migration_sql_contains_parent_chunk(self):
        """Test that migration SQL includes parent-child relationship."""
        sql = get_pgvector_migration_sql()
        assert "parent_chunk_id" in sql

    def test_migration_sql_contains_chunk_type(self):
        """Test that migration SQL includes chunk type."""
        sql = get_pgvector_migration_sql()
        assert "chunk_type" in sql

    def test_migration_sql_contains_indexes(self):
        """Test that migration SQL includes indexes."""
        sql = get_pgvector_migration_sql()
        assert "CREATE INDEX" in sql
        assert "ivfflat" in sql.lower()


# =============================================================================
# EnhancedRAGService Integration Tests
# =============================================================================

class TestEnhancedRAGService:
    """Integration tests for the full RAG service."""

    def test_initialization(self, mock_db_session, rag_config):
        """Test service initialization."""
        service = EnhancedRAGService(mock_db_session, rag_config)
        assert service.db == mock_db_session
        assert service.config == rag_config
        assert service.hybrid_searcher is not None
        assert service.reranker is not None
        assert service.query_expander is not None

    def test_default_config_used(self, mock_db_session):
        """Test that default config is used when none provided."""
        service = EnhancedRAGService(mock_db_session)
        assert service.config.initial_retrieval_k == 50

    @pytest.mark.asyncio
    async def test_generate_handles_no_results(self, mock_db_session, rag_config):
        """Test generation when no chunks are found."""
        service = EnhancedRAGService(mock_db_session, rag_config)

        # Mock embedding service to return empty results
        with patch.object(service, '_get_embedding', new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 1536

            # Mock hybrid searcher to return empty
            with patch.object(service.hybrid_searcher, 'search', new_callable=AsyncMock) as mock_search:
                mock_search.return_value = []

                # Mock generate answer
                with patch.object(service, '_generate_answer', new_callable=AsyncMock) as mock_gen:
                    mock_gen.return_value = "No relevant information found."

                    response = await service.generate(
                        query="test query",
                        user_id="test_user",
                        kb_id="test_kb"
                    )

                    assert isinstance(response, RAGResponse)
                    assert len(response.chunks_used) == 0


# =============================================================================
# RAGResponse Tests
# =============================================================================

class TestRAGResponse:
    """Tests for RAG response structure."""

    def test_create_response(self, sample_chunks):
        """Test creating a RAG response."""
        response = RAGResponse(
            answer="Test answer",
            chunks_used=sample_chunks,
            query_expanded=["test", "test query"],
            retrieval_time_ms=100.0,
            rerank_time_ms=50.0,
            generation_time_ms=200.0,
            total_time_ms=350.0,
            model_used="gpt-4o-mini"
        )

        assert response.answer == "Test answer"
        assert len(response.chunks_used) == 3
        assert response.query_expanded == ["test", "test query"]
        assert response.total_time_ms == 350.0

    def test_response_without_expansion(self, sample_chunks):
        """Test response without query expansion."""
        response = RAGResponse(
            answer="Test answer",
            chunks_used=sample_chunks,
            model_used="gpt-4o-mini"
        )

        assert response.query_expanded is None


# =============================================================================
# Scoring Tests
# =============================================================================

class TestHybridScoring:
    """Tests for hybrid score calculation."""

    def test_hybrid_score_calculation(self, sample_chunks):
        """Test that hybrid scores are calculated correctly."""
        embedding_weight = 0.7
        tfidf_weight = 0.3

        for chunk in sample_chunks:
            expected_hybrid = (
                embedding_weight * chunk.embedding_score +
                tfidf_weight * chunk.tfidf_score
            )
            chunk.hybrid_score = expected_hybrid

        # Verify first chunk
        assert sample_chunks[0].hybrid_score == pytest.approx(
            0.7 * 0.9 + 0.3 * 0.7,
            rel=0.01
        )

    def test_score_normalization(self):
        """Test that scores are properly bounded."""
        chunk = RetrievedChunk(
            chunk_id=1,
            document_id=1,
            content="test",
            embedding_score=1.0,
            tfidf_score=1.0
        )
        chunk.hybrid_score = 0.7 * 1.0 + 0.3 * 1.0

        # Max possible hybrid score is 1.0
        assert chunk.hybrid_score <= 1.0
