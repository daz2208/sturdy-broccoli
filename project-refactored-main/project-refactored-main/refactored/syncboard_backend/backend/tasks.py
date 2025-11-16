"""
Celery Background Tasks for SyncBoard 3.0 Knowledge Bank.

This module defines all background tasks that run asynchronously:
- File upload processing (PDF, images, videos)
- URL/YouTube content ingestion
- Duplicate detection
- Build suggestions generation
- Analytics caching

Each task updates its progress state for real-time frontend feedback.
"""

import base64
import logging
from datetime import datetime
from typing import List, Dict, Optional
from celery import Task

from .celery_app import celery_app
from .models import DocumentMetadata, Concept
from .dependencies import (
    documents,
    metadata,
    clusters,
    users,
    vector_store,
    concept_extractor,
    clustering_engine,
    image_processor,
    build_suggester,
)
from .sanitization import sanitize_filename, sanitize_text_content, validate_url
from .constants import MAX_UPLOAD_SIZE_BYTES
from . import ingest
from .db_storage_adapter import save_storage_to_db

# Initialize logger
logger = logging.getLogger(__name__)

# =============================================================================
# Helper Functions
# =============================================================================

def find_or_create_cluster_sync(
    doc_id: int,
    suggested_cluster: str,
    concepts_list: List[Dict],
    skill_level: str
) -> int:
    """
    Synchronous version of find_or_create_cluster for Celery tasks.

    Args:
        doc_id: Document ID
        suggested_cluster: Suggested cluster name
        concepts_list: List of concept dictionaries
        skill_level: Document skill level

    Returns:
        Cluster ID
    """
    # Try to find existing cluster
    cluster_id = clustering_engine.find_best_cluster(
        doc_concepts=concepts_list,
        suggested_name=suggested_cluster,
        existing_clusters=clusters
    )

    if cluster_id is not None:
        clustering_engine.add_to_cluster(cluster_id, doc_id, clusters)
        return cluster_id

    # Create new cluster
    cluster_id = clustering_engine.create_cluster(
        doc_id=doc_id,
        name=suggested_cluster,
        concepts=concepts_list,
        skill_level=skill_level,
        existing_clusters=clusters
    )

    return cluster_id


# =============================================================================
# File Upload Task
# =============================================================================

@celery_app.task(bind=True, name="backend.tasks.process_file_upload")
def process_file_upload(
    self: Task,
    user_id: str,
    filename: str,
    content_base64: str
) -> Dict:
    """
    Process file upload in background.

    Progress stages:
    1. Decoding file
    2. Extracting text
    3. AI analysis (concept extraction)
    4. Clustering
    5. Saving to database

    Args:
        self: Celery task instance (for progress updates)
        user_id: Username of uploader
        filename: Original filename
        content_base64: Base64-encoded file content

    Returns:
        dict: {doc_id, cluster_id, concepts, filename}

    Raises:
        Exception: If processing fails at any stage
    """
    try:
        # Stage 1: Decode file
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "decoding",
                "message": "Decoding file...",
                "percent": 10
            }
        )

        filename_safe = sanitize_filename(filename)
        file_bytes = base64.b64decode(content_base64)

        # Validate file size
        if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
            raise ValueError(
                f"File too large. Maximum size is {MAX_UPLOAD_SIZE_BYTES / (1024*1024):.0f}MB"
            )

        # Stage 2: Extract text
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "extracting_text",
                "message": f"Extracting text from {filename_safe}...",
                "percent": 25
            }
        )

        document_text = ingest.ingest_upload_file(filename_safe, file_bytes)

        # Stage 3: AI analysis
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "ai_analysis",
                "message": "Running AI concept extraction...",
                "percent": 50
            }
        )

        # Note: concept_extractor.extract() is async, but we're in a sync Celery task
        # We need to run it in an event loop
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        extraction = loop.run_until_complete(
            concept_extractor.extract(document_text, "file")
        )

        # Stage 4: Clustering
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "clustering",
                "message": "Assigning to knowledge cluster...",
                "percent": 75
            }
        )

        # Add to vector store
        doc_id = vector_store.add_document(document_text)
        documents[doc_id] = document_text

        # Create metadata
        meta = DocumentMetadata(
            doc_id=doc_id,
            owner=user_id,
            source_type="file",
            filename=filename_safe,
            concepts=[Concept(**c) for c in extraction.get("concepts", [])],
            skill_level=extraction.get("skill_level", "unknown"),
            cluster_id=None,
            ingested_at=datetime.utcnow().isoformat(),
            content_length=len(document_text)
        )
        metadata[doc_id] = meta

        # Find or create cluster
        cluster_id = find_or_create_cluster_sync(
            doc_id=doc_id,
            suggested_cluster=extraction.get("suggested_cluster", "General"),
            concepts_list=extraction.get("concepts", []),
            skill_level=meta.skill_level
        )
        metadata[doc_id].cluster_id = cluster_id

        # Stage 5: Save to database
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "saving",
                "message": "Saving to database...",
                "percent": 90
            }
        )

        save_storage_to_db(documents, metadata, clusters, users)

        logger.info(
            f"Background task: User {user_id} uploaded file {filename_safe} as doc {doc_id} "
            f"(cluster: {cluster_id})"
        )

        # Return success result
        return {
            "doc_id": doc_id,
            "cluster_id": cluster_id,
            "concepts": extraction.get("concepts", []),
            "filename": filename_safe,
            "user_id": user_id
        }

    except Exception as e:
        logger.error(f"File upload task failed: {e}", exc_info=True)
        self.update_state(
            state="FAILURE",
            meta={
                "error": str(e),
                "message": f"Failed to process {filename}: {str(e)}"
            }
        )
        raise


