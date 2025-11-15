"""
Tests for authentication router endpoints.

Tests user registration and login functionality.
"""

import pytest
from fastapi.testclient import TestClient

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


# =============================================================================
# REGISTRATION TESTS
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


# =============================================================================
# LOGIN TESTS
# =============================================================================

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
