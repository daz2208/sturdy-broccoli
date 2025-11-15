"""
Tests for search router endpoints.

Tests search functionality with filters and queries.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

# Import the FastAPI app
import sys
from pathlib import Path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from backend.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Register and login, return auth headers."""
    # Register a test user
    username = "testuser_search"
    password = "testpass123"

    register_response = client.post(
        "/users",
        json={"username": username, "password": password}
    )

    # Login to get token
    login_response = client.post(
        "/token",
        json={"username": username, "password": password}
    )

    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# SEARCH TESTS
# =============================================================================

@patch('backend.main.concept_extractor.extract')
async def test_search_documents(mock_extract, client, auth_headers):
    """Test search functionality."""
    # Mock concept extraction
    mock_extract.return_value = {
        "concepts": [
            {"name": "Python", "category": "language", "confidence": 0.9}
        ],
        "skill_level": "beginner",
        "suggested_cluster": "Python Basics",
        "primary_topic": "Programming"
    }

    # Upload content
    client.post(
        "/upload_text",
        headers=auth_headers,
        json={"content": "Python programming tutorial"}
    )

    # Search
    response = client.get(
        "/search_full?q=Python&top_k=10",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert isinstance(data["results"], list)


def test_search_empty_query(client, auth_headers):
    """Test search with empty query."""
    response = client.get(
        "/search_full?q=",
        headers=auth_headers
    )

    # Should return empty results or error
    assert response.status_code in [200, 400]


@patch('backend.main.concept_extractor.extract')
async def test_search_with_filters(mock_extract, client, auth_headers):
    """Test search with filters (source_type, skill_level)."""
    # Mock concept extraction
    mock_extract.return_value = {
        "concepts": [
            {"name": "Testing", "category": "concept", "confidence": 0.8}
        ],
        "skill_level": "intermediate",
        "suggested_cluster": "Testing",
        "primary_topic": "QA"
    }

    # Upload content
    client.post(
        "/upload_text",
        headers=auth_headers,
        json={"content": "Unit testing with pytest"}
    )

    # Search with filters
    response = client.get(
        "/search_full?q=testing&source_type=text&skill_level=intermediate",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert "filters_applied" in data
    assert data["filters_applied"]["source_type"] == "text"