# =============================================================================
# URL Upload Task
# =============================================================================

@celery_app.task(bind=True, name="backend.tasks.process_url_upload")
def process_url_upload(
    self: Task,
    user_id: str,
    url: str
) -> Dict:
    """
    Process URL/YouTube upload in background.

    Progress stages:
    1. Downloading content
    2. Extracting text
    3. AI analysis
    4. Clustering
    5. Saving

    Args:
        self: Celery task instance
        user_id: Username
        url: URL to ingest

    Returns:
        dict: {doc_id, cluster_id, concepts, url}
    """
    try:
        # Stage 1: Download
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "downloading",
                "message": f"Downloading content from {url}...",
                "percent": 20
            }
        )

        url_safe = validate_url(url)
        document_text = ingest.download_url(url_safe)

        # Stage 2: AI analysis
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "ai_analysis",
                "message": "Running AI concept extraction...",
                "percent": 50
            }
        )

        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        extraction = loop.run_until_complete(
            concept_extractor.extract(document_text, "url")
        )

        # Stage 3: Clustering
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "clustering",
                "message": "Assigning to knowledge cluster...",
                "percent": 75
            }
        )

        # Add to vector store
        doc_id = vector_store.add_document(document_text)
        documents[doc_id] = document_text

        # Create metadata
        meta = DocumentMetadata(
            doc_id=doc_id,
            owner=user_id,
            source_type="url",
            source_url=url_safe,
            concepts=[Concept(**c) for c in extraction.get("concepts", [])],
            skill_level=extraction.get("skill_level", "unknown"),
            cluster_id=None,
            ingested_at=datetime.utcnow().isoformat(),
            content_length=len(document_text)
        )
        metadata[doc_id] = meta

        # Find or create cluster
        cluster_id = find_or_create_cluster_sync(
            doc_id=doc_id,
            suggested_cluster=extraction.get("suggested_cluster", "General"),
            concepts_list=extraction.get("concepts", []),
            skill_level=meta.skill_level
        )
        metadata[doc_id].cluster_id = cluster_id

        # Stage 4: Save
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "saving",
                "message": "Saving to database...",
                "percent": 90
            }
        )

        save_storage_to_db(documents, metadata, clusters, users)

        logger.info(f"Background task: User {user_id} uploaded URL {url_safe} as doc {doc_id}")

        return {
            "doc_id": doc_id,
            "cluster_id": cluster_id,
            "concepts": extraction.get("concepts", []),
            "url": url_safe,
            "user_id": user_id
        }

    except Exception as e:
        logger.error(f"URL upload task failed: {e}", exc_info=True)
        self.update_state(
            state="FAILURE",
            meta={
                "error": str(e),
                "message": f"Failed to process URL {url}: {str(e)}"
            }
        )
        raise


# =============================================================================
# Image Upload Task
# =============================================================================

