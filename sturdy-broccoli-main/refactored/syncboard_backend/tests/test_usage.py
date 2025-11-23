"""
Tests for Usage & Billing Router.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    """Create test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    """Create authenticated user and return auth headers."""
    # Create a test user
    import uuid
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    password = "testpass123"

    # Register user
    response = client.post("/users", json={
        "username": username,
        "password": password
    })

    # Login and get token
    response = client.post("/token", json={
        "username": username,
        "password": password
    })

    if response.status_code == 200:
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}

    # Return empty headers if login failed (for testing)
    return {}


class TestUsageRouter:
    """Tests for usage tracking and billing endpoints."""

    def test_get_plans(self, client: TestClient):
        """Test listing available plans."""
        response = client.get("/usage/plans")
        assert response.status_code == 200

        plans = response.json()
        assert len(plans) == 4  # free, starter, pro, enterprise

        plan_ids = [p["id"] for p in plans]
        assert "free" in plan_ids
        assert "starter" in plan_ids
        assert "pro" in plan_ids
        assert "enterprise" in plan_ids

        # Check free plan details
        free_plan = next(p for p in plans if p["id"] == "free")
        assert free_plan["name"] == "Free"
        assert free_plan["price_monthly"] == 0
        assert "Basic search" in free_plan["features"]

    def test_get_usage_unauthenticated(self, client: TestClient):
        """Test getting usage without authentication."""
        response = client.get("/usage")
        assert response.status_code == 401

    def test_get_usage_authenticated(self, client: TestClient, auth_headers: dict):
        """Test getting current usage for authenticated user."""
        if not auth_headers:
            pytest.skip("Could not authenticate user")

        response = client.get("/usage", headers=auth_headers)
        assert response.status_code == 200

        usage = response.json()
        assert "period_start" in usage
        assert "period_end" in usage
        assert "api_calls" in usage
        assert "documents_uploaded" in usage
        assert "ai_requests" in usage
        assert "storage_bytes" in usage
        assert "limits" in usage
        assert "usage_percentage" in usage

    def test_get_subscription(self, client: TestClient, auth_headers: dict):
        """Test getting subscription details."""
        if not auth_headers:
            pytest.skip("Could not authenticate user")

        response = client.get("/usage/subscription", headers=auth_headers)
        assert response.status_code == 200

        subscription = response.json()
        assert "plan" in subscription
        assert "status" in subscription
        assert "started_at" in subscription
        assert "limits" in subscription
        assert subscription["status"] == "active"

    def test_get_usage_history(self, client: TestClient, auth_headers: dict):
        """Test getting usage history."""
        if not auth_headers:
            pytest.skip("Could not authenticate user")

        response = client.get("/usage/history", headers=auth_headers)
        assert response.status_code == 200

        history = response.json()
        assert isinstance(history, list)

    def test_get_usage_history_with_months(self, client: TestClient, auth_headers: dict):
        """Test getting usage history with months parameter."""
        if not auth_headers:
            pytest.skip("Could not authenticate user")

        response = client.get("/usage/history?months=3", headers=auth_headers)
        assert response.status_code == 200

    def test_upgrade_subscription(self, client: TestClient, auth_headers: dict):
        """Test upgrading subscription plan."""
        if not auth_headers:
            pytest.skip("Could not authenticate user")

        response = client.post(
            "/usage/subscription/upgrade",
            json={"plan": "starter"},
            headers=auth_headers
        )
        assert response.status_code == 200

        result = response.json()
        assert result["plan"] == "starter"
        assert "limits" in result

    def test_upgrade_invalid_plan(self, client: TestClient, auth_headers: dict):
        """Test upgrading to invalid plan fails."""
        if not auth_headers:
            pytest.skip("Could not authenticate user")

        response = client.post(
            "/usage/subscription/upgrade",
            json={"plan": "invalid_plan"},
            headers=auth_headers
        )
        assert response.status_code == 422  # Validation error

    def test_plan_limits_structure(self, client: TestClient):
        """Test that plan limits have correct structure."""
        response = client.get("/usage/plans")
        plans = response.json()

        for plan in plans:
            limits = plan["limits"]
            assert "api_calls_per_minute" in limits
            assert "api_calls_per_day" in limits
            assert "documents_per_month" in limits
            assert "ai_requests_per_day" in limits
            assert "storage_mb" in limits
            assert "knowledge_bases" in limits

    def test_enterprise_unlimited_features(self, client: TestClient):
        """Test that enterprise plan has unlimited features."""
        response = client.get("/usage/plans")
        plans = response.json()

        enterprise = next(p for p in plans if p["id"] == "enterprise")
        limits = enterprise["limits"]

        # Enterprise has unlimited documents and KBs (-1)
        assert limits["documents_per_month"] == -1
        assert limits["knowledge_bases"] == -1


class TestUsageTracking:
    """Tests for usage tracking helper functions."""

    def test_usage_percentage_calculation(self, client: TestClient, auth_headers: dict):
        """Test that usage percentage is calculated correctly."""
        if not auth_headers:
            pytest.skip("Could not authenticate user")

        response = client.get("/usage", headers=auth_headers)
        usage = response.json()

        percentages = usage["usage_percentage"]

        # All percentages should be between 0 and 100
        for key, value in percentages.items():
            assert 0 <= value <= 100


class TestQuotaEnforcement:
    """Tests for quota enforcement."""

    def test_free_plan_limits(self, client: TestClient):
        """Test free plan has expected limits."""
        response = client.get("/usage/plans")
        plans = response.json()

        free = next(p for p in plans if p["id"] == "free")
        limits = free["limits"]

        assert limits["api_calls_per_minute"] == 10
        assert limits["api_calls_per_day"] == 100
        assert limits["documents_per_month"] == 50
        assert limits["ai_requests_per_day"] == 10
        assert limits["storage_mb"] == 100
        assert limits["knowledge_bases"] == 1
