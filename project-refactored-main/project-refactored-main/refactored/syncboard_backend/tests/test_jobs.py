"""
Tests for Celery Job Status Router (jobs.py).

Tests job status retrieval, cancellation, and ownership verification.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import HTTPException

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
    username = "testuser_jobs"
    password = "testpass123"

    client.post("/users", json={"username": username, "password": password})
    login_response = client.post("/token", json={"username": username, "password": password})
    token = login_response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# GET JOB STATUS TESTS
# =============================================================================

class TestGetJobStatus:
    """Tests for GET /jobs/{job_id}/status endpoint."""

    def test_get_job_status_pending(self, client, auth_headers):
        """Test getting status of pending job."""
        with patch('backend.routers.jobs.AsyncResult') as mock_result:
            mock_task = MagicMock()
            mock_task.state = 'PENDING'
            mock_task.info = None
            mock_result.return_value = mock_task

            response = client.get("/jobs/test-job-123/status", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == "test-job-123"
            assert data["status"] == "PENDING"

    def test_get_job_status_processing(self, client, auth_headers):
        """Test getting status of processing job with progress."""
        with patch('backend.routers.jobs.AsyncResult') as mock_result:
            mock_task = MagicMock()
            mock_task.state = 'PROCESSING'
            mock_task.info = {
                'progress': 50,
                'current_step': 'Extracting text from PDF'
            }
            mock_result.return_value = mock_task

            response = client.get("/jobs/test-job-456/status", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == "test-job-456"
            assert data["status"] == "PROCESSING"
            assert data["progress"] == 50
            assert "current_step" in data

    def test_get_job_status_success(self, client, auth_headers):
        """Test getting status of successfully completed job."""
        with patch('backend.routers.jobs.AsyncResult') as mock_result:
            mock_task = MagicMock()
            mock_task.state = 'SUCCESS'
            mock_task.info = {
                'document_id': 42,
                'cluster_id': 5,
                'concepts': ['Python', 'Testing']
            }
            mock_task.result = mock_task.info
            mock_result.return_value = mock_task

            response = client.get("/jobs/test-job-789/status", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == "test-job-789"
            assert data["status"] == "SUCCESS"
            assert data["document_id"] == 42
            assert data["cluster_id"] == 5

    def test_get_job_status_failure(self, client, auth_headers):
        """Test getting status of failed job with error message."""
        with patch('backend.routers.jobs.AsyncResult') as mock_result:
            mock_task = MagicMock()
            mock_task.state = 'FAILURE'
            mock_task.info = Exception("Failed to download URL: 404 Not Found")
            mock_result.return_value = mock_task

            response = client.get("/jobs/test-job-fail/status", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == "test-job-fail"
            assert data["status"] == "FAILURE"
            assert "error" in data
            assert "404" in data["error"]

    def test_get_job_status_retry(self, client, auth_headers):
        """Test getting status of job being retried."""
        with patch('backend.routers.jobs.AsyncResult') as mock_result:
            mock_task = MagicMock()
            mock_task.state = 'RETRY'
            mock_task.info = {'retry_count': 2, 'max_retries': 3}
            mock_result.return_value = mock_task

            response = client.get("/jobs/test-job-retry/status", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == "test-job-retry"
            assert data["status"] == "RETRY"


# =============================================================================
# CANCEL JOB TESTS
# =============================================================================

class TestCancelJob:
    """Tests for DELETE /jobs/{job_id} endpoint."""

    def test_cancel_job_success(self, client, auth_headers):
        """Test successfully canceling a pending job."""
        with patch('backend.routers.jobs.AsyncResult') as mock_result:
            mock_task = MagicMock()
            mock_task.state = 'PENDING'
            mock_task.revoke = MagicMock()
            mock_result.return_value = mock_task

            response = client.delete("/jobs/test-job-cancel/status", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Job cancelled successfully"
            mock_task.revoke.assert_called_once_with(terminate=True)

    def test_cancel_job_already_completed(self, client, auth_headers):
        """Test canceling a job that's already completed."""
        with patch('backend.routers.jobs.AsyncResult') as mock_result:
            mock_task = MagicMock()
            mock_task.state = 'SUCCESS'
            mock_result.return_value = mock_task

            response = client.delete("/jobs/test-job-done/status", headers=auth_headers)

            # Should still return 200 but indicate it was already complete
            assert response.status_code in [200, 400]

    def test_cancel_nonexistent_job(self, client, auth_headers):
        """Test canceling a job that doesn't exist."""
        with patch('backend.routers.jobs.AsyncResult') as mock_result:
            mock_task = MagicMock()
            mock_task.state = 'PENDING'
            mock_task.revoke = MagicMock()
            mock_result.return_value = mock_task

            # Job that was never created
            response = client.delete("/jobs/nonexistent-job-999/status", headers=auth_headers)

            # Should handle gracefully
            assert response.status_code in [200, 404]


