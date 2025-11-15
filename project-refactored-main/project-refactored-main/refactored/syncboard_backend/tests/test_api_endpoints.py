"""
End-to-end API endpoint tests (Phase 5).

Tests all 12 API endpoints with actual HTTP calls using FastAPI TestClient.
Verifies full workflows from registration through document management.
"""

import pytest
import base64
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

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


@pytest.fixture
def auth_headers(client):
    """Register and login, return auth headers."""
    # Register a test user
    username = "testuser_api"
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
# AUTHENTICATION TESTS
# =============================================================================

def test_register_new_user(client):
    """Test user registration."""
    response = client.post(
        "/users",
        json={"username": "newuser123", "password": "password123"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "newuser123"


def test_register_duplicate_user(client):
    """Test registering duplicate username fails."""
    username = "duplicate_user"
    password = "password123"

    # First registration
    client.post("/users", json={"username": username, "password": password})

    # Second registration should fail
    response = client.post(
        "/users",
        json={"username": username, "password": password}
    )

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


def test_register_invalid_username(client):
    """Test username validation."""
    # Too short
    response = client.post(
        "/users",
        json={"username": "ab", "password": "password123"}
    )
    assert response.status_code == 422


def test_register_invalid_password(client):
    """Test password validation."""
    # Too short
    response = client.post(
        "/users",
        json={"username": "validuser", "password": "short"}
    )
    assert response.status_code == 422


def test_login_success(client):
    """Test successful login."""
    username = "logintest"
    password = "password123"

    # Register
    client.post("/users", json={"username": username, "password": password})

    # Login
    response = client.post(
        "/token",
        json={"username": username, "password": password}
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_credentials(client):
    """Test login with wrong password."""
    response = client.post(
        "/token",
        json={"username": "nonexistent", "password": "wrongpass"}
    )

    assert response.status_code == 401


def test_unauthorized_access(client):
    """Test accessing protected endpoint without auth."""
    response = client.get("/clusters")
    assert response.status_code == 401


# =============================================================================
# UPLOAD TESTS
# =============================================================================

async def test_upload_text(client, auth_headers):
    """Test text upload endpoint."""

    response = client.post(
        "/upload_text",
        headers=auth_headers,
        json={"content": "Learn Python programming basics"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "document_id" in data
    assert "cluster_id" in data


def test_upload_text_empty_content(client, auth_headers):
    """Test uploading empty text fails."""
    response = client.post(
        "/upload_text",
        headers=auth_headers,
        json={"content": ""}
    )

    assert response.status_code == 400


async def test_upload_url(client, auth_headers):
    """Test URL upload endpoint."""
