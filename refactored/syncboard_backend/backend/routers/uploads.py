"""
Uploads Router for SyncBoard 3.0 Knowledge Bank.

Endpoints:
- POST /upload_text - Upload plain text content
- POST /upload - Upload document via URL (YouTube, web article, etc)
- POST /upload_file - Upload file (PDF, audio, etc) as base64
- POST /upload_image - Upload and process image with OCR
"""

import base64
import logging
from datetime import datetime
from typing import List, Dict
from fastapi import APIRouter, HTTPException, Request, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..models import (
    TextUpload,
    DocumentUpload,
    FileBytesUpload,
    ImageUpload,
    User,
    DocumentMetadata,
    Concept,
)
from ..dependencies import (
    get_current_user,
    get_documents,
    get_metadata,
    get_clusters,
    get_users,
    get_vector_store,
    get_storage_lock,
    get_concept_extractor,
    get_clustering_engine,
    get_image_processor,
    get_kb_documents,
    get_kb_metadata,
    get_kb_clusters,
    get_user_default_kb_id,
    ensure_kb_exists,
)
from ..database import get_db
from sqlalchemy.orm import Session
from ..sanitization import (
    sanitize_filename,
    sanitize_text_content,
    sanitize_description,
    validate_url,
)
from ..constants import MAX_UPLOAD_SIZE_BYTES
from .. import ingest
from ..db_storage_adapter import save_storage_to_db
from ..redis_client import increment_user_job_count, get_user_job_count
from ..tasks import process_file_upload, process_url_upload, process_image_upload

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(
    prefix="",
    tags=["uploads"],
    responses={401: {"description": "Unauthorized"}},
)

# =============================================================================
# Clustering Helper
# =============================================================================

async def find_or_create_cluster(
    doc_id: int,
    suggested_cluster: str,
    concepts: List[Dict],
    kb_id: str
) -> int:
    """Find best cluster or create new one for a knowledge base."""
    kb_metadata = get_kb_metadata(kb_id)
    kb_clusters = get_kb_clusters(kb_id)
    clustering_engine = get_clustering_engine()

    meta = kb_metadata[doc_id]

    # Try to find existing cluster in this KB
    cluster_id = clustering_engine.find_best_cluster(
        doc_concepts=concepts,
        suggested_name=suggested_cluster,
        existing_clusters=kb_clusters
    )

    if cluster_id is not None:
        clustering_engine.add_to_cluster(cluster_id, doc_id, kb_clusters)
        return cluster_id

    # Create new cluster in this KB
    cluster_id = clustering_engine.create_cluster(
        doc_id=doc_id,
        name=suggested_cluster,
        concepts=concepts,
        skill_level=meta.skill_level,
        existing_clusters=kb_clusters
    )

    # Set knowledge_base_id on the cluster
    kb_clusters[cluster_id].knowledge_base_id = kb_id

    return cluster_id

# =============================================================================
# Text Upload Endpoint
# =============================================================================