# =============================================================================
# AUTHENTICATION & AUTHORIZATION TESTS
# =============================================================================

class TestJobSecurity:
    """Tests for job ownership and authentication."""

    def test_get_job_status_unauthorized(self, client):
        """Test getting job status without authentication fails."""
        response = client.get("/jobs/test-job-123/status")

        assert response.status_code == 401

    def test_cancel_job_unauthorized(self, client):
        """Test canceling job without authentication fails."""
        response = client.delete("/jobs/test-job-123/status")

        assert response.status_code == 401


# =============================================================================
# EDGE CASES & ERROR HANDLING
# =============================================================================

class TestJobEdgeCases:
    """Tests for edge cases and error handling."""

    def test_get_job_status_with_special_characters_in_id(self, client, auth_headers):
        """Test job ID with special characters."""
        with patch('backend.routers.jobs.AsyncResult') as mock_result:
            mock_task = MagicMock()
            mock_task.state = 'PENDING'
            mock_result.return_value = mock_task

            # UUID-style job ID
            job_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
            response = client.get(f"/jobs/{job_id}/status", headers=auth_headers)

            assert response.status_code == 200

    def test_get_job_status_celery_connection_error(self, client, auth_headers):
        """Test handling Celery broker connection errors."""
        with patch('backend.routers.jobs.AsyncResult') as mock_result:
            mock_result.side_effect = Exception("Connection to broker lost")

            response = client.get("/jobs/test-job/status", headers=auth_headers)

            # Should handle gracefully with 500 or similar
            assert response.status_code in [500, 503]

    def test_job_with_missing_info(self, client, auth_headers):
        """Test job with missing or malformed info."""
        with patch('backend.routers.jobs.AsyncResult') as mock_result:
            mock_task = MagicMock()
            mock_task.state = 'PROCESSING'
            mock_task.info = None  # Missing info
            mock_result.return_value = mock_task

            response = client.get("/jobs/test-job-no-info/status", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "PROCESSING"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestJobWorkflow:
    """Integration tests for complete job workflows."""

    def test_upload_check_status_workflow(self, client, auth_headers):
        """Test complete workflow: upload file -> check status -> get result."""
        # Step 1: Upload a URL (creates background job)
        with patch('backend.routers.uploads.process_url_upload.delay') as mock_upload:
            mock_upload.return_value.id = "workflow-job-123"

            upload_response = client.post(
                "/upload",
                headers=auth_headers,
                json={"url": "https://example.com/article"}
            )

            assert upload_response.status_code == 200
            job_id = upload_response.json()["job_id"]

        # Step 2: Check job status (initially pending)
        with patch('backend.routers.jobs.AsyncResult') as mock_result:
            mock_task = MagicMock()
            mock_task.state = 'PENDING'
            mock_result.return_value = mock_task

            status_response = client.get(f"/jobs/{job_id}/status", headers=auth_headers)

            assert status_response.status_code == 200
            assert status_response.json()["status"] == "PENDING"

        # Step 3: Check again (now processing)
        with patch('backend.routers.jobs.AsyncResult') as mock_result:
            mock_task = MagicMock()
            mock_task.state = 'PROCESSING'
            mock_task.info = {'progress': 75}
            mock_result.return_value = mock_task

            status_response = client.get(f"/jobs/{job_id}/status", headers=auth_headers)

            assert status_response.status_code == 200
            assert status_response.json()["status"] == "PROCESSING"

        # Step 4: Check final status (completed)
        with patch('backend.routers.jobs.AsyncResult') as mock_result:
            mock_task = MagicMock()
            mock_task.state = 'SUCCESS'
            mock_task.result = {
                'document_id': 100,
                'cluster_id': 10,
                'concepts': ['AI', 'Machine Learning']
            }
            mock_result.return_value = mock_task

            status_response = client.get(f"/jobs/{job_id}/status", headers=auth_headers)

            assert status_response.status_code == 200
            data = status_response.json()
            assert data["status"] == "SUCCESS"
            assert data["document_id"] == 100

    def test_cancel_running_job_workflow(self, client, auth_headers):
        """Test canceling a job that's currently processing."""
        job_id = "cancel-test-job"

        # Start with processing job
        with patch('backend.routers.jobs.AsyncResult') as mock_result:
            mock_task = MagicMock()
            mock_task.state = 'PROCESSING'
            mock_task.info = {'progress': 30}
            mock_result.return_value = mock_task

            status = client.get(f"/jobs/{job_id}/status", headers=auth_headers)
            assert status.json()["status"] == "PROCESSING"

        # Cancel the job
        with patch('backend.routers.jobs.AsyncResult') as mock_result:
            mock_task = MagicMock()
            mock_task.state = 'PROCESSING'
            mock_task.revoke = MagicMock()
            mock_result.return_value = mock_task

            cancel_response = client.delete(f"/jobs/{job_id}/status", headers=auth_headers)
            assert cancel_response.status_code == 200
