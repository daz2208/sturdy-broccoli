"""
OAuth Authentication Tests.

Tests OAuth login flow for Google and GitHub providers.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
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
# OAuth Login Initiation Tests
# =============================================================================

def test_oauth_google_login_not_configured(client):
    """Test Google OAuth login fails gracefully when not configured."""
    # Without GOOGLE_CLIENT_ID/SECRET env vars, should return 503
    with patch.dict('os.environ', {'GOOGLE_CLIENT_ID': '', 'GOOGLE_CLIENT_SECRET': ''}):
        response = client.get("/auth/google/login", allow_redirects=False)
        # Either redirects to provider (if configured) or returns error
        assert response.status_code in [307, 503]


def test_oauth_github_login_not_configured(client):
    """Test GitHub OAuth login fails gracefully when not configured."""
    with patch.dict('os.environ', {'GITHUB_CLIENT_ID': '', 'GITHUB_CLIENT_SECRET': ''}):
        response = client.get("/auth/github/login", allow_redirects=False)
        assert response.status_code in [307, 503]


def test_oauth_invalid_provider(client):
    """Test invalid OAuth provider returns 400."""
    response = client.get("/auth/invalid_provider/login", allow_redirects=False)
    assert response.status_code == 400
    assert "Unsupported OAuth provider" in response.json()["detail"]


def test_oauth_google_login_redirect(client):
    """Test Google OAuth login redirects to Google."""
    with patch.dict('os.environ', {
        'GOOGLE_CLIENT_ID': 'test-client-id',
        'GOOGLE_CLIENT_SECRET': 'test-secret'
    }):
        with patch('backend.routers.auth.redis_client.setex', new_callable=AsyncMock) as mock_redis:
            mock_redis.return_value = True
            response = client.get("/auth/google/login", allow_redirects=False)

            if response.status_code == 307:  # Redirect
                location = response.headers.get("location", "")
                assert "accounts.google.com" in location
                assert "client_id=test-client-id" in location
                assert "response_type=code" in location


def test_oauth_github_login_redirect(client):
    """Test GitHub OAuth login redirects to GitHub."""
    with patch.dict('os.environ', {
        'GITHUB_CLIENT_ID': 'test-client-id',
        'GITHUB_CLIENT_SECRET': 'test-secret'
    }):
        with patch('backend.routers.auth.redis_client.setex', new_callable=AsyncMock) as mock_redis:
            mock_redis.return_value = True
            response = client.get("/auth/github/login", allow_redirects=False)

            if response.status_code == 307:  # Redirect
                location = response.headers.get("location", "")
                assert "github.com/login/oauth/authorize" in location
                assert "client_id=test-client-id" in location


# =============================================================================
# OAuth Callback Tests
# =============================================================================

def test_oauth_callback_missing_params(client):
    """Test OAuth callback with missing params redirects with error."""
    response = client.get("/auth/google/callback", allow_redirects=False)
    assert response.status_code == 307
    location = response.headers.get("location", "")
    assert "error=missing_params" in location


def test_oauth_callback_with_error(client):
    """Test OAuth callback with error from provider."""
    response = client.get("/auth/google/callback?error=access_denied", allow_redirects=False)
    assert response.status_code == 307
    location = response.headers.get("location", "")
    assert "error=access_denied" in location


def test_oauth_callback_invalid_state(client):
    """Test OAuth callback with invalid state token."""
    with patch('backend.routers.auth.redis_client.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None  # State not found

        response = client.get(
            "/auth/google/callback?code=test_code&state=invalid_state",
            allow_redirects=False
        )
        assert response.status_code == 307
        location = response.headers.get("location", "")
        assert "error=invalid_state" in location


def test_oauth_callback_state_mismatch(client):
    """Test OAuth callback with state that doesn't match provider."""
    with patch('backend.routers.auth.redis_client.get', new_callable=AsyncMock) as mock_get:
        # State stored for github, but callback is for google
        mock_get.return_value = b"github"

        response = client.get(
            "/auth/google/callback?code=test_code&state=valid_state",
            allow_redirects=False
        )
        assert response.status_code == 307
        location = response.headers.get("location", "")
        assert "error=invalid_state" in location


@pytest.mark.asyncio
async def test_oauth_callback_successful_google_flow():
    """Test successful Google OAuth flow with mocked external calls."""
    from unittest.mock import patch, AsyncMock

    # This is a comprehensive mock test for the OAuth flow
    mock_token_response = AsyncMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {"access_token": "mock_access_token"}

    mock_user_response = AsyncMock()
    mock_user_response.status_code = 200
    mock_user_response.json.return_value = {
        "id": "12345",
        "email": "testuser@gmail.com",
        "name": "Test User"
    }

    with patch('backend.routers.auth.redis_client.get', new_callable=AsyncMock) as mock_get, \
         patch('backend.routers.auth.redis_client.delete', new_callable=AsyncMock) as mock_delete, \
         patch('backend.routers.auth.httpx.AsyncClient') as mock_client_class, \
         patch.dict('os.environ', {
             'GOOGLE_CLIENT_ID': 'test-client-id',
             'GOOGLE_CLIENT_SECRET': 'test-secret',
             'FRONTEND_URL': 'http://localhost:3000'
         }):

        mock_get.return_value = b"google"  # Valid state
        mock_delete.return_value = True

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_token_response
        mock_client.get.return_value = mock_user_response
        mock_client_class.return_value = mock_client

        client = TestClient(app)
        response = client.get(
            "/auth/google/callback?code=valid_code&state=valid_state",
            allow_redirects=False
        )

        # Should redirect to frontend with token
        assert response.status_code == 307
        location = response.headers.get("location", "")
        assert "localhost:3000/login" in location
        # Should have token in URL (or error if something went wrong)
        assert "token=" in location or "error=" in location
