"""
Tests for documents router endpoints.

Tests document retrieval, deletion, and metadata updates.
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
    username = "testuser_documents"
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
# DOCUMENT RETRIEVAL TESTS
# =============================================================================

@patch('backend.main.concept_extractor.extract')
async def test_get_document(mock_extract, client, auth_headers):
    """Test getting a single document."""
    # Mock concept extraction
    mock_extract.return_value = {
        "concepts": [
            {"name": "API", "category": "concept", "confidence": 0.85}
        ],
        "skill_level": "intermediate",
        "suggested_cluster": "APIs",
        "primary_topic": "Backend"
    }

    # Upload document
    upload_response = client.post(
        "/upload_text",
        headers=auth_headers,
        json={"content": "REST API design patterns"}
    )
    doc_id = upload_response.json()["document_id"]

    # Get document
    response = client.get(f"/documents/{doc_id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["doc_id"] == doc_id
    assert "content" in data
    assert "metadata" in data


def test_get_nonexistent_document(client, auth_headers):
    """Test getting document that doesn't exist."""
    response = client.get("/documents/99999", headers=auth_headers)
    assert response.status_code == 404


# =============================================================================
# DOCUMENT DELETION TESTS
# =============================================================================

@patch('backend.main.concept_extractor.extract')
async def test_delete_document(mock_extract, client, auth_headers):
    """Test deleting a document."""
    # Mock concept extraction
    mock_extract.return_value = {
        "concepts": [
            {"name": "Delete", "category": "concept", "confidence": 0.7}
        ],
        "skill_level": "beginner",
        "suggested_cluster": "Operations",
        "primary_topic": "CRUD"
    }

    # Upload document
    upload_response = client.post(
        "/upload_text",
        headers=auth_headers,
        json={"content": "Document to be deleted"}
    )
    doc_id = upload_response.json()["document_id"]

    # Delete document
    response = client.delete(f"/documents/{doc_id}", headers=auth_headers)

    assert response.status_code == 200
    assert "deleted" in response.json()["message"].lower()

    # Verify deletion
    get_response = client.get(f"/documents/{doc_id}", headers=auth_headers)
    assert get_response.status_code == 404


# =============================================================================
# DOCUMENT UPDATE TESTS
# =============================================================================

@patch('backend.main.concept_extractor.extract')
async def test_update_document_metadata(mock_extract, client, auth_headers):
    """Test updating document metadata."""
    # Mock concept extraction
    mock_extract.return_value = {
        "concepts": [
            {"name": "Update", "category": "concept", "confidence": 0.75}
        ],
        "skill_level": "intermediate",
        "suggested_cluster": "Updates",
        "primary_topic": "Metadata"
    }

    # Upload document
    upload_response = client.post(
        "/upload_text",
        headers=auth_headers,
        json={"content": "Document to update"}
    )
    doc_id = upload_response.json()["document_id"]

    # Update metadata
    response = client.put(
        f"/documents/{doc_id}/metadata",
        headers=auth_headers,
        json={"skill_level": "advanced"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["skill_level"] == "advanced"
