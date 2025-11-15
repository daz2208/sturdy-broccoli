"""
Tests for build suggestions router endpoints.

Tests the "what can I build" project suggestions functionality.
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
    username = "testuser_suggestions"
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
# BUILD SUGGESTIONS TESTS
# =============================================================================

@patch('backend.main.build_suggester.analyze_knowledge_bank')
async def test_what_can_i_build(mock_analyze, client, auth_headers):
    """Test build suggestions endpoint."""
    # Mock build suggestions
    mock_analyze.return_value = [
        {
            "title": "Test Project",
            "description": "A test project",
            "feasibility": "high",
            "effort_estimate": "1 week",
            "required_skills": ["Python"],
            "missing_knowledge": [],
            "relevant_clusters": [0],
            "starter_steps": ["Step 1", "Step 2"],
            "file_structure": "project/\n  main.py"
        }
    ]

    response = client.post(
        "/what_can_i_build",
        headers=auth_headers,
        json={"max_suggestions": 5}
    )

    assert response.status_code == 200
    data = response.json()
    assert "suggestions" in data
    assert "knowledge_summary" in data
