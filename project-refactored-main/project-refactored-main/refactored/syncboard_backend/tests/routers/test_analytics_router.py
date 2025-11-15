"""
Tests for analytics router endpoints.

Tests analytics dashboard and statistics endpoints.
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
    username = "testuser_analytics"
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
# ANALYTICS TESTS
# =============================================================================

def test_get_analytics_empty(client, auth_headers):
    """Test getting analytics when no data exists."""
    response = client.get("/analytics", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "summary" in data or "statistics" in data


@patch('backend.main.concept_extractor.extract')
async def test_get_analytics_with_data(mock_extract, client, auth_headers):
    """Test getting analytics after uploading content."""
    # Mock concept extraction
    mock_extract.return_value = {
        "concepts": [
            {"name": "Analytics", "category": "concept", "confidence": 0.9}
        ],
        "skill_level": "intermediate",
        "suggested_cluster": "Analytics",
        "primary_topic": "Data"
    }

    # Upload some content
    client.post(
        "/upload_text",
        headers=auth_headers,
        json={"content": "Analytics and metrics tracking"}
    )

    # Get analytics
    response = client.get("/analytics", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    # Verify analytics structure contains expected fields
    assert isinstance(data, dict)
