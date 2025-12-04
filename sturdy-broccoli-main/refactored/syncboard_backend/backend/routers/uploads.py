"""
Uploads Router for SyncBoard 3.0 Knowledge Bank.

Endpoints:
- POST /upload_text - Upload plain text content
- POST /upload - Upload document via URL (YouTube, web article, etc)
- POST /upload_file - Upload file (PDF, audio, etc) as base64
- POST /upload_image - Upload and process image with OCR
- POST /upload_batch - Upload multiple files in one request
- POST /upload_batch_urls - Upload multiple URLs in one request
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
    BatchFileUpload,
    BatchUrlUpload,
    User,
    DocumentMetadata,
    Concept,
)
from ..dependencies import (
    get_current_user,
    get_repository,
    get_concept_extractor,
    get_clustering_engine,
    get_image_processor,
    get_kb_metadata,
    get_kb_clusters,
    get_user_default_kb_id,
    ensure_kb_exists,
)
from ..repository_interface import KnowledgeBankRepository
from ..database import get_db
from sqlalchemy.orm import Session
from ..redis_client import (
    invalidate_analytics,
    invalidate_build_suggestions,
    invalidate_search
)
from ..sanitization import (
    sanitize_filename,
    sanitize_text_content,
    sanitize_description,
    validate_url,
    validate_and_split_url,
    detect_multiple_urls,
)
from ..constants import MAX_UPLOAD_SIZE_BYTES
from .. import ingest
from ..redis_client import increment_user_job_count, get_user_job_count
from ..tasks import process_file_upload, process_url_upload, process_image_upload
from ..chunking_pipeline import chunk_document_on_upload
from ..db_models import DBDocument
from celery import group  # For parallel batch processing
from ..celery_app import celery_app  # For queue depth inspection
from ..websocket_manager import broadcast_document_created
from ..feedback_service import feedback_service

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Batch upload configuration
MAX_BATCH_SIZE = 20  # Maximum files per batch submission
CHUNK_SIZE = 5  # Process N files at a time to avoid overwhelming workers
MAX_QUEUE_DEPTH = 30  # Maximum pending tasks before rejecting new uploads

# Create router
router = APIRouter(
    prefix="",
    tags=["uploads"],
    responses={401: {"description": "Unauthorized"}},
)

# =============================================================================
# Clustering Helper
# =============================================================================

def generate_cluster_name_from_concepts(concepts: List[Dict], primary_topic: str = None) -> str:
    """Generate a meaningful cluster name when LLM returns 'General'."""
    # First try primary_topic if provided
    if primary_topic and primary_topic.lower() not in ['uncategorized', 'unknown', 'general']:
        return primary_topic.replace('_', ' ').title()

    if not concepts:
        return "General"

    # Get top concepts by confidence
    sorted_concepts = sorted(concepts, key=lambda c: c.get('confidence', 0.5), reverse=True)[:3]

    if not sorted_concepts:
        return "General"

    top_names = [c.get('name', '').replace('_', ' ').title() for c in sorted_concepts if c.get('name')]

    if len(top_names) >= 2:
        return f"{top_names[0]} & {top_names[1]}"
    elif top_names:
        return top_names[0]

    return "General"


async def find_or_create_cluster(
    doc_id: int,
    suggested_cluster: str,
    concepts: List[Dict],
    kb_id: str,
    primary_topic: str = None
) -> int:
    """Find best cluster or create new one for a knowledge base."""
    kb_metadata = get_kb_metadata(kb_id)
    kb_clusters = get_kb_clusters(kb_id)
    clustering_engine = get_clustering_engine()

    # Fix: If suggested_cluster is "General" or empty, generate better name
    if not suggested_cluster or suggested_cluster.lower() == 'general':
        suggested_cluster = generate_cluster_name_from_concepts(concepts, primary_topic)
        logger.info(f"Generated cluster name from concepts: '{suggested_cluster}'")

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
    repo: KnowledgeBankRepository = Depends(get_repository),
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

    # Get concept extractor
    concept_extractor = get_concept_extractor()

    # AGENTIC LEARNING: Use learning-aware extraction that applies past corrections
    # This closes the feedback loop - the system actually learns from user corrections
    extraction = await concept_extractor.extract_with_learning(
        content=content,
        source_type="text",
        username=current_user.username,
        knowledge_base_id=kb_id
    )

    # Log learning metadata if applied
    learning_applied = extraction.get("learning_applied", {})
    if learning_applied.get("corrections_used", 0) > 0:
        logger.info(
            f"Agentic learning applied: {learning_applied['corrections_used']} corrections, "
            f"preferences={learning_applied.get('preferences_applied', [])}, "
            f"confidence_calibrated={learning_applied.get('confidence_calibrated', False)}"
        )

    # Record AI decision for concept extraction (agentic learning)
    concept_decision_id = None
    try:
        concept_decision_id = await feedback_service.record_ai_decision(
            decision_type="concept_extraction",
            username=current_user.username,
            input_data={"content_sample": content[:500], "source_type": "text"},
            output_data={"concepts": extraction.get("concepts", []), "skill_level": extraction.get("skill_level")},
            confidence_score=extraction.get("confidence_score", 0.5),
            knowledge_base_id=kb_id,
            model_name="gpt-5-mini"
        )
    except Exception as e:
        logger.warning(f"Failed to record concept extraction decision: {e}")

    # Create metadata
    meta = DocumentMetadata(
        doc_id=None,  # Will be set by repository
        owner=current_user.username,
        source_type="text",
        concepts=[Concept(**c) for c in extraction.get("concepts", [])],
        skill_level=extraction.get("skill_level", "unknown"),
        cluster_id=None,  # Will be set after clustering
        knowledge_base_id=kb_id,
        ingested_at=datetime.utcnow().isoformat(),
        content_length=len(content)
    )

    # Add document using repository
    doc_id = await repo.add_document(content, meta)

    # Find or create cluster
    cluster_id = await find_or_create_cluster(
        doc_id=doc_id,
        suggested_cluster=extraction.get("suggested_cluster", "General"),
        concepts=extraction.get("concepts", []),
        kb_id=kb_id,
        primary_topic=extraction.get("primary_topic")
    )

    # Update metadata with cluster_id and save
    if cluster_id:
        meta.cluster_id = cluster_id
        meta.doc_id = doc_id
        await repo.update_document_metadata(doc_id, meta)

    # Record AI decision for clustering (agentic learning)
    try:
        # Calculate clustering confidence (simple heuristic for now)
        clustering_confidence = 0.75  # Default medium confidence
        if cluster_id and len(extraction.get("concepts", [])) >= 3:
            clustering_confidence = 0.85  # Higher confidence with more concepts

        await feedback_service.record_ai_decision(
            decision_type="clustering",
            username=current_user.username,
            input_data={"concepts": extraction.get("concepts", []), "suggested_cluster": extraction.get("suggested_cluster")},
            output_data={"cluster_id": cluster_id, "cluster_name": extraction.get("suggested_cluster")},
            confidence_score=clustering_confidence,
            knowledge_base_id=kb_id,
            document_id=doc_id,
            cluster_id=cluster_id,
            model_name="heuristic"
        )
    except Exception as e:
        logger.warning(f"Failed to record clustering decision: {e}")

    # Update document count in KB
    from ..db_models import DBKnowledgeBase
    kb = db.query(DBKnowledgeBase).filter_by(id=kb_id).first()
    if kb:
        kb_documents = await repo.get_documents_by_kb(kb_id)
        kb.document_count = len(kb_documents)
        db.commit()

        # Chunk document for RAG (async, runs embeddings)
        chunk_result = None
        try:
            db_doc = db.query(DBDocument).filter_by(doc_id=doc_id).first()
            if db_doc:
                chunk_result = await chunk_document_on_upload(
                    db=db,
                    document=db_doc,
                    content=content,
                    generate_embeddings=True
                )
                logger.info(f"Chunked document {doc_id}: {chunk_result.get('chunks', 0)} chunks created")

                # Document Summarization
                from ..summarization_service import generate_hierarchical_summaries
                from ..db_models import DBDocumentChunk

                summarization_result = {}
                if chunk_result and chunk_result.get('chunks', 0) > 0:
                    try:
                        # Query chunks for summarization
                        db_chunks = db.query(DBDocumentChunk).filter_by(
                            document_id=db_doc.id
                        ).order_by(DBDocumentChunk.chunk_index).all()

                        if db_chunks:
                            # Convert to format expected by summarization service
                            chunks_data = [
                                {
                                    'id': chunk.id,
                                    'content': chunk.content,
                                    'chunk_index': chunk.chunk_index
                                }
                                for chunk in db_chunks
                            ]

                            # Run summarization (already in async context)
                            summarization_result = await generate_hierarchical_summaries(
                                db=db,
                                document_id=db_doc.id,
                                knowledge_base_id=kb_id,
                                chunks=chunks_data,
                                generate_ideas=True
                            )

                            # Update document summary status
                            db_doc.summary_status = 'completed'
                            db.commit()

                            logger.info(
                                f"Generated summaries for doc {doc_id}: "
                                f"{summarization_result.get('chunk_summaries', 0)} chunks, "
                                f"{summarization_result.get('section_summaries', 0)} sections, "
                                f"{summarization_result.get('document_summary', 0)} document"
                            )
                        else:
                            logger.warning(f"No chunks found for document {doc_id}, skipping summarization")
                    except Exception as sum_err:
                        logger.warning(f"Summarization failed (non-critical): {sum_err}")
                        # Update status to failed but don't stop the upload
                        try:
                            db_doc.summary_status = 'failed'
                            db.commit()
                        except Exception as db_err:
                            logger.error(f"Failed to update summary status: {db_err}")
                else:
                    logger.info(f"Summarization skipped - no chunks created for doc {doc_id}")

        except Exception as chunk_err:
            logger.warning(f"Chunking failed for doc {doc_id}: {chunk_err}")
            # Non-fatal - document is still saved, just won't have chunk-based RAG

        # Structured logging with request context
        logger.info(
            f"[{request.state.request_id}] User {current_user.username} uploaded text as doc {doc_id} "
            f"to KB {kb_id} (cluster: {cluster_id}, concepts: {len(extraction.get('concepts', []))})"
        )

        # Invalidate caches (new document added)
        invalidate_analytics(current_user.username)
        invalidate_build_suggestions(current_user.username)
        invalidate_search(current_user.username)

        # Broadcast WebSocket event for real-time updates
        try:
            await broadcast_document_created(
                knowledge_base_id=kb_id,
                doc_id=doc_id,
                title=f"Text Document #{doc_id}",
                source_type="text",
                created_by=current_user.username
            )
        except Exception as ws_err:
            logger.warning(f"WebSocket broadcast failed (non-critical): {ws_err}")

        return {
            "document_id": doc_id,
            "cluster_id": cluster_id,
            "knowledge_base_id": kb_id,
            "concepts": extraction.get("concepts", []),
            "chunks_created": chunk_result.get("chunks", 0) if chunk_result else 0,
            "chunking_status": "completed" if chunk_result and chunk_result.get("chunks", 0) > 0 else "pending"
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
    # Validate URL and check for multiple URLs
    url_string = str(doc.url)
    is_valid, urls, error_msg = validate_and_split_url(url_string)

    if not is_valid:
        # Check if multiple URLs were detected
        if len(urls) > 1:
            raise HTTPException(
                status_code=400,
                detail=f"{error_msg} Found URLs: {', '.join(urls[:3])}{'...' if len(urls) > 3 else ''}"
            )
        else:
            raise HTTPException(status_code=400, detail=error_msg)

    url = urls[0]  # Use the validated single URL

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


# =============================================================================
# Batch File Upload Endpoint (Celery)
# =============================================================================

@router.post("/upload_batch")
@limiter.limit("3/minute")
async def upload_batch(
    req: BatchFileUpload,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload multiple files in one request - Background processing with Celery.

    Rate limited to 3 batch uploads per minute (max 20 files per batch).

    Args:
        req: Batch file upload request containing list of files
        request: FastAPI request (for rate limiting)
        current_user: Authenticated user
        db: Database session

    Returns:
        List of job IDs for polling status

    Response:
        {
            "message": "Batch upload queued",
            "total_files": 5,
            "knowledge_base_id": "uuid",
            "jobs": [
                {"filename": "doc1.pdf", "job_id": "abc123", "status": "queued"},
                {"filename": "doc2.pdf", "job_id": "def456", "status": "queued"},
                ...
            ],
            "errors": []
        }

    Poll /jobs/{job_id}/status for progress on each file.
    """
    # Validate batch size
    if len(req.files) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size exceeds limit. Maximum {MAX_BATCH_SIZE} files per batch (received {len(req.files)})."
        )

    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Check queue depth to prevent overwhelming the system
    try:
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active() or {}
        reserved_tasks = inspect.reserved() or {}

        total_pending = sum(len(tasks) for tasks in active_tasks.values())
        total_pending += sum(len(tasks) for tasks in reserved_tasks.values())

        if total_pending > MAX_QUEUE_DEPTH:
            raise HTTPException(
                status_code=503,
                detail=f"Upload queue is full ({total_pending} pending tasks). Please try again in a few minutes."
            )
    except HTTPException:
        raise
    except Exception as e:
        # If we can't check queue depth (Redis down?), log but continue
        logger.warning(f"Could not check queue depth: {e}")

    # Check concurrent job count - batch counts as multiple jobs
    user_job_count = get_user_job_count(current_user.username)
    max_allowed = 10 - user_job_count

    if max_allowed <= 0:
        raise HTTPException(
            status_code=429,
            detail="Too many background jobs in progress. Please wait for current uploads to complete."
        )

    jobs = []
    errors = []
    valid_tasks = []
    valid_filenames = []

    # Phase 1: Validate all files and prepare task signatures
    for file_item in req.files:
        # Stop if we've hit the job limit
        if len(valid_tasks) >= max_allowed:
            errors.append({
                "filename": file_item.filename,
                "error": "Job limit reached - file not queued"
            })
            continue

        # Sanitize filename
        filename = sanitize_filename(file_item.filename)

        try:
            # Validate base64 and file size
            file_bytes = base64.b64decode(file_item.content)

            if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
                errors.append({
                    "filename": filename,
                    "error": f"File too large. Maximum size is {MAX_UPLOAD_SIZE_BYTES / (1024*1024):.0f}MB"
                })
                continue

        except Exception as exc:
            errors.append({
                "filename": filename,
                "error": f"Invalid base64 content: {exc}"
            })
            continue

        # Create task signature (don't execute yet)
        task_signature = process_file_upload.signature(
            args=(current_user.username, filename, file_item.content, kb_id),
            immutable=True
        )
        valid_tasks.append(task_signature)
        valid_filenames.append(filename)

    # Phase 2: Execute tasks in chunks to avoid overwhelming workers
    if valid_tasks:
        try:
            all_task_ids = []

            # Process tasks in chunks (e.g., 5 at a time)
            for i in range(0, len(valid_tasks), CHUNK_SIZE):
                chunk = valid_tasks[i:i+CHUNK_SIZE]
                chunk_group = group(chunk)
                chunk_result = chunk_group.apply_async()

                # Collect task IDs from this chunk
                all_task_ids.extend([task.id for task in chunk_result.results])

                logger.debug(
                    f"Queued chunk {i//CHUNK_SIZE + 1}/{(len(valid_tasks)-1)//CHUNK_SIZE + 1}: "
                    f"{len(chunk)} files"
                )

            # Build jobs response with all task IDs
            for task_id, filename in zip(all_task_ids, valid_filenames):
                # Increment job count for each queued task
                increment_user_job_count(current_user.username)

                jobs.append({
                    "filename": filename,
                    "job_id": task_id,
                    "status": "queued"
                })

            logger.info(
                f"[{request.state.request_id}] User {current_user.username} queued batch file upload (CHUNKED): "
                f"{len(jobs)} files to KB {kb_id} in {(len(valid_tasks)-1)//CHUNK_SIZE + 1} chunks"
            )
        except Exception as celery_err:
            # Celery/Redis not available - add to errors
            error_msg = f"Background processing unavailable: {str(celery_err)[:100]}"
            logger.error(f"Celery group execution failed: {celery_err}")

            # Add all filenames to errors since execution failed
            for filename in valid_filenames:
                errors.append({
                    "filename": filename,
                    "error": error_msg
                })

            raise HTTPException(
                status_code=503,
                detail="Background processing service unavailable. Redis/Celery may not be running."
            )

    return {
        "message": "Batch upload queued (chunked processing)",
        "total_files": len(req.files),
        "queued": len(jobs),
        "knowledge_base_id": kb_id,
        "jobs": jobs,
        "errors": errors
    }