@celery_app.task(bind=True, name="backend.tasks.process_image_upload")
def process_image_upload(
    self: Task,
    user_id: str,
    filename: str,
    content_base64: str,
    description: Optional[str] = None
) -> Dict:
    """
    Process image upload with OCR in background.

    Args:
        self: Celery task instance
        user_id: Username
        filename: Original filename
        content_base64: Base64-encoded image
        description: Optional description

    Returns:
        dict: {doc_id, cluster_id, concepts, image_path, ocr_length}
    """
    try:
        # Stage 1: Decode image
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "decoding",
                "message": "Decoding image...",
                "percent": 10
            }
        )

        filename_safe = sanitize_filename(filename)
        image_bytes = base64.b64decode(content_base64)

        if len(image_bytes) > MAX_UPLOAD_SIZE_BYTES:
            raise ValueError(f"Image too large. Maximum size is {MAX_UPLOAD_SIZE_BYTES / (1024*1024):.0f}MB")

        # Stage 2: OCR processing
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "ocr",
                "message": "Running OCR on image...",
                "percent": 30
            }
        )

        ocr_text = image_processor.extract_text_from_image(image_bytes)

        # Combine OCR text with description
        if description:
            combined_text = f"{description}\n\n{ocr_text}"
        else:
            combined_text = ocr_text

        # Stage 3: AI analysis
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "ai_analysis",
                "message": "Running AI concept extraction...",
                "percent": 60
            }
        )

        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        extraction = loop.run_until_complete(
            concept_extractor.extract(combined_text, "image")
        )

        # Add to vector store
        doc_id = vector_store.add_document(combined_text)
        documents[doc_id] = combined_text

        # Store image file
        image_path = image_processor.store_image(image_bytes, doc_id, filename_safe)

        # Create metadata
        meta = DocumentMetadata(
            doc_id=doc_id,
            owner=user_id,
            source_type="image",
            filename=filename_safe,
            image_path=image_path,
            concepts=[Concept(**c) for c in extraction.get("concepts", [])],
            skill_level=extraction.get("skill_level", "unknown"),
            cluster_id=None,
            ingested_at=datetime.utcnow().isoformat(),
            content_length=len(combined_text)
        )
        metadata[doc_id] = meta

        # Clustering
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "clustering",
                "message": "Assigning to cluster...",
                "percent": 80
            }
        )

        cluster_id = find_or_create_cluster_sync(
            doc_id=doc_id,
            suggested_cluster=extraction.get("suggested_cluster", "General"),
            concepts_list=extraction.get("concepts", []),
            skill_level=meta.skill_level
        )
        metadata[doc_id].cluster_id = cluster_id

        # Save
        save_storage_to_db(documents, metadata, clusters, users)

        logger.info(f"Background task: User {user_id} uploaded image {filename_safe} as doc {doc_id}")

        return {
            "doc_id": doc_id,
            "cluster_id": cluster_id,
            "concepts": extraction.get("concepts", []),
            "image_path": image_path,
            "ocr_text_length": len(ocr_text),
            "user_id": user_id
        }

    except Exception as e:
        logger.error(f"Image upload task failed: {e}", exc_info=True)
        self.update_state(
            state="FAILURE",
            meta={
                "error": str(e),
                "message": f"Failed to process image {filename}: {str(e)}"
            }
        )
        raise


# =============================================================================
# Duplicate Detection Task
# =============================================================================

@celery_app.task(bind=True, name="backend.tasks.find_duplicates_background")
def find_duplicates_background(
    self: Task,
    user_id: str,
    threshold: float = 0.85
) -> Dict:
    """
    Find duplicates in background (O(n²) operation).

    Args:
        self: Celery task instance
        user_id: Username
        threshold: Similarity threshold

    Returns:
        dict: {duplicate_groups: [...]}
    """
    try:
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "analyzing",
                "message": "Analyzing documents for duplicates...",
                "percent": 50
            }
        )

        # Import here to avoid circular dependency
        from .routers.duplicates import find_duplicate_groups

        # Get user's documents
        user_docs = {
            doc_id: meta
            for doc_id, meta in metadata.items()
            if meta.owner == user_id
        }

        # Find duplicates
        duplicate_groups = find_duplicate_groups(
            user_docs=user_docs,
            threshold=threshold
        )

        logger.info(
            f"Background task: Found {len(duplicate_groups)} duplicate groups for user {user_id}"
        )

        return {
            "duplicate_groups": duplicate_groups,
            "user_id": user_id,
            "threshold": threshold
        }

    except Exception as e:
        logger.error(f"Duplicate detection task failed: {e}", exc_info=True)
        self.update_state(
            state="FAILURE",
            meta={
                "error": str(e),
                "message": f"Failed to find duplicates: {str(e)}"
            }
        )
        raise


# =============================================================================
# Build Suggestions Task
# =============================================================================

@celery_app.task(bind=True, name="backend.tasks.generate_build_suggestions")
def generate_build_suggestions(
    self: Task,
    user_id: str,
    max_suggestions: int = 5
) -> Dict:
    """
    Generate build suggestions in background.

    Args:
        self: Celery task instance
        user_id: Username
        max_suggestions: Maximum number of suggestions

    Returns:
        dict: {suggestions: [...]}
    """
    try:
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "analyzing",
                "message": "Analyzing your knowledge bank...",
                "percent": 30
            }
        )

        # Get user's data
        user_docs = {
            doc_id: meta
            for doc_id, meta in metadata.items()
            if meta.owner == user_id
        }

        user_clusters = {
            cluster_id: cluster
            for cluster_id, cluster in clusters.items()
            if cluster_id in [meta.cluster_id for meta in user_docs.values()]
        }

        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "generating",
                "message": "Generating build suggestions...",
                "percent": 70
            }
        )

        # Generate suggestions
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        suggestions = loop.run_until_complete(
            build_suggester.generate_suggestions(
                clusters=user_clusters,
                metadata=user_docs,
                documents=documents,
                max_suggestions=max_suggestions
            )
        )

        logger.info(
            f"Background task: Generated {len(suggestions)} build suggestions for user {user_id}"
        )

        return {
            "suggestions": suggestions,
            "user_id": user_id
        }

    except Exception as e:
        logger.error(f"Build suggestions task failed: {e}", exc_info=True)
        self.update_state(
            state="FAILURE",
            meta={
                "error": str(e),
                "message": f"Failed to generate suggestions: {str(e)}"
            }
        )
        raise
