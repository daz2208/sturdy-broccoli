"""
Tests for clusters router endpoints.

Tests cluster retrieval, updates, and export functionality.
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
    username = "testuser_clusters"
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
# CLUSTER RETRIEVAL TESTS
# =============================================================================

def test_get_clusters_empty(client, auth_headers):
    """Test getting clusters when none exist."""
    response = client.get("/clusters", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "clusters" in data
    assert isinstance(data["clusters"], list)


@patch('backend.main.concept_extractor.extract')
async def test_get_clusters_with_data(mock_extract, client, auth_headers):
    """Test getting clusters after uploading content."""
    # Mock concept extraction
    mock_extract.return_value = {
        "concepts": [
            {"name": "FastAPI", "category": "framework", "confidence": 0.9}
        ],
        "skill_level": "intermediate",
        "suggested_cluster": "Web Frameworks",
        "primary_topic": "Backend Development"
    }

    # Upload some content first
    client.post(
        "/upload_text",
        headers=auth_headers,
        json={"content": "FastAPI tutorial for building APIs"}
    )

    # Get clusters
    response = client.get("/clusters", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data["clusters"]) > 0

    cluster = data["clusters"][0]
    assert "id" in cluster
    assert "name" in cluster
    assert "doc_count" in cluster


# =============================================================================
# CLUSTER UPDATE TESTS
# =============================================================================

@patch('backend.main.concept_extractor.extract')
async def test_update_cluster(mock_extract, client, auth_headers):
    """Test updating cluster name."""
    # Mock concept extraction
    mock_extract.return_value = {
        "concepts": [
            {"name": "Cluster", "category": "concept", "confidence": 0.8}
        ],
        "skill_level": "intermediate",
        "suggested_cluster": "Original Name",
        "primary_topic": "Clustering"
    }

    # Upload to create cluster
    upload_response = client.post(
        "/upload_text",
        headers=auth_headers,
        json={"content": "Content for cluster"}
    )
    cluster_id = upload_response.json()["cluster_id"]

    # Update cluster
    response = client.put(
        f"/clusters/{cluster_id}",
        headers=auth_headers,
        json={"name": "Updated Cluster Name"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["cluster"]["name"] == "Updated Cluster Name"


# =============================================================================
# CLUSTER EXPORT TESTS
# =============================================================================

@patch('backend.main.concept_extractor.extract')
async def test_export_cluster_json(mock_extract, client, auth_headers):
    """Test exporting cluster as JSON."""
    # Mock concept extraction
    mock_extract.return_value = {
        "concepts": [
            {"name": "Export", "category": "concept", "confidence": 0.8}
        ],
        "skill_level": "intermediate",
        "suggested_cluster": "Export Test",
        "primary_topic": "Data Export"
    }

    # Upload to create cluster
    upload_response = client.post(
        "/upload_text",
        headers=auth_headers,
        json={"content": "Content for export"}
    )
    cluster_id = upload_response.json()["cluster_id"]

    # Export as JSON
    response = client.get(
        f"/export/cluster/{cluster_id}?format=json",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert "cluster" in data
    assert "documents" in data


@patch('backend.main.concept_extractor.extract')
async def test_export_cluster_markdown(mock_extract, client, auth_headers):
    """Test exporting cluster as Markdown."""
    # Mock concept extraction
    mock_extract.return_value = {
        "concepts": [
            {"name": "Markdown", "category": "format", "confidence": 0.9}
        ],
        "skill_level": "beginner",
        "suggested_cluster": "Markdown Export",
        "primary_topic": "Documentation"
    }

    # Upload to create cluster
    upload_response = client.post(
        "/upload_text",
        headers=auth_headers,
        json={"content": "Markdown export test"}
    )
    cluster_id = upload_response.json()["cluster_id"]

    # Export as Markdown
    response = client.get(
        f"/export/cluster/{cluster_id}?format=markdown",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert data["format"] == "markdown"


def test_export_nonexistent_cluster(client, auth_headers):
    """Test exporting cluster that doesn't exist."""
    response = client.get(
        "/export/cluster/99999?format=json",
        headers=auth_headers
    )
    assert response.status_code == 404


@patch('backend.main.concept_extractor.extract')
async def test_export_all(mock_extract, client, auth_headers):
    """Test exporting entire knowledge bank."""
    # Mock concept extraction
    mock_extract.return_value = {
        "concepts": [
            {"name": "Full", "category": "concept", "confidence": 0.7}
        ],
        "skill_level": "intermediate",
        "suggested_cluster": "Full Export",
        "primary_topic": "Export"
    }

    # Upload some content
    client.post(
        "/upload_text",
        headers=auth_headers,
        json={"content": "First document"}
    )
    client.post(
        "/upload_text",
        headers=auth_headers,
        json={"content": "Second document"}
    )

    # Export all as JSON
    response = client.get("/export/all?format=json", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert "clusters" in data
    assert len(data["documents"]) >= 2
