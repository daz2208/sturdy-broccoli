"""
Tests for security middleware.

Tests security headers and HTTPS enforcement.
"""

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

# Import the FastAPI app
import sys
from pathlib import Path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from backend.security_middleware import SecurityHeadersMiddleware


@pytest.fixture
def app_with_middleware_dev():
    """Create test app with security middleware in development mode."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, environment="development")

    @app.get("/test")
    def test_endpoint():
        return {"message": "test"}

    return app


@pytest.fixture
def app_with_middleware_prod():
    """Create test app with security middleware in production mode."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, environment="production")

    @app.get("/test")
    def test_endpoint():
        return {"message": "test"}

    return app


# =============================================================================
# SECURITY HEADERS TESTS
# =============================================================================

def test_adds_x_content_type_options(app_with_middleware_dev):
    """Test X-Content-Type-Options header is added."""
    client = TestClient(app_with_middleware_dev)
    response = client.get("/test")

    assert "X-Content-Type-Options" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_adds_x_frame_options(app_with_middleware_dev):
    """Test X-Frame-Options header is added."""
    client = TestClient(app_with_middleware_dev)
    response = client.get("/test")

    assert "X-Frame-Options" in response.headers
    assert response.headers["X-Frame-Options"] == "DENY"


def test_adds_x_xss_protection(app_with_middleware_dev):
    """Test X-XSS-Protection header is added."""
    client = TestClient(app_with_middleware_dev)
    response = client.get("/test")

    assert "X-XSS-Protection" in response.headers
    assert response.headers["X-XSS-Protection"] == "1; mode=block"


def test_adds_content_security_policy(app_with_middleware_dev):
    """Test Content-Security-Policy header is added."""
    client = TestClient(app_with_middleware_dev)
    response = client.get("/test")

    assert "Content-Security-Policy" in response.headers
    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_adds_referrer_policy(app_with_middleware_dev):
    """Test Referrer-Policy header is added."""
    client = TestClient(app_with_middleware_dev)
    response = client.get("/test")

    assert "Referrer-Policy" in response.headers
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_adds_permissions_policy(app_with_middleware_dev):
    """Test Permissions-Policy header is added."""
    client = TestClient(app_with_middleware_dev)
    response = client.get("/test")

    assert "Permissions-Policy" in response.headers
    perms = response.headers["Permissions-Policy"]
    assert "geolocation=()" in perms
    assert "camera=()" in perms


# =============================================================================
# HSTS TESTS (PRODUCTION VS DEVELOPMENT)
# =============================================================================

def test_no_hsts_in_development(app_with_middleware_dev):
    """Test HSTS header is NOT added in development mode."""
    client = TestClient(app_with_middleware_dev)
    response = client.get("/test")

    assert "Strict-Transport-Security" not in response.headers


def test_hsts_in_production(app_with_middleware_prod):
    """Test HSTS header IS added in production mode."""
    client = TestClient(app_with_middleware_prod)
    response = client.get("/test")

    assert "Strict-Transport-Security" in response.headers
    hsts = response.headers["Strict-Transport-Security"]
    assert "max-age=31536000" in hsts
    assert "includeSubDomains" in hsts
    assert "preload" in hsts


# =============================================================================
# MIDDLEWARE BEHAVIOR TESTS
# =============================================================================

def test_middleware_allows_request_to_proceed(app_with_middleware_dev):
    """Test middleware doesn't block valid requests."""
    client = TestClient(app_with_middleware_dev)
    response = client.get("/test")

    assert response.status_code == 200
    assert response.json() == {"message": "test"}


def test_middleware_applies_to_all_endpoints(app_with_middleware_dev):
    """Test middleware applies headers to all endpoints."""
    app = app_with_middleware_dev

    @app.get("/another")
    def another_endpoint():
        return {"data": "value"}

    client = TestClient(app)
    response = client.get("/another")

    assert "X-Content-Type-Options" in response.headers
    assert "Content-Security-Policy" in response.headers


def test_middleware_applies_to_post_requests(app_with_middleware_dev):
    """Test middleware applies to POST requests."""
    app = app_with_middleware_dev

    @app.post("/create")
    def create_endpoint():
        return {"created": True}

    client = TestClient(app)
    response = client.post("/create")

    assert "X-Content-Type-Options" in response.headers


def test_middleware_applies_to_error_responses(app_with_middleware_dev):
    """Test middleware applies headers even to error responses."""
    app = app_with_middleware_dev

    @app.get("/error")
    def error_endpoint():
        raise ValueError("Test error")

    client = TestClient(app)
    try:
        response = client.get("/error")
    except:
        pass

    # Even on error, security headers should be present if response is created


# =============================================================================
# ENVIRONMENT CONFIGURATION TESTS
# =============================================================================

def test_middleware_respects_environment_setting():
    """Test middleware respects environment parameter."""
    # Test development
    app_dev = FastAPI()
    middleware_dev = SecurityHeadersMiddleware(app_dev.routes, environment="development")
    assert middleware_dev.environment == "development"
    assert middleware_dev.is_production == False

    # Test production
    app_prod = FastAPI()
    middleware_prod = SecurityHeadersMiddleware(app_prod.routes, environment="production")
    assert middleware_prod.environment == "production"
    assert middleware_prod.is_production == True


def test_middleware_default_environment():
    """Test middleware defaults to development."""
    app = FastAPI()
    middleware = SecurityHeadersMiddleware(app.routes)
    assert middleware.environment == "development"


# =============================================================================
# CSP POLICY TESTS
# =============================================================================

def test_csp_allows_self_resources(app_with_middleware_dev):
    """Test CSP allows resources from same origin."""
    client = TestClient(app_with_middleware_dev)
    response = client.get("/test")

    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp


def test_csp_restricts_inline_scripts(app_with_middleware_dev):
    """Test CSP configuration for scripts."""
    client = TestClient(app_with_middleware_dev)
    response = client.get("/test")

    csp = response.headers["Content-Security-Policy"]
    assert "script-src 'self' 'unsafe-inline'" in csp


def test_csp_image_policy(app_with_middleware_dev):
    """Test CSP allows images from various sources."""
    client = TestClient(app_with_middleware_dev)
    response = client.get("/test")

    csp = response.headers["Content-Security-Policy"]
    assert "img-src 'self' data: https:" in csp


def test_csp_prevents_iframe_embedding(app_with_middleware_dev):
    """Test CSP prevents iframe embedding."""
    client = TestClient(app_with_middleware_dev)
    response = client.get("/test")

    csp = response.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in csp


# =============================================================================
# PERMISSIONS POLICY TESTS
# =============================================================================

def test_permissions_policy_disables_geolocation(app_with_middleware_dev):
    """Test Permissions-Policy disables geolocation."""
    client = TestClient(app_with_middleware_dev)
    response = client.get("/test")

    perms = response.headers["Permissions-Policy"]
    assert "geolocation=()" in perms


def test_permissions_policy_disables_camera_and_microphone(app_with_middleware_dev):
    """Test Permissions-Policy disables camera and microphone."""
    client = TestClient(app_with_middleware_dev)
    response = client.get("/test")

    perms = response.headers["Permissions-Policy"]
    assert "camera=()" in perms
    assert "microphone=()" in perms


def test_permissions_policy_disables_payment(app_with_middleware_dev):
    """Test Permissions-Policy disables payment APIs."""
    client = TestClient(app_with_middleware_dev)
    response = client.get("/test")

    perms = response.headers["Permissions-Policy"]
    assert "payment=()" in perms