@router.post("/upload_text")
@limiter.limit("10/minute")
async def upload_text_content(
    req: TextUpload,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload plain text content.

    Rate limited to 10 uploads per minute.

    Args:
        req: Text upload request
        request: FastAPI request (for rate limiting)
        current_user: Authenticated user
        db: Database session

    Returns:
        Document ID, cluster ID, and extracted concepts
    """
    # Sanitize text content to prevent XSS and resource exhaustion
    content = sanitize_text_content(req.content)

    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(current_user.username, db)
    ensure_kb_exists(kb_id)

    # Get KB-scoped storage
    kb_documents = get_kb_documents(kb_id)
    kb_metadata = get_kb_metadata(kb_id)
    kb_clusters = get_kb_clusters(kb_id)
    documents = get_documents()
    metadata = get_metadata()
    clusters = get_clusters()
    users = get_users()
    vector_store = get_vector_store()
    storage_lock = get_storage_lock()
    concept_extractor = get_concept_extractor()

    async with storage_lock:
        # Extract concepts
        extraction = await concept_extractor.extract(content, "text")

        # Add to vector store
        doc_id = vector_store.add_document(content)

        # Add to KB-scoped storage
        kb_documents[doc_id] = content

        # Create metadata
        meta = DocumentMetadata(
            doc_id=doc_id,
            owner=current_user.username,
            source_type="text",
            concepts=[Concept(**c) for c in extraction.get("concepts", [])],
            skill_level=extraction.get("skill_level", "unknown"),
            cluster_id=None,
            knowledge_base_id=kb_id,
            ingested_at=datetime.utcnow().isoformat(),
            content_length=len(content)
        )
        kb_metadata[doc_id] = meta

        # Find or create cluster
        cluster_id = await find_or_create_cluster(
            doc_id=doc_id,
            suggested_cluster=extraction.get("suggested_cluster", "General"),
            concepts=extraction.get("concepts", []),
            kb_id=kb_id
        )
        kb_metadata[doc_id].cluster_id = cluster_id

        # Save
        save_storage_to_db(documents, metadata, clusters, users)

        # Update document count in KB
        from ..db_models import DBKnowledgeBase
        kb = db.query(DBKnowledgeBase).filter_by(id=kb_id).first()
        if kb:
            kb.document_count = len(kb_documents)
            db.commit()

        # Structured logging with request context
        logger.info(
            f"[{request.state.request_id}] User {current_user.username} uploaded text as doc {doc_id} "
            f"to KB {kb_id} (cluster: {cluster_id}, concepts: {len(extraction.get('concepts', []))})"
        )

        return {
            "document_id": doc_id,
            "cluster_id": cluster_id,
            "knowledge_base_id": kb_id,
            "concepts": extraction.get("concepts", [])
        }

# =============================================================================
# URL Upload Endpoint (Celery)
# =============================================================================

@router.post("/upload")
@limiter.limit("5/minute")
async def upload_url(
    doc: DocumentUpload,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload document via URL (YouTube, web article, etc) - Background processing with Celery.

    Rate limited to 5 uploads per minute.

    Args:
        doc: Document upload request with URL
        request: FastAPI request (for rate limiting)
        current_user: Authenticated user
        db: Database session

    Returns:
        Job ID for polling status

    Response:
        {
            "job_id": "abc123-def456",
            "message": "URL queued for processing",
            "url": "https://example.com",
            "knowledge_base_id": "uuid"
        }

    Poll /jobs/{job_id}/status for progress and results.
    """
    # Validate URL to prevent SSRF attacks
    url = validate_url(str(doc.url))

    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Rate limit: Check concurrent job count
    user_job_count = get_user_job_count(current_user.username)
    if user_job_count >= 10:
        raise HTTPException(
            status_code=429,
            detail="Too many background jobs in progress. Please wait for current uploads to complete."
        )

    # Queue Celery task with kb_id
    task = process_url_upload.delay(
        user_id=current_user.username,
        url=url,
        kb_id=kb_id
    )

    # Increment job count
    increment_user_job_count(current_user.username)

    logger.info(
        f"[{request.state.request_id}] User {current_user.username} queued URL upload: "
        f"{url} to KB {kb_id} (job_id: {task.id})"
    )

    return {
        "job_id": task.id,
        "message": "URL queued for processing",
        "url": url,
        "knowledge_base_id": kb_id
    }

# =============================================================================
# File Upload Endpoint (Celery)
# =============================================================================

@router.post("/upload_file")
@limiter.limit("5/minute")
async def upload_file(
    req: FileBytesUpload,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload file (PDF, audio, etc) as base64 - Background processing with Celery.

    Rate limited to 5 uploads per minute.

    Args:
        req: File upload request
        request: FastAPI request (for rate limiting)
        current_user: Authenticated user
        db: Database session

    Returns:
        Job ID for polling status

    Response:
        {
            "job_id": "abc123-def456",
            "message": "File queued for processing",
            "filename": "document.pdf",
            "knowledge_base_id": "uuid"
        }

    Poll /jobs/{job_id}/status for progress and results.
    """
    # Sanitize filename to prevent path traversal attacks
    filename = sanitize_filename(req.filename)

    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(current_user.username, db)

    try:
        # Validate base64 and file size early
        file_bytes = base64.b64decode(req.content)

        if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE_BYTES / (1024*1024):.0f}MB"
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 content: {exc}")

    # Rate limit: Check concurrent job count
    user_job_count = get_user_job_count(current_user.username)
    if user_job_count >= 10:
        raise HTTPException(
            status_code=429,
            detail="Too many background jobs in progress. Please wait for current uploads to complete."
        )

    # Queue Celery task with kb_id
    task = process_file_upload.delay(
        user_id=current_user.username,
        filename=filename,
        content_base64=req.content,  # Pass original base64 to avoid re-encoding
        kb_id=kb_id
    )

    # Increment job count
    increment_user_job_count(current_user.username)

    logger.info(
        f"[{request.state.request_id}] User {current_user.username} queued file upload: "
        f"{filename} to KB {kb_id} (job_id: {task.id})"
    )

    return {
        "job_id": task.id,
        "message": "File queued for processing",
        "filename": filename,
        "knowledge_base_id": kb_id
    }

# =============================================================================
# Image Upload Endpoint (Celery)
# =============================================================================

@router.post("/upload_image")
@limiter.limit("10/minute")
async def upload_image(
    req: ImageUpload,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload and process image with OCR - Background processing with Celery.

    Rate limited to 10 uploads per minute.

    Args:
        req: Image upload request
        request: FastAPI request (for rate limiting)
        current_user: Authenticated user
        db: Database session

    Returns:
        Job ID for polling status

    Response:
        {
            "job_id": "abc123-def456",
            "message": "Image queued for OCR processing",
            "filename": "screenshot.png",
            "knowledge_base_id": "uuid"
        }

    Poll /jobs/{job_id}/status for progress and results.
    """
    # Sanitize filename to prevent path traversal attacks
    filename = sanitize_filename(req.filename)

    # Sanitize optional description
    description = sanitize_description(req.description) if req.description else None

    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(current_user.username, db)

    try:
        # Validate base64 and file size early
        image_bytes = base64.b64decode(req.content)

        if len(image_bytes) > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Image too large. Maximum size is {MAX_UPLOAD_SIZE_BYTES / (1024*1024):.0f}MB"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64: {e}")

    # Rate limit: Check concurrent job count
    user_job_count = get_user_job_count(current_user.username)
    if user_job_count >= 10:
        raise HTTPException(
            status_code=429,
            detail="Too many background jobs in progress. Please wait for current uploads to complete."
        )

    # Queue Celery task with kb_id
    task = process_image_upload.delay(
        user_id=current_user.username,
        filename=filename,
        content_base64=req.content,
        description=description,
        kb_id=kb_id
    )

    # Increment job count
    increment_user_job_count(current_user.username)

    logger.info(
        f"[{request.state.request_id}] User {current_user.username} queued image upload: "
        f"{filename} (job_id: {task.id})"
    )

    return {
        "job_id": task.id,
        "message": "Image queued for OCR processing",
        "filename": filename
    }
