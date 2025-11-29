"""
Test Project Goals API endpoints.

Tests all 7 project goals endpoints:
- GET /project-goals - List all goals
- GET /project-goals/primary - Get primary goal
- GET /project-goals/{id} - Get specific goal
- POST /project-goals - Create goal
- PUT /project-goals/{id} - Update goal
- DELETE /project-goals/{id} - Delete goal
- POST /project-goals/set-primary/{id} - Set primary goal
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add backend to path
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
    username = "testuser_goals"
    password = "testpass123"

    # Register
    client.post(
        "/users",
        json={"username": username, "password": password}
    )

    # Login
    login_response = client.post(
        "/token",
        json={"username": username, "password": password}
    )

    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# PROJECT GOALS TESTS
# =============================================================================

def test_create_project_goal(client, auth_headers):
    """Test creating a project goal."""
    goal_data = {
        "goal_type": "revenue",
        "description": "Generate $10k monthly revenue from SaaS product",
        "priority": 1,
        "constraints": {
            "time_available": "20 hours/week",
            "budget": "$5000",
            "target_market": "Small businesses",
            "tech_stack_preference": "Python, FastAPI, React",
            "deployment_preference": "Cloud-based (AWS/GCP)"
        }
    }

    response = client.post(
        "/project-goals",
        json=goal_data,
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["goal_type"] == "revenue"
    assert data["description"] == goal_data["description"]
    assert data["priority"] == 1
    assert data["is_primary"] == False
    assert "id" in data
    assert data["constraints"]["budget"] == "$5000"


def test_create_learning_goal(client, auth_headers):
    """Test creating a learning goal."""
    goal_data = {
        "goal_type": "learning",
        "description": "Master React and TypeScript for full-stack development",
        "priority": 2,
        "constraints": {
            "time_available": "10 hours/week",
            "budget": "$1000",
            "tech_stack_preference": "React, TypeScript, Next.js"
        }
    }

    response = client.post(
        "/project-goals",
        json=goal_data,
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["goal_type"] == "learning"
    assert data["priority"] == 2


def test_get_all_goals(client, auth_headers):
    """Test getting all project goals."""
    # Create multiple goals
    goals = [
        {
            "goal_type": "revenue",
            "description": "Revenue goal 1",
            "priority": 1
        },
        {
            "goal_type": "learning",
            "description": "Learning goal 1",
            "priority": 2
        },
        {
            "goal_type": "portfolio",
            "description": "Portfolio goal 1",
            "priority": 3
        }
    ]

    for goal_data in goals:
        client.post("/project-goals", json=goal_data, headers=auth_headers)

    # Get all goals
    response = client.get("/project-goals", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "goals" in data
    assert len(data["goals"]) >= 3


def test_get_goal_by_id(client, auth_headers):
    """Test getting a specific goal by ID."""
    # Create a goal
    goal_data = {
        "goal_type": "automation",
        "description": "Automate deployment pipeline",
        "priority": 1
    }

    create_response = client.post(
        "/project-goals",
        json=goal_data,
        headers=auth_headers
    )
    goal_id = create_response.json()["id"]

    # Get the goal
    response = client.get(f"/project-goals/{goal_id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == goal_id
    assert data["description"] == goal_data["description"]


def test_update_goal(client, auth_headers):
    """Test updating a project goal."""
    # Create a goal
    goal_data = {
        "goal_type": "revenue",
        "description": "Initial description",
        "priority": 1
    }

    create_response = client.post(
        "/project-goals",
        json=goal_data,
        headers=auth_headers
    )
    goal_id = create_response.json()["id"]

    # Update the goal
    update_data = {
        "description": "Updated description",
        "priority": 5,
        "constraints": {
            "time_available": "30 hours/week",
            "budget": "$10000"
        }
    }

    response = client.put(
        f"/project-goals/{goal_id}",
        json=update_data,
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Updated description"
    assert data["priority"] == 5
    assert data["constraints"]["budget"] == "$10000"


def test_set_primary_goal(client, auth_headers):
    """Test setting a primary goal."""
    # Create two goals
    goal1_data = {
        "goal_type": "revenue",
        "description": "Goal 1",
        "priority": 1
    }
    goal2_data = {
        "goal_type": "learning",
        "description": "Goal 2",
        "priority": 2
    }

    response1 = client.post("/project-goals", json=goal1_data, headers=auth_headers)
    response2 = client.post("/project-goals", json=goal2_data, headers=auth_headers)

    goal1_id = response1.json()["id"]
    goal2_id = response2.json()["id"]

    # Set goal 1 as primary
    response = client.post(
        f"/project-goals/set-primary/{goal1_id}",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Primary goal set successfully"

    # Verify goal 1 is primary
    check_response = client.get(f"/project-goals/{goal1_id}", headers=auth_headers)
    assert check_response.json()["is_primary"] == True

    # Set goal 2 as primary (should unset goal 1)
    response = client.post(
        f"/project-goals/set-primary/{goal2_id}",
        headers=auth_headers
    )

    assert response.status_code == 200

    # Verify goal 1 is no longer primary
    check_response1 = client.get(f"/project-goals/{goal1_id}", headers=auth_headers)
    assert check_response1.json()["is_primary"] == False

    # Verify goal 2 is now primary
    check_response2 = client.get(f"/project-goals/{goal2_id}", headers=auth_headers)
    assert check_response2.json()["is_primary"] == True


def test_get_primary_goal(client, auth_headers):
    """Test getting the primary goal."""
    # Initially should have no primary goal
    response = client.get("/project-goals/primary", headers=auth_headers)
    # May return 404 or empty result depending on implementation
    assert response.status_code in [200, 404]

    # Create and set a primary goal
    goal_data = {
        "goal_type": "portfolio",
        "description": "Build impressive portfolio",
        "priority": 1
    }

    create_response = client.post("/project-goals", json=goal_data, headers=auth_headers)
    goal_id = create_response.json()["id"]

    # Set as primary
    client.post(f"/project-goals/set-primary/{goal_id}", headers=auth_headers)

    # Get primary goal
    response = client.get("/project-goals/primary", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == goal_id
    assert data["is_primary"] == True


def test_delete_goal(client, auth_headers):
    """Test deleting a project goal."""
    # Create a goal
    goal_data = {
        "goal_type": "automation",
        "description": "Goal to delete",
        "priority": 1
    }

    create_response = client.post(
        "/project-goals",
        json=goal_data,
        headers=auth_headers
    )
    goal_id = create_response.json()["id"]

    # Delete the goal
    response = client.delete(f"/project-goals/{goal_id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "message" in data

    # Verify goal is deleted
    get_response = client.get(f"/project-goals/{goal_id}", headers=auth_headers)
    assert get_response.status_code == 404


def test_goal_types_validation(client, auth_headers):
    """Test that only valid goal types are accepted."""
    valid_types = ["revenue", "learning", "portfolio", "automation"]

    for goal_type in valid_types:
        goal_data = {
            "goal_type": goal_type,
            "description": f"Test {goal_type} goal",
            "priority": 1
        }

        response = client.post(
            "/project-goals",
            json=goal_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["goal_type"] == goal_type


def test_invalid_goal_type(client, auth_headers):
    """Test that invalid goal type is rejected."""
    goal_data = {
        "goal_type": "invalid_type",
        "description": "Test goal",
        "priority": 1
    }

    response = client.post(
        "/project-goals",
        json=goal_data,
        headers=auth_headers
    )

    # Should fail validation
    assert response.status_code == 422


def test_goal_priority_validation(client, auth_headers):
    """Test priority field validation."""
    # Valid priorities
    for priority in [1, 5, 10]:
        goal_data = {
            "goal_type": "learning",
            "description": f"Priority {priority} goal",
            "priority": priority
        }

        response = client.post(
            "/project-goals",
            json=goal_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["priority"] == priority


def test_unauthorized_access(client):
    """Test that endpoints require authentication."""
    # Try to access without auth
    response = client.get("/project-goals")
    assert response.status_code == 401

    response = client.get("/project-goals/primary")
    assert response.status_code == 401

    response = client.post("/project-goals", json={})
    assert response.status_code == 401


def test_goal_with_all_constraints(client, auth_headers):
    """Test creating a goal with all constraint fields."""
    goal_data = {
        "goal_type": "revenue",
        "description": "Comprehensive goal with all constraints",
        "priority": 1,
        "constraints": {
            "time_available": "40 hours/week",
            "budget": "$20000",
            "target_market": "Enterprise clients",
            "tech_stack_preference": "Python, FastAPI, React, PostgreSQL, Docker",
            "deployment_preference": "Kubernetes on AWS EKS"
        }
    }

    response = client.post(
        "/project-goals",
        json=goal_data,
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    constraints = data["constraints"]
    assert constraints["time_available"] == "40 hours/week"
    assert constraints["budget"] == "$20000"
    assert constraints["target_market"] == "Enterprise clients"
    assert "PostgreSQL" in constraints["tech_stack_preference"]
    assert "Kubernetes" in constraints["deployment_preference"]


def test_update_partial_fields(client, auth_headers):
    """Test updating only some fields of a goal."""
    # Create goal
    goal_data = {
        "goal_type": "portfolio",
        "description": "Original description",
        "priority": 3,
        "constraints": {
            "time_available": "10 hours/week",
            "budget": "$1000"
        }
    }

    create_response = client.post("/project-goals", json=goal_data, headers=auth_headers)
    goal_id = create_response.json()["id"]

    # Update only description
    update_data = {
        "description": "New description only"
    }

    response = client.put(
        f"/project-goals/{goal_id}",
        json=update_data,
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "New description only"
    # Priority should remain unchanged
    assert data["priority"] == 3