# =============================================================================
# Batch URL Upload Endpoint (Celery)
# =============================================================================

@router.post("/upload_batch_urls")
@limiter.limit("3/minute")
async def upload_batch_urls(
    req: BatchUrlUpload,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload multiple URLs in one request - Background processing with Celery.

    Rate limited to 3 batch uploads per minute (max 10 URLs per batch).

    Args:
        req: Batch URL upload request containing list of URLs
        request: FastAPI request (for rate limiting)
        current_user: Authenticated user
        db: Database session

    Returns:
        List of job IDs for polling status

    Response:
        {
            "message": "Batch URL upload queued",
            "total_urls": 5,
            "knowledge_base_id": "uuid",
            "jobs": [
                {"url": "https://youtube.com/...", "job_id": "abc123", "status": "queued"},
                {"url": "https://example.com/...", "job_id": "def456", "status": "queued"},
                ...
            ],
            "errors": []
        }

    Poll /jobs/{job_id}/status for progress on each URL.
    """
    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Check concurrent job count
    user_job_count = get_user_job_count(current_user.username)
    max_allowed = 10 - user_job_count

    if max_allowed <= 0:
        raise HTTPException(
            status_code=429,
            detail="Too many background jobs in progress. Please wait for current uploads to complete."
        )

    jobs = []
    errors = []
    valid_tasks = []
    valid_urls = []

    # Phase 1: Validate all URLs and prepare task signatures
    for url_item in req.urls:
        # Stop if we've hit the job limit
        if len(valid_tasks) >= max_allowed:
            errors.append({
                "url": url_item[:100],
                "error": "Job limit reached - URL not queued"
            })
            continue

        # Sanitize and validate URL
        url_item = url_item.strip()
        if not url_item:
            errors.append({
                "url": "(empty)",
                "error": "Empty URL"
            })
            continue

        # Check if this URL item contains multiple URLs
        detected_urls = detect_multiple_urls(url_item)

        if len(detected_urls) == 0:
            errors.append({
                "url": url_item[:100],
                "error": "No valid URL detected in string"
            })
            continue

        if len(detected_urls) > 1:
            errors.append({
                "url": url_item[:100],
                "error": f"Multiple URLs detected in single entry ({len(detected_urls)} URLs). Please submit each URL separately."
            })
            continue

        url = detected_urls[0]

        # Validate the single URL
        try:
            url = validate_url(url)
        except HTTPException as ve:
            errors.append({
                "url": url[:100],
                "error": str(ve.detail)
            })
            continue

        # Create task signature (don't execute yet)
        task_signature = process_url_upload.signature(
            args=(current_user.username, url, kb_id),
            immutable=True
        )
        valid_tasks.append(task_signature)
        valid_urls.append(url)

    # Phase 2: Execute all valid tasks in parallel using group
    if valid_tasks:
        try:
            # Execute tasks in parallel
            job_group = group(valid_tasks)
            group_result = job_group.apply_async()

            # Get individual task IDs from the group
            for i, (task_result, url) in enumerate(zip(group_result.results, valid_urls)):
                # Increment job count for each queued task
                increment_user_job_count(current_user.username)

                jobs.append({
                    "url": url[:100],  # Truncate long URLs in response
                    "job_id": task_result.id,
                    "status": "queued"
                })

            logger.info(
                f"[{request.state.request_id}] User {current_user.username} queued batch URL upload IN PARALLEL: "
                f"{len(jobs)} URLs to KB {kb_id} (group_id: {group_result.id})"
            )

        except Exception as celery_err:
            # Celery/Redis not available - add to errors
            error_msg = f"Background processing unavailable: {str(celery_err)[:100]}"
            logger.error(f"Celery group execution failed: {celery_err}")

            # Add all URLs to errors since parallel execution failed
            for url in valid_urls:
                errors.append({
                    "url": url[:100],
                    "error": error_msg
                })

            raise HTTPException(
                status_code=503,
                detail="Background processing service unavailable. Redis/Celery may not be running."
            )

    return {
        "message": "Batch URL upload queued (parallel processing)",
        "total_urls": len(req.urls),
        "queued": len(jobs),
        "knowledge_base_id": kb_id,
        "jobs": jobs,
        "errors": errors
    }
