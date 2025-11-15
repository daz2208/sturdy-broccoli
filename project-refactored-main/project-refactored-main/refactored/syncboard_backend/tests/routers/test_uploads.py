"""
Tests for uploads router endpoints.

Tests text, URL, file, and image upload functionality.
"""

import pytest
import base64
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
    username = "testuser_uploads"
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
# TEXT UPLOAD TESTS
# =============================================================================

@patch('backend.main.concept_extractor.extract')
async def test_upload_text(mock_extract, client, auth_headers):
    """Test text upload endpoint."""
    # Mock concept extraction
    mock_extract.return_value = {
        "concepts": [
            {"name": "Python", "category": "language", "confidence": 0.9}
        ],
        "skill_level": "intermediate",
        "suggested_cluster": "Python Programming",
        "primary_topic": "Programming"
    }

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


# =============================================================================
# URL UPLOAD TESTS
# =============================================================================

@patch('backend.main.ingest.download_url')
@patch('backend.main.concept_extractor.extract')
async def test_upload_url(mock_extract, mock_download, client, auth_headers):
    """Test URL upload endpoint."""
    # Mock URL download
    mock_download.return_value = "Article content about Docker"

    # Mock concept extraction
    mock_extract.return_value = {
        "concepts": [
            {"name": "Docker", "category": "tool", "confidence": 0.85}
        ],
        "skill_level": "intermediate",
        "suggested_cluster": "Containerization",
        "primary_topic": "DevOps"
    }

    response = client.post(
        "/upload",
        headers=auth_headers,
        json={"url": "https://example.com/docker-tutorial"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "document_id" in data
    assert "cluster_id" in data


# =============================================================================
# FILE UPLOAD TESTS
# =============================================================================

@patch('backend.main.ingest.ingest_upload_file')
@patch('backend.main.concept_extractor.extract')
async def test_upload_file(mock_extract, mock_ingest, client, auth_headers):
    """Test file upload endpoint."""
    # Mock file ingestion
    mock_ingest.return_value = "PDF content about testing"

    # Mock concept extraction
    mock_extract.return_value = {
        "concepts": [
            {"name": "Testing", "category": "concept", "confidence": 0.8}
        ],
        "skill_level": "beginner",
        "suggested_cluster": "Software Testing",
        "primary_topic": "Quality Assurance"
    }

    # Encode fake file content
    file_content = b"Fake PDF content"
    encoded = base64.b64encode(file_content).decode('utf-8')

    response = client.post(
        "/upload_file",
        headers=auth_headers,
        json={"filename": "test.pdf", "content": encoded}
    )

    assert response.status_code == 200
    data = response.json()
    assert "document_id" in data
    assert "cluster_id" in data


def test_upload_file_too_large(client, auth_headers):
    """Test uploading file larger than 50MB fails."""
    # Create 51MB of data
    large_content = b"x" * (51 * 1024 * 1024)
    encoded = base64.b64encode(large_content).decode('utf-8')

    response = client.post(
        "/upload_file",
        headers=auth_headers,
        json={"filename": "large.pdf", "content": encoded}
    )

    assert response.status_code == 413


# =============================================================================
# IMAGE UPLOAD TESTS
# =============================================================================

@patch('backend.main.image_processor.extract_text_from_image')
@patch('backend.main.image_processor.get_image_metadata')
@patch('backend.main.image_processor.store_image')
@patch('backend.main.concept_extractor.extract')
async def test_upload_image(mock_extract, mock_store, mock_meta, mock_ocr, client, auth_headers):
    """Test image upload with OCR."""
    # Mock OCR
    mock_ocr.return_value = "Text from image"
    mock_meta.return_value = {"width": 800, "height": 600}
    mock_store.return_value = "stored_images/doc_0.png"

    # Mock concept extraction
    mock_extract.return_value = {
        "concepts": [
            {"name": "OCR", "category": "technology", "confidence": 0.7}
        ],
        "skill_level": "advanced",
        "suggested_cluster": "Image Processing",
        "primary_topic": "Computer Vision"
    }

    # Encode fake image
    image_bytes = b"fake image data"
    encoded = base64.b64encode(image_bytes).decode('utf-8')

    response = client.post(
        "/upload_image",
        headers=auth_headers,
        json={
            "filename": "test.png",
            "content": encoded,
            "description": "Test image"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "document_id" in data
    assert "ocr_text_length" in data
