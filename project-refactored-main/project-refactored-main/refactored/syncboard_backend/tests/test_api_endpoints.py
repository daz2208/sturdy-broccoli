"""
End-to-end integration tests for the complete API workflow.

This file contains integration tests that exercise multiple routers together.
Individual router tests are located in tests/routers/.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

# Import the FastAPI app
import sys
from pathlib import Path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from backend.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


# =============================================================================
# HEALTH CHECK TEST
# =============================================================================

def test_health_check(client):
    """Test health check endpoint (no auth required)."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "statistics" in data
    assert "documents" in data["statistics"]
    assert "clusters" in data["statistics"]
    assert "users" in data["statistics"]
    assert "dependencies" in data
    assert "disk_healthy" in data["dependencies"]
    assert "openai_configured" in data["dependencies"]


# =============================================================================
# INTEGRATION TEST - FULL WORKFLOW
# =============================================================================

@patch('backend.main.concept_extractor.extract')
async def test_full_workflow(mock_extract, client):
    """
    Test complete workflow: register → login → upload → search → delete.

    This is a comprehensive integration test that exercises the entire system
    across multiple routers: auth, uploads, search, documents, and clusters.
    """
    # Mock concept extraction for all uploads
    mock_extract.return_value = {
        "concepts": [
            {"name": "Integration", "category": "concept", "confidence": 0.9},
            {"name": "Testing", "category": "concept", "confidence": 0.85}
        ],
        "skill_level": "advanced",
        "suggested_cluster": "Integration Testing",
        "primary_topic": "Software Testing"
    }

    # 1. Register user
    register_response = client.post(
        "/users",
        json={"username": "workflow_user", "password": "testpass123"}
    )
    assert register_response.status_code == 200

    # 2. Login
    login_response = client.post(
        "/token",
        json={"username": "workflow_user", "password": "testpass123"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Upload text document
    upload_response = client.post(
        "/upload_text",
        headers=headers,
        json={"content": "Integration testing is important for software quality"}
    )
    assert upload_response.status_code == 200
    doc_id = upload_response.json()["document_id"]
    cluster_id = upload_response.json()["cluster_id"]

    # 4. Search for document
    search_response = client.get(
        "/search_full?q=integration&top_k=5",
        headers=headers
    )
    assert search_response.status_code == 200
    assert len(search_response.json()["results"]) > 0

    # 5. Get clusters
    clusters_response = client.get("/clusters", headers=headers)
    assert clusters_response.status_code == 200
    assert len(clusters_response.json()["clusters"]) > 0

    # 6. Export cluster
    export_response = client.get(
        f"/export/cluster/{cluster_id}?format=json",
        headers=headers
    )
    assert export_response.status_code == 200

    # 7. Update document metadata
    update_response = client.put(
        f"/documents/{doc_id}/metadata",
        headers=headers,
        json={"skill_level": "expert"}
    )
    assert update_response.status_code == 200

    # 8. Delete document
    delete_response = client.delete(f"/documents/{doc_id}", headers=headers)
    assert delete_response.status_code == 200

    # 9. Verify deletion
    get_response = client.get(f"/documents/{doc_id}", headers=headers)
    assert get_response.status_code == 404

    # 10. Check health
    health_response = client.get("/health")
    assert health_response.status_code == 200
