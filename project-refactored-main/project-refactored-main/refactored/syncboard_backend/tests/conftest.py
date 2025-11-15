"""
Shared test fixtures for all test modules.

Provides:
- db_session: SQLite in-memory database session for testing
- Test environment setup (TESTING=true, secrets, etc.)
- Test state cleanup between tests
- OpenAI mock fixtures (Critical Fix #1)
"""

import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Dict, List

# =============================================================================
# Test Environment Configuration
# =============================================================================

# Set test environment variables
os.environ['TESTING'] = 'true'
os.environ['SYNCBOARD_SECRET_KEY'] = os.environ.get('SYNCBOARD_SECRET_KEY', 'test-secret-key-for-testing')
os.environ['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', 'sk-test-key')

# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture
def db_session() -> Session:
    """
    Create test database session with in-memory SQLite.

    Used by tests that need direct database access (e.g., analytics tests).
    Creates fresh database with all tables for each test.
    """
    from backend.db_models import Base

    # Create in-memory SQLite database
    engine = create_engine("sqlite:///:memory:", echo=False)

    # Create all tables
    Base.metadata.create_all(engine)

    # Create session
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()


# =============================================================================
# State Cleanup
# =============================================================================

@pytest.fixture
def cleanup_test_state():
    """
    Clean up global state between tests (opt-in).

    Use this fixture explicitly in tests that need state isolation:
        def test_something(cleanup_test_state):
            ...

    Prevents test pollution from shared in-memory state.
    """
    # Setup: Nothing needed before test

    yield  # Test runs here

    # Teardown: Clean up global state after test
    from backend import dependencies

    # Clear in-memory storage
    dependencies.documents.clear()
    dependencies.metadata.clear()
    dependencies.clusters.clear()
    dependencies.users.clear()

    # Clear vector store (only attributes that exist)
    if hasattr(dependencies.vector_store, 'docs'):
        dependencies.vector_store.docs.clear()
    if hasattr(dependencies.vector_store, 'doc_ids'):
        dependencies.vector_store.doc_ids.clear()
    if hasattr(dependencies.vector_store, 'texts'):
        dependencies.vector_store.texts.clear()
    if hasattr(dependencies.vector_store, 'tfidf_matrix'):
        dependencies.vector_store.tfidf_matrix = None


# =============================================================================
# OpenAI Mock Fixtures (Critical Fix #1)
# =============================================================================

class MockLLMProvider:
    """Mock LLM provider that returns valid test data without API calls."""

    async def extract_concepts(self, content: str, source_type: str) -> Dict:
        """Return mock concept extraction results."""
        # Extract some keywords from content for realistic mocks
        words = content.lower().split()
        concepts = []

        # Add realistic concepts based on content
        concept_keywords = {
            'python': {'name': 'Python', 'category': 'programming language', 'confidence': 0.9},
            'fastapi': {'name': 'FastAPI', 'category': 'web framework', 'confidence': 0.85},
            'docker': {'name': 'Docker', 'category': 'containerization', 'confidence': 0.88},
            'kubernetes': {'name': 'Kubernetes', 'category': 'orchestration', 'confidence': 0.82},
            'postgresql': {'name': 'PostgreSQL', 'category': 'database', 'confidence': 0.87},
            'api': {'name': 'REST API', 'category': 'architecture', 'confidence': 0.75},
            'test': {'name': 'Testing', 'category': 'quality assurance', 'confidence': 0.70},
            'web': {'name': 'Web Development', 'category': 'development', 'confidence': 0.72},
            'backend': {'name': 'Backend Development', 'category': 'development', 'confidence': 0.73},
        }

        for keyword, concept in concept_keywords.items():
            if keyword in words:
                concepts.append(concept)

        # Always include at least 2 generic concepts
        if len(concepts) == 0:
            concepts = [
                {'name': 'Programming', 'category': 'general', 'confidence': 0.6},
                {'name': 'Development', 'category': 'general', 'confidence': 0.55}
            ]

        return {
            'concepts': concepts[:5],  # Max 5 concepts
            'skill_level': 'intermediate',
            'primary_topic': concepts[0]['name'] if concepts else 'General',
            'suggested_cluster': f"{concepts[0]['name']} Development" if concepts else 'General'
        }

    async def generate_build_suggestions(self, knowledge_summary: str, max_suggestions: int) -> List[Dict]:
        """Return mock build suggestions."""
        suggestions = [
            {
                'title': 'Full-Stack Web Application',
                'description': 'Build a complete web app using your knowledge of Python, FastAPI, and databases',
                'difficulty': 'intermediate',
                'estimated_hours': 40,
                'technologies': ['Python', 'FastAPI', 'PostgreSQL', 'Docker']
            },
            {
                'title': 'API Gateway Service',
                'description': 'Create a microservices API gateway with authentication and rate limiting',
                'difficulty': 'advanced',
                'estimated_hours': 60,
                'technologies': ['FastAPI', 'Docker', 'Redis', 'JWT']
            },
            {
                'title': 'Data Processing Pipeline',
                'description': 'Build an ETL pipeline for processing and analyzing large datasets',
                'difficulty': 'intermediate',
                'estimated_hours': 35,
                'technologies': ['Python', 'Pandas', 'PostgreSQL', 'Airflow']
            }
        ]
        return suggestions[:max_suggestions]


@pytest.fixture
def mock_llm_provider():
    """Provide a mock LLM provider for testing without OpenAI API calls."""
    return MockLLMProvider()


@pytest.fixture(autouse=True)
def mock_openai_for_all_tests(monkeypatch):
    """
    Automatically mock OpenAI for all tests.

    This prevents real API calls and provides consistent test data.
    Applied to all tests via autouse=True.
    """
    mock_provider = MockLLMProvider()

    # Mock the ConceptExtractor to use our mock provider
    def mock_concept_extractor_init(self, llm_provider=None):
        self.provider = llm_provider or mock_provider

    monkeypatch.setattr(
        'backend.concept_extractor.ConceptExtractor.__init__',
        mock_concept_extractor_init
    )

    return mock_provider
