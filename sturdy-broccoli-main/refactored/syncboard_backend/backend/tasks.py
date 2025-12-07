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
from celery.signals import worker_process_init
from sqlalchemy import func

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
    get_kb_documents,
    get_kb_metadata,
    get_kb_clusters,
    ensure_kb_exists,
)
from .sanitization import sanitize_filename, sanitize_text_content, validate_url
from .constants import MAX_UPLOAD_SIZE_BYTES
from .config import settings
from . import ingest
from .db_storage_adapter import load_storage_from_db
from .db_repository import DatabaseKnowledgeBankRepository
from .redis_client import notify_data_changed
from .chunking_pipeline import chunk_document_on_upload
from .db_models import DBDocument
from .database import get_db_context
from .websocket_manager import (
    broadcast_document_created,
    broadcast_cluster_created,
    broadcast_job_completed,
    broadcast_job_failed
)
from .feedback_service import feedback_service
import asyncio

# Initialize logger
logger = logging.getLogger(__name__)


def run_async(coro):
    """
    Safely run an async coroutine from sync Celery context.

    Handles the case where an event loop may or may not exist.
    This avoids 'run_async() cannot be called from a running event loop' errors.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, safe to use asyncio.run()
        return asyncio.run(coro)
    else:
        # Loop exists, create a new one in a thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            # CRITICAL FIX: Increased timeout from 30s → 300s → 1500s → 3300s (55 minutes)
            # Supports very large batch uploads (e.g., 500+ documents in ZIP)
            # Upload operations include: AI extraction, clustering, DB save, chunking, summarization
            # Stays under Celery's hard limit (3600s/60min) for safety
            # Individual operations still complete in seconds; this prevents spurious timeouts on batch processing
            return future.result(timeout=3300)

CONCEPT_SAMPLE_CHARS = 12_000  # limit sent to LLM for concept extraction
MAX_SINGLE_DOCUMENT_CHARS = 200_000  # cap single-document payloads to keep processing responsive


def chunk_document_sync(doc_id: int, content: str, kb_id: str) -> dict:
    """
    Synchronous wrapper for document chunking (for use in Celery tasks).

    Args:
        doc_id: Document ID (vector store ID)
        content: Document text content
        kb_id: Knowledge base ID

    Returns:
        Chunking result dict or empty dict on failure
    """
    import asyncio

    try:
        with get_db_context() as db:
            db_doc = db.query(DBDocument).filter_by(doc_id=doc_id).first()
            if not db_doc:
                logger.warning(f"Document {doc_id} not found for chunking")
                return {}

            # Run async chunking in sync context
            result = run_async(
                chunk_document_on_upload(
                    db=db,
                    document=db_doc,
                    content=content,
                    generate_embeddings=True
                )
            )
            logger.info(f"Chunked document {doc_id}: {result.get('chunks', 0)} chunks")
            return result
    except Exception as e:
        logger.warning(f"Chunking failed for document {doc_id}: {e}")
        return {}

# =============================================================================
# Helper Functions
# =============================================================================

def sync_vector_store_next_id():
    """
    Synchronize vector_store._next_id with the database MAX(doc_id) + 1.

    This prevents doc_id collisions when the in-memory counter gets out of sync
    with the actual maximum doc_id in the PostgreSQL database.

    Called before batch document operations to ensure atomic doc_id generation.
    """
    try:
        with get_db_context() as db:
            # Query MAX(doc_id) from the database
            max_doc_id = db.query(func.max(DBDocument.doc_id)).scalar()

            if max_doc_id is not None:
                vector_store._next_id = max_doc_id + 1
                logger.info(f"[DOC_ID_SYNC] Synced vector_store._next_id to {vector_store._next_id} (MAX(doc_id)={max_doc_id})")
            else:
                # No documents in database yet
                vector_store._next_id = 0
                logger.info("[DOC_ID_SYNC] No documents in database, setting _next_id to 0")
    except Exception as e:
        logger.error(f"[DOC_ID_SYNC] Failed to sync vector_store._next_id with database: {e}")
        # Don't raise - allow operation to continue with current _next_id

def reload_cache_from_db():
    """Reload in-memory cache from database after Celery task updates."""
    try:
        # Clear vector store first to prevent ID mismatch
        vector_store.docs.clear()
        vector_store.doc_ids.clear()
        vector_store.vectorizer = None
        vector_store.doc_matrix = None

        docs, meta, clusts, usrs = load_storage_from_db(vector_store)

        # FIX: Reset _next_id to prevent doc_id collisions
        # Find the max doc_id across all KBs and set _next_id to max + 1
        all_doc_ids = []
        for kb_docs in docs.values():
            all_doc_ids.extend(kb_docs.keys())

        if all_doc_ids:
            max_doc_id = max(all_doc_ids)
            vector_store._next_id = max_doc_id + 1
        else:
            vector_store._next_id = 0

        documents.clear()
        documents.update(docs)
        metadata.clear()
        metadata.update(meta)
        clusters.clear()
        clusters.update(clusts)
        users.clear()
        users.update(usrs)

        total_docs = sum(len(d) for d in docs.values())
        total_clusters = sum(len(c) for c in clusts.values())
        logger.debug(f"Cache reloaded: {total_docs} documents in {len(docs)} KBs, {total_clusters} clusters, next_id={vector_store._next_id}")
    except Exception as e:
        logger.error(f"Failed to reload cache from database: {e}")

def generate_cluster_name_from_concepts(concepts_list: List[Dict], primary_topic: str = None) -> str:
    """
    Generate a meaningful cluster name from concepts when LLM returns 'General'.

    Args:
        concepts_list: List of concept dictionaries with 'name' and 'category'
        primary_topic: Optional primary topic from extraction

    Returns:
        A descriptive cluster name
    """
    # First try primary_topic if provided
    if primary_topic and primary_topic.lower() not in ['uncategorized', 'unknown', 'general']:
        # Title case the topic
        return primary_topic.replace('_', ' ').title()

    # Fall back to generating name from top concepts
    if not concepts_list:
        return "General"

    # Get top 2-3 concepts by confidence
    sorted_concepts = sorted(
        concepts_list,
        key=lambda c: c.get('confidence', 0.5),
        reverse=True
    )[:3]

    if not sorted_concepts:
        return "General"

    # Use top concept(s) to create name
    top_names = [c.get('name', '').replace('_', ' ').title() for c in sorted_concepts if c.get('name')]

    if len(top_names) >= 2:
        return f"{top_names[0]} & {top_names[1]}"
    elif top_names:
        return top_names[0]

    return "General"


def find_or_create_cluster_sync(
    doc_id: int,
    suggested_cluster: str,
    concepts_list: List[Dict],
    skill_level: str,
    kb_id: str,
    primary_topic: str = None
) -> int:
    """
    Synchronous version of find_or_create_cluster for Celery tasks.

    Args:
        doc_id: Document ID
        suggested_cluster: Suggested cluster name
        concepts_list: List of concept dictionaries
        skill_level: Document skill level
        kb_id: Knowledge base ID
        primary_topic: Optional primary topic for better naming

    Returns:
        Cluster ID
    """
    # Fix: If suggested_cluster is "General" or empty, generate better name from concepts
    if not suggested_cluster or suggested_cluster.lower() == 'general':
        suggested_cluster = generate_cluster_name_from_concepts(concepts_list, primary_topic)
        logger.info(f"Generated cluster name from concepts: '{suggested_cluster}'")

    # Get KB-scoped clusters
    kb_clusters = get_kb_clusters(kb_id)

    # Try to find existing cluster in this KB
    cluster_id = clustering_engine.find_best_cluster(
        doc_concepts=concepts_list,
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
        concepts=concepts_list,
        skill_level=skill_level,
        existing_clusters=kb_clusters
    )

    # Set knowledge_base_id on the cluster
    kb_clusters[cluster_id].knowledge_base_id = kb_id

    # Broadcast WebSocket event for real-time updates (new cluster created)
    try:
        run_async(broadcast_cluster_created(
            knowledge_base_id=kb_id,
            cluster_id=cluster_id,
            cluster_name=kb_clusters[cluster_id].name,
            document_count=len(kb_clusters[cluster_id].doc_ids)
        ))
    except Exception as ws_err:
        logger.warning(f"WebSocket broadcast failed (non-critical): {ws_err}")

    return cluster_id


# =============================================================================
# Worker Initialization Hook
# =============================================================================

@worker_process_init.connect
def initialize_worker_state(**kwargs):
    """
    Ensure each Celery worker process loads the latest documents, metadata,
    and clusters before handling uploads so IDs stay in sync with the DB.
    """
    logger.info("Initializing Celery worker cache from database")
    reload_cache_from_db()


# =============================================================================
# Multi-Document ZIP Processing Helper
# =============================================================================

def process_multi_document_zip(
    self: Task,
    user_id: str,
    filename: str,
    documents_list: List[Dict],
    kb_id: str
) -> Dict:
    """
    Process multiple documents from a ZIP file (smart extraction).

    Each document in the list gets:
    - AI concept extraction
    - Clustering
    - Vector store addition
    - Database persistence
    - Chunking and summarization

    Args:
        self: Celery task instance
        user_id: Username
        filename: Original ZIP filename
        documents_list: List of document dicts from smart ZIP extraction
        kb_id: Knowledge base ID

    Returns:
        dict: {doc_ids: [...], filenames: [...], total_documents: N}
    """
    import asyncio

    logger.info(f"Processing multi-document ZIP: {filename} with {len(documents_list)} documents")

    # CRITICAL FIX: Sync vector_store._next_id with database before batch operations
    # This prevents doc_id collisions when processing multiple documents
    # See: Non-atomic doc_id generation bug where vector store assigns IDs in-memory
    # but database is the source of truth. When these get out of sync, constraint violations occur.
    sync_vector_store_next_id()

    # Get KB-scoped storage
    kb_documents = get_kb_documents(kb_id)
    kb_metadata = get_kb_metadata(kb_id)

    processed_docs = []
    failed_docs = []
    total_docs = len(documents_list)

    for idx, doc_dict in enumerate(documents_list):
        try:
            # Extract document info
            doc_filename = doc_dict.get('filename', f'file_{idx+1}')
            document_text = doc_dict.get('content', '')
            doc_metadata = doc_dict.get('metadata', {})

            # Progress update
            progress = 25 + int((idx / total_docs) * 70)  # 25% to 95%

            self.update_state(
                state="PROCESSING",
                meta={
                    "stage": "processing_zip_files",
                    "message": f"Processing file {idx+1}/{total_docs}: {doc_filename[:40]}...",
                    "percent": progress,
                    "current_file": idx + 1,
                    "total_files": total_docs
                }
            )

            # Skip empty documents
            if not document_text or len(document_text.strip()) < 10:
                logger.warning(f"Skipping empty document: {doc_filename}")
                continue

            # Stage: AI analysis with AGENTIC LEARNING
            # Uses extract_with_learning() which applies past corrections and user preferences
            extraction = run_async(
                concept_extractor.extract_with_learning(
                    content=document_text,
                    source_type="file",
                    username=user_id,
                    knowledge_base_id=kb_id
                )
            )

            # Log learning metadata if applied
            learning_applied = extraction.get("learning_applied", {})
            if learning_applied.get("corrections_used", 0) > 0:
                logger.info(
                    f"Agentic learning applied to ZIP file {doc_filename}: "
                    f"{learning_applied['corrections_used']} corrections used"
                )

            # Record AI decision for concept extraction (agentic learning)
            try:
                run_async(feedback_service.record_ai_decision(
                    decision_type="concept_extraction",
                    username=user_id,
                    input_data={"content_sample": document_text[:500], "source_type": "file", "filename": doc_filename},
                    output_data={"concepts": extraction.get("concepts", []), "skill_level": extraction.get("skill_level"), "learning_applied": learning_applied},
                    confidence_score=extraction.get("confidence_score", 0.5),
                    knowledge_base_id=kb_id,
                    model_name="gpt-5-mini"
                ))
                logger.debug(f"Recorded concept extraction decision for ZIP file {doc_filename} (confidence: {extraction.get('confidence_score', 0.5):.2f})")
            except Exception as e:
                logger.warning(f"Failed to record concept extraction decision: {e}")

            # Add to vector store
            doc_id = vector_store.add_document(document_text)
            kb_documents[doc_id] = document_text

            # Create metadata
            meta = DocumentMetadata(
                doc_id=doc_id,
                owner=user_id,
                source_type="file",
                filename=doc_filename,
                concepts=[Concept(**c) for c in extraction.get("concepts", [])],
                skill_level=extraction.get("skill_level", "unknown"),
                cluster_id=None,
                knowledge_base_id=kb_id,
                ingested_at=datetime.utcnow().isoformat(),
                content_length=len(document_text)
            )
            kb_metadata[doc_id] = meta

            # Find or create cluster
            cluster_id = find_or_create_cluster_sync(
                doc_id=doc_id,
                suggested_cluster=extraction.get("suggested_cluster", "General"),
                concepts_list=extraction.get("concepts", []),
                skill_level=meta.skill_level,
                kb_id=kb_id,
                primary_topic=extraction.get("primary_topic")
            )
            kb_metadata[doc_id].cluster_id = cluster_id

            # Save document to database immediately via repository
            # This ensures doc_id and cluster_id exist before recording AI decisions
            with get_db_context() as db:
                repo = DatabaseKnowledgeBankRepository(db)
                run_async(repo.add_document(document_text, meta))

            # Record AI decision for clustering (agentic learning)
            # Must happen AFTER document save so cluster exists in DB
            try:
                clustering_confidence = 0.75  # Default medium confidence
                if cluster_id and len(extraction.get("concepts", [])) >= 3:
                    clustering_confidence = 0.85  # Higher confidence with more concepts

                run_async(feedback_service.record_ai_decision(
                    decision_type="clustering",
                    username=user_id,
                    input_data={"concepts": extraction.get("concepts", []), "suggested_cluster": extraction.get("suggested_cluster")},
                    output_data={"cluster_id": cluster_id, "cluster_name": extraction.get("suggested_cluster")},
                    confidence_score=clustering_confidence,
                    knowledge_base_id=kb_id,
                    document_id=doc_id,
                    cluster_id=cluster_id,
                    model_name="heuristic"
                ))
                logger.debug(f"Recorded clustering decision for ZIP doc {doc_id} → cluster {cluster_id} (confidence: {clustering_confidence:.2f})")
            except Exception as e:
                logger.warning(f"Failed to record clustering decision: {e}")

            # Chunk document for RAG
            chunk_result = chunk_document_sync(doc_id, document_text, kb_id)

            # Document Summarization
            summarization_result = {}
            if chunk_result.get('chunks', 0) > 0:
                try:
                    from .summarization_service import generate_hierarchical_summaries

                    with get_db_context() as db:
                        db_doc = db.query(DBDocument).filter_by(doc_id=doc_id).first()
                        if db_doc:
                            from .db_models import DBDocumentChunk

                            db_chunks = db.query(DBDocumentChunk).filter_by(
                                document_id=db_doc.id
                            ).order_by(DBDocumentChunk.chunk_index).all()

                            if db_chunks:
                                chunks_data = [
                                    {
                                        'id': chunk.id,
                                        'content': chunk.content,
                                        'chunk_index': chunk.chunk_index
                                    }
                                    for chunk in db_chunks
                                ]

                                try:
                                    loop = asyncio.get_event_loop()
                                except RuntimeError:
                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)

                                summarization_result = loop.run_until_complete(
                                    generate_hierarchical_summaries(
                                        db=db,
                                        document_id=db_doc.id,
                                        knowledge_base_id=kb_id,
                                        chunks=chunks_data,
                                        generate_ideas=True
                                    )
                                )

                                db_doc.summary_status = 'completed'
                                db.commit()
                except Exception as e:
                    logger.warning(f"Summarization failed for {doc_filename}: {e}")

            # Stage: Generate idea seeds (auto-generate build ideas from summaries)
            # This was MISSING - ZIP-extracted documents weren't getting quick ideas generated!
            if summarization_result.get('status') == 'success':
                try:
                    from .idea_seeds_service import generate_document_idea_seeds
                    # Get document ID from database
                    with get_db_context() as db:
                        db_doc = db.query(DBDocument).filter_by(doc_id=doc_id).first()
                        if db_doc:
                            internal_doc_id = db_doc.id
                        else:
                            internal_doc_id = None

                    # Generate ideas (manages its own db session to avoid transaction warnings)
                    if internal_doc_id:
                        idea_result = run_async(generate_document_idea_seeds(
                            document_id=internal_doc_id,
                            knowledge_base_id=kb_id
                        ))
                        logger.info(f"Generated {idea_result.get('ideas_generated', 0)} idea seeds for ZIP doc {doc_id}")
                except Exception as e:
                    logger.warning(f"Idea seed generation failed for ZIP doc {doc_filename}: {e}")

            # Track processed document
            processed_docs.append({
                "doc_id": doc_id,
                "filename": doc_filename,
                "cluster_id": cluster_id,
                "concepts": len(extraction.get("concepts", [])),
                "chunks": chunk_result.get("chunks", 0),
                "folder": doc_dict.get('folder'),
                "original_zip": filename
            })

            logger.info(
                f"Processed ZIP document {idx+1}/{total_docs}: {doc_filename} → "
                f"doc_id={doc_id}, cluster={cluster_id}, chunks={chunk_result.get('chunks', 0)}"
            )

        except Exception as e:
            logger.error(f"Failed to process ZIP document {doc_filename}: {e}", exc_info=True)
            failed_docs.append({
                "filename": doc_filename,
                "error": str(e),
                "index": idx
            })
            continue

    # Reload cache and notify
    # Documents already saved via repository in the loop above
    reload_cache_from_db()
    notify_data_changed()

    # Log completion with failure summary
    if failed_docs:
        logger.warning(
            f"Multi-document ZIP processing completed WITH FAILURES: {filename} → "
            f"{len(processed_docs)}/{total_docs} succeeded, {len(failed_docs)} failed"
        )
    else:
        logger.info(
            f"Multi-document ZIP processing complete: {filename} → "
            f"{len(processed_docs)}/{total_docs} documents successfully processed"
        )

    # Return summary including failures
    return {
        "status": "multi_document_success" if not failed_docs else "multi_document_partial",
        "original_filename": filename,
        "total_documents": len(processed_docs),
        "total_failed": len(failed_docs),
        "doc_ids": [d["doc_id"] for d in processed_docs],
        "filenames": [d["filename"] for d in processed_docs],
        "documents": processed_docs,
        "failed_documents": failed_docs,
        "user_id": user_id,
        "knowledge_base_id": kb_id
    }


# =============================================================================
# File Upload Task
# =============================================================================

@celery_app.task(bind=True, name="backend.tasks.process_file_upload")
def process_file_upload(
    self: Task,
    user_id: str,
    filename: str,
    content_base64: str,
    kb_id: str
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
        kb_id: Knowledge base ID

    Returns:
        dict: {doc_id, cluster_id, concepts, filename, knowledge_base_id}

    Raises:
        Exception: If processing fails at any stage
    """
    # Ensure KB exists in memory
    ensure_kb_exists(kb_id)
    try:
        # Stage 1: Decode file
        filename_safe = sanitize_filename(filename)
        logger.info(f"Starting file upload task for {filename_safe} (kb={kb_id}, user={user_id})")
        file_bytes = base64.b64decode(content_base64)

        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "decoding",
                "message": f"Decoding file: {filename_safe} ({len(file_bytes):,} bytes)",
                "percent": 10
            }
        )

        # Validate file size
        if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
            raise ValueError(
                f"File too large. Maximum size is {MAX_UPLOAD_SIZE_BYTES / (1024*1024):.0f}MB"
            )

        # Stage 2: Extract text
        file_ext = filename_safe.split('.')[-1].upper() if '.' in filename_safe else 'UNKNOWN'
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "extracting_text",
                "message": f"Extracting text from {file_ext} file: {filename_safe}...",
                "percent": 25
            }
        )

        # Use clean_for_ai=True to remove formatting metadata from ZIP files
        # This helps AI concept extraction work better on archived content
        document_text_or_list = ingest.ingest_upload_file(filename_safe, file_bytes, clean_for_ai=True)

        # Check if ZIP returned multiple documents (smart extraction)
        if isinstance(document_text_or_list, list):
            # MULTI-DOCUMENT ZIP EXTRACTION: Process each file separately
            return process_multi_document_zip(
                self=self,
                user_id=user_id,
                filename=filename_safe,
                documents_list=document_text_or_list,
                kb_id=kb_id
            )

        # SINGLE DOCUMENT: Continue with existing flow
        document_text = document_text_or_list
        original_length = len(document_text)
        if original_length > MAX_SINGLE_DOCUMENT_CHARS:
            logger.info(
                f"Truncating large single-document payload from {original_length:,} to "
                f"{MAX_SINGLE_DOCUMENT_CHARS:,} characters for processing"
            )
            document_text = document_text[:MAX_SINGLE_DOCUMENT_CHARS]
        logger.info(
            f"File upload will be processed as single document: {filename_safe} "
            f"({len(document_text):,} chars, original {original_length:,})"
        )

        # Stage 3: AI analysis
        content_length = len(document_text)
        cache_status = "checking cache" if settings.enable_concept_caching else "analyzing"
        analysis_sample_len = min(content_length, CONCEPT_SAMPLE_CHARS)
        if content_length > analysis_sample_len:
            logger.info(
                f"Sampling {analysis_sample_len:,} chars from {content_length:,} for concept extraction"
            )
        analysis_text = document_text[:analysis_sample_len]
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "ai_analysis",
                "message": (
                    f"AI analysis: {cache_status} for {content_length:,} character document "
                    f"(sampling {analysis_sample_len:,} chars)..."
                ),
                "percent": 50
            }
        )

        # AGENTIC LEARNING: Use extract_with_learning() which applies past corrections
        # This closes the feedback loop - the system actually learns from user corrections
        import asyncio
        extraction = run_async(
            concept_extractor.extract_with_learning(
                content=analysis_text,
                source_type="file",
                username=user_id,
                knowledge_base_id=kb_id
            )
        )

        # Log learning metadata if applied
        learning_applied = extraction.get("learning_applied", {})
        if learning_applied.get("corrections_used", 0) > 0:
            logger.info(
                f"Agentic learning applied to file {filename_safe}: "
                f"{learning_applied['corrections_used']} corrections, "
                f"preferences={learning_applied.get('preferences_applied', [])}"
            )

        # Record AI decision for concept extraction (agentic learning)
        try:
            run_async(feedback_service.record_ai_decision(
                decision_type="concept_extraction",
                username=user_id,
                input_data={"content_sample": analysis_text[:500], "source_type": "file", "filename": filename_safe},
                output_data={"concepts": extraction.get("concepts", []), "skill_level": extraction.get("skill_level"), "learning_applied": learning_applied},
                confidence_score=extraction.get("confidence_score", 0.5),
                knowledge_base_id=kb_id,
                model_name="gpt-5-mini"
            ))
            logger.debug(f"Recorded concept extraction decision for file {filename_safe} (confidence: {extraction.get('confidence_score', 0.5):.2f})")
        except Exception as e:
            logger.warning(f"Failed to record concept extraction decision: {e}")

        # Stage 4: Clustering
        concept_count = len(extraction.get('concepts', []))
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "clustering",
                "message": f"Clustering: Found {concept_count} high-confidence concepts, assigning to knowledge cluster...",
                "percent": 75
            }
        )

        # Get KB-scoped storage
        kb_documents = get_kb_documents(kb_id)
        kb_metadata = get_kb_metadata(kb_id)

        # CRITICAL FIX: Sync vector_store._next_id with database to prevent collisions
        # Even single uploads need this in concurrent scenarios
        sync_vector_store_next_id()

        # Add to vector store
        doc_id = vector_store.add_document(document_text)
        kb_documents[doc_id] = document_text

        # Create metadata
        meta = DocumentMetadata(
            doc_id=doc_id,
            owner=user_id,
            source_type="file",
            filename=filename_safe,
            concepts=[Concept(**c) for c in extraction.get("concepts", [])],
            skill_level=extraction.get("skill_level", "unknown"),
            cluster_id=None,
            knowledge_base_id=kb_id,
            ingested_at=datetime.utcnow().isoformat(),
            content_length=len(document_text)
        )
        kb_metadata[doc_id] = meta

        # Find or create cluster
        cluster_id = find_or_create_cluster_sync(
            doc_id=doc_id,
            suggested_cluster=extraction.get("suggested_cluster", "General"),
            concepts_list=extraction.get("concepts", []),
            skill_level=meta.skill_level,
            kb_id=kb_id,
            primary_topic=extraction.get("primary_topic")
        )
        kb_metadata[doc_id].cluster_id = cluster_id

        # Stage 5: Save to database via repository
        skill_level = extraction.get('skill_level', 'unknown')
        primary_topic = extraction.get('primary_topic', 'uncategorized')
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "saving",
                "message": f"Saving: {concept_count} concepts, skill level: {skill_level}, topic: {primary_topic}",
                "percent": 90
            }
        )

        with get_db_context() as db:
            repo = DatabaseKnowledgeBankRepository(db)
            run_async(repo.add_document(document_text, meta))

        # Record AI decision for clustering (agentic learning)
        # Must happen AFTER document save so cluster exists in DB
        try:
            clustering_confidence = 0.75  # Default medium confidence
            if cluster_id and len(extraction.get("concepts", [])) >= 3:
                clustering_confidence = 0.85  # Higher confidence with more concepts

            run_async(feedback_service.record_ai_decision(
                decision_type="clustering",
                username=user_id,
                input_data={"concepts": extraction.get("concepts", []), "suggested_cluster": extraction.get("suggested_cluster")},
                output_data={"cluster_id": cluster_id, "cluster_name": extraction.get("suggested_cluster")},
                confidence_score=clustering_confidence,
                knowledge_base_id=kb_id,
                document_id=doc_id,
                cluster_id=cluster_id,
                model_name="heuristic"
            ))
            logger.debug(f"Recorded clustering decision for doc {doc_id} → cluster {cluster_id} (confidence: {clustering_confidence:.2f})")
        except Exception as e:
            logger.warning(f"Failed to record clustering decision: {e}")
        reload_cache_from_db()
        notify_data_changed()  # Notify backend to reload

        # Stage 6: Chunk document for RAG
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "chunking",
                "message": f"Chunking: Creating searchable chunks from {content_length:,} characters for RAG system...",
                "percent": 95
            }
        )

        chunk_result = chunk_document_sync(doc_id, document_text, kb_id)

        # Stage 7: Document Summarization
        chunk_count = chunk_result.get('chunks', 0)
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "summarizing",
                "message": f"Summarizing: Generating hierarchical summaries for {chunk_count} chunks (chunk → section → document)...",
                "percent": 97
            }
        )

        from .summarization_service import generate_hierarchical_summaries

        summarization_result = {}
        if chunk_result.get('chunks', 0) > 0:
            try:
                # Get database document and chunks
                with get_db_context() as db:
                    db_doc = db.query(DBDocument).filter_by(doc_id=doc_id).first()
                    if db_doc:
                        from .db_models import DBDocumentChunk

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

                            # Run async summarization in sync context
                            import asyncio
                            try:
                                loop = asyncio.get_event_loop()
                            except RuntimeError:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)

                            summarization_result = loop.run_until_complete(
                                generate_hierarchical_summaries(
                                    db=db,
                                    document_id=db_doc.id,
                                    knowledge_base_id=kb_id,
                                    chunks=chunks_data,
                                    generate_ideas=True
                                )
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
                    else:
                        logger.warning(f"Document {doc_id} not found in database for summarization")
            except Exception as e:
                logger.warning(f"Summarization failed (non-critical): {e}")
                # Update status to failed but don't stop the upload
                try:
                    with get_db_context() as db:
                        db_doc = db.query(DBDocument).filter_by(doc_id=doc_id).first()
                        if db_doc:
                            db_doc.summary_status = 'failed'
                            db.commit()
                except Exception as db_err:
                    logger.error(f"Failed to update summary status: {db_err}")
        else:
            logger.info(f"Summarization skipped - no chunks created for doc {doc_id}")

        # Stage 8: Generate idea seeds (auto-generate build ideas from summaries)
        logger.info(f"[DIAG] Stage 8 check: summarization_result.status={summarization_result.get('status')}")
        if summarization_result.get('status') == 'success':
            logger.info(f"[DIAG] Stage 8 ENTERED for doc {doc_id}")
            try:
                from .idea_seeds_service import generate_document_idea_seeds
                # Get document ID from database
                with get_db_context() as db:
                    db_doc = db.query(DBDocument).filter_by(doc_id=doc_id).first()
                    if db_doc:
                        internal_doc_id = db_doc.id
                        logger.info(f"[DIAG] Found internal_doc_id={internal_doc_id}")
                    else:
                        internal_doc_id = None
                        logger.warning(f"[DIAG] No db_doc found for doc_id={doc_id}")

                # Generate ideas (manages its own db session to avoid transaction warnings)
                if internal_doc_id:
                    logger.info(f"[DIAG] Calling generate_document_idea_seeds...")
                    idea_result = run_async(generate_document_idea_seeds(
                        document_id=internal_doc_id,
                        knowledge_base_id=kb_id
                    ))
                    logger.info(f"[DIAG] Seed result: {idea_result}")
                    logger.info(f"Generated {idea_result.get('ideas_generated', 0)} idea seeds for doc {doc_id}")
            except Exception as e:
                logger.error(f"[DIAG] Stage 8 EXCEPTION: {e}", exc_info=True)
        else:
            logger.warning(f"[DIAG] Stage 8 SKIPPED - status='{summarization_result.get('status')}'")

        logger.info(
            f"Background task: User {user_id} uploaded file {filename_safe} as doc {doc_id} "
            f"to KB {kb_id} (cluster: {cluster_id}, chunks: {chunk_result.get('chunks', 0)}, "
            f"summaries: {summarization_result.get('status', 'skipped')})"
        )

        # Broadcast WebSocket event for real-time updates
        try:
            run_async(broadcast_document_created(
                knowledge_base_id=kb_id,
                doc_id=doc_id,
                title=filename_safe,
                source_type="file",
                created_by=user_id
            ))
        except Exception as ws_err:
            logger.warning(f"WebSocket broadcast failed (non-critical): {ws_err}")

        # Broadcast job completion for progress UI
        try:
            run_async(broadcast_job_completed(
                username=user_id,
                job_id=self.request.id,
                job_type="file_upload",
                result={
                    "doc_id": doc_id,
                    "filename": filename_safe,
                    "chunks_created": chunk_result.get("chunks", 0)
                }
            ))
        except Exception as ws_err:
            logger.warning(f"Job completion broadcast failed (non-critical): {ws_err}")

        # Return success result
        return {
            "doc_id": doc_id,
            "cluster_id": cluster_id,
            "concepts": extraction.get("concepts", []),
            "filename": filename_safe,
            "user_id": user_id,
            "knowledge_base_id": kb_id,
            "chunks_created": chunk_result.get("chunks", 0)
        }

    except Exception as e:
        logger.error(f"File upload task failed: {e}", exc_info=True)

        # CLEANUP: Rollback and remove partial data
        try:
            # Clean up vector store if doc_id was created
            if 'doc_id' in locals() and doc_id:
                try:
                    vector_store.delete_document(doc_id)
                    logger.debug(f"Cleaned up vector store entry for doc {doc_id}")
                except Exception as vs_err:
                    logger.warning(f"Failed to clean up vector store: {vs_err}")

                # Clean up KB documents and metadata
                try:
                    kb_documents = get_kb_documents(kb_id)
                    kb_metadata = get_kb_metadata(kb_id)
                    kb_documents.pop(doc_id, None)
                    kb_metadata.pop(doc_id, None)
                    logger.debug(f"Cleaned up KB memory for doc {doc_id}")
                except Exception as kb_err:
                    logger.warning(f"Failed to clean up KB memory: {kb_err}")

                # Clean up database entry if it exists
                try:
                    with get_db_context() as db:
                        db_doc = db.query(DBDocument).filter_by(doc_id=doc_id).first()
                        if db_doc:
                            db.delete(db_doc)
                            db.commit()
                            logger.debug(f"Cleaned up database entry for doc {doc_id}")
                except Exception as db_err:
                    logger.warning(f"Failed to clean up database: {db_err}")
        except Exception as cleanup_err:
            logger.error(f"Cleanup after failure encountered error: {cleanup_err}")

        self.update_state(
            state="FAILURE",
            meta={
                "error": str(e),
                "message": f"Failed to process {filename}: {str(e)}"
            }
        )

        # Broadcast job failure
        try:
            run_async(broadcast_job_failed(
                username=user_id,
                job_id=self.request.id,
                job_type="file_upload",
                error=str(e)
            ))
        except Exception as ws_err:
            logger.warning(f"Job failure broadcast failed (non-critical): {ws_err}")
        raise


# =============================================================================
# URL Upload Task
# =============================================================================

@celery_app.task(bind=True, name="backend.tasks.process_url_upload")
def process_url_upload(
    self: Task,
    user_id: str,
    url: str,
    kb_id: str
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
        kb_id: Knowledge base ID

    Returns:
        dict: {doc_id, cluster_id, concepts, url, knowledge_base_id}
    """
    # Ensure KB exists in memory
    ensure_kb_exists(kb_id)
    try:
        # Stage 1: Download
        url_safe = validate_url(url)
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "downloading",
                "message": f"Downloading: Fetching content from {url_safe[:80]}...",
                "percent": 20
            }
        )

        document_text = ingest.download_url(url_safe)
        content_length = len(document_text)

        # Detect YouTube content for enhanced AI extraction
        is_youtube = "YOUTUBE VIDEO TRANSCRIPT" in document_text

        # Stage 2: AI analysis
        cache_status = "checking cache" if settings.enable_concept_caching else "analyzing"
        content_type = "YouTube video" if is_youtube else "web page"
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "ai_analysis",
                "message": f"AI analysis: {cache_status} {content_type} ({content_length:,} chars, smart sampling: 6000)...",
                "percent": 50
            }
        )

        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # AGENTIC LEARNING: Use extract_with_learning() for YouTube/URL extraction
        # Pass 'youtube' as source_type for YouTube videos to trigger enhanced extraction
        source_type = "youtube" if is_youtube else "url"
        extraction = loop.run_until_complete(
            concept_extractor.extract_with_learning(
                content=document_text,
                source_type=source_type,
                username=user_id,
                knowledge_base_id=kb_id
            )
        )

        # Log learning metadata if applied
        learning_applied = extraction.get("learning_applied", {})
        if learning_applied.get("corrections_used", 0) > 0:
            logger.info(
                f"Agentic learning applied to {source_type} {url_safe[:50]}: "
                f"{learning_applied['corrections_used']} corrections, "
                f"preferences={learning_applied.get('preferences_applied', [])}"
            )

        # Record AI decision for concept extraction (agentic learning)
        try:
            loop.run_until_complete(feedback_service.record_ai_decision(
                decision_type="concept_extraction",
                username=user_id,
                input_data={"content_sample": document_text[:500], "source_type": source_type, "url": url_safe[:100]},
                output_data={"concepts": extraction.get("concepts", []), "skill_level": extraction.get("skill_level"), "learning_applied": learning_applied},
                confidence_score=extraction.get("confidence_score", 0.5),
                knowledge_base_id=kb_id,
                model_name="gpt-5-mini"
            ))
            logger.debug(f"Recorded concept extraction decision for URL {url_safe[:50]} (confidence: {extraction.get('confidence_score', 0.5):.2f})")
        except Exception as e:
            logger.warning(f"Failed to record concept extraction decision: {e}")

        # Extract YouTube-specific metadata from AI response
        youtube_metadata = {}
        if is_youtube:
            youtube_metadata = {
                'video_title': extraction.get('title'),
                'video_creator': extraction.get('creator'),
                'video_type': extraction.get('video_type'),
                'target_audience': extraction.get('target_audience'),
                'key_takeaways': extraction.get('key_takeaways', []),
                'estimated_watch_time': extraction.get('estimated_watch_time')
            }
            logger.info(
                f"Extracted YouTube metadata: title='{youtube_metadata['video_title']}', "
                f"creator={youtube_metadata['video_creator']}, type={youtube_metadata['video_type']}"
            )

        # Stage 3: Clustering
        concept_count = len(extraction.get('concepts', []))
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "clustering",
                "message": f"Clustering: Found {concept_count} high-confidence concepts, assigning to knowledge cluster...",
                "percent": 75
            }
        )

        # Get KB-scoped storage
        kb_documents = get_kb_documents(kb_id)
        kb_metadata = get_kb_metadata(kb_id)

        # CRITICAL FIX: Sync vector_store._next_id with database to prevent collisions
        sync_vector_store_next_id()

        # Add to vector store
        doc_id = vector_store.add_document(document_text)
        kb_documents[doc_id] = document_text

        # Create metadata
        meta = DocumentMetadata(
            doc_id=doc_id,
            owner=user_id,
            source_type="url",
            source_url=url_safe,
            filename=youtube_metadata.get('video_title') if is_youtube else None,
            concepts=[Concept(**c) for c in extraction.get("concepts", [])],
            skill_level=extraction.get("skill_level", "unknown"),
            cluster_id=None,
            knowledge_base_id=kb_id,
            ingested_at=datetime.utcnow().isoformat(),
            content_length=len(document_text)
        )
        kb_metadata[doc_id] = meta

        # Save YouTube-specific metadata to database
        if is_youtube and youtube_metadata.get('video_title'):
            try:
                with get_db_context() as db:
                    db_doc = db.query(DBDocument).filter_by(doc_id=doc_id).first()
                    if db_doc:
                        db_doc.video_title = youtube_metadata.get('video_title')
                        db_doc.video_creator = youtube_metadata.get('video_creator')
                        db_doc.video_type = youtube_metadata.get('video_type')
                        db_doc.target_audience = youtube_metadata.get('target_audience')
                        db_doc.key_takeaways = youtube_metadata.get('key_takeaways')
                        db_doc.estimated_watch_time = youtube_metadata.get('estimated_watch_time')
                        db.commit()
                        logger.info(f"Saved YouTube metadata for doc {doc_id}")
            except Exception as e:
                logger.warning(f"Failed to save YouTube metadata for doc {doc_id}: {e}")

        # Find or create cluster
        cluster_id = find_or_create_cluster_sync(
            doc_id=doc_id,
            suggested_cluster=extraction.get("suggested_cluster", "General"),
            concepts_list=extraction.get("concepts", []),
            skill_level=meta.skill_level,
            kb_id=kb_id,
            primary_topic=extraction.get("primary_topic")
        )
        kb_metadata[doc_id].cluster_id = cluster_id

        # Stage 4: Save
        skill_level = extraction.get('skill_level', 'unknown')
        primary_topic = extraction.get('primary_topic', 'uncategorized')
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "saving",
                "message": f"Saving: {concept_count} concepts, skill level: {skill_level}, topic: {primary_topic}",
                "percent": 90
            }
        )

        with get_db_context() as db:
            repo = DatabaseKnowledgeBankRepository(db)
            run_async(repo.add_document(document_text, meta))

        # Record AI decision for clustering (agentic learning)
        # Must happen AFTER document save so cluster exists in DB
        try:
            clustering_confidence = 0.75  # Default medium confidence
            if cluster_id and len(extraction.get("concepts", [])) >= 3:
                clustering_confidence = 0.85  # Higher confidence with more concepts

            loop.run_until_complete(feedback_service.record_ai_decision(
                decision_type="clustering",
                username=user_id,
                input_data={"concepts": extraction.get("concepts", []), "suggested_cluster": extraction.get("suggested_cluster")},
                output_data={"cluster_id": cluster_id, "cluster_name": extraction.get("suggested_cluster")},
                confidence_score=clustering_confidence,
                knowledge_base_id=kb_id,
                document_id=doc_id,
                cluster_id=cluster_id,
                model_name="heuristic"
            ))
            logger.debug(f"Recorded clustering decision for URL doc {doc_id} → cluster {cluster_id} (confidence: {clustering_confidence:.2f})")
        except Exception as e:
            logger.warning(f"Failed to record clustering decision: {e}")
        reload_cache_from_db()
        notify_data_changed()  # Notify backend to reload

        # Stage 5: Chunk document for RAG
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "chunking",
                "message": f"Chunking: Creating searchable chunks from {content_length:,} characters for RAG system...",
                "percent": 95
            }
        )

        chunk_result = chunk_document_sync(doc_id, document_text, kb_id)

        # Stage 6: Document Summarization
        chunk_count = chunk_result.get('chunks', 0)
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "summarizing",
                "message": f"Summarizing: Generating hierarchical summaries for {chunk_count} chunks (chunk → section → document)...",
                "percent": 97
            }
        )

        from .summarization_service import generate_hierarchical_summaries

        summarization_result = {}
        if chunk_result.get('chunks', 0) > 0:
            try:
                # Get database document and chunks
                with get_db_context() as db:
                    db_doc = db.query(DBDocument).filter_by(doc_id=doc_id).first()
                    if db_doc:
                        from .db_models import DBDocumentChunk

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

                            # Run async summarization in sync context
                            import asyncio
                            try:
                                loop = asyncio.get_event_loop()
                            except RuntimeError:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)

                            summarization_result = loop.run_until_complete(
                                generate_hierarchical_summaries(
                                    db=db,
                                    document_id=db_doc.id,
                                    knowledge_base_id=kb_id,
                                    chunks=chunks_data,
                                    generate_ideas=True
                                )
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
                    else:
                        logger.warning(f"Document {doc_id} not found in database for summarization")
            except Exception as e:
                logger.warning(f"Summarization failed (non-critical): {e}")
                # Update status to failed but don't stop the upload
                try:
                    with get_db_context() as db:
                        db_doc = db.query(DBDocument).filter_by(doc_id=doc_id).first()
                        if db_doc:
                            db_doc.summary_status = 'failed'
                            db.commit()
                except Exception as db_err:
                    logger.error(f"Failed to update summary status: {db_err}")
        else:
            logger.info(f"Summarization skipped - no chunks created for doc {doc_id}")

        # Stage 8: Generate idea seeds (auto-generate build ideas from summaries)
        logger.info(f"[DIAG] Stage 8 check: summarization_result.status={summarization_result.get('status')}")
        if summarization_result.get('status') == 'success':
            logger.info(f"[DIAG] Stage 8 ENTERED for doc {doc_id}")
            try:
                from .idea_seeds_service import generate_document_idea_seeds
                # Get document ID from database
                with get_db_context() as db:
                    db_doc = db.query(DBDocument).filter_by(doc_id=doc_id).first()
                    if db_doc:
                        internal_doc_id = db_doc.id
                        logger.info(f"[DIAG] Found internal_doc_id={internal_doc_id}")
                    else:
                        internal_doc_id = None
                        logger.warning(f"[DIAG] No db_doc found for doc_id={doc_id}")

                # Generate ideas (manages its own db session to avoid transaction warnings)
                if internal_doc_id:
                    logger.info(f"[DIAG] Calling generate_document_idea_seeds...")
                    idea_result = run_async(generate_document_idea_seeds(
                        document_id=internal_doc_id,
                        knowledge_base_id=kb_id
                    ))
                    logger.info(f"[DIAG] Seed result: {idea_result}")
                    logger.info(f"Generated {idea_result.get('ideas_generated', 0)} idea seeds for doc {doc_id}")
            except Exception as e:
                logger.error(f"[DIAG] Stage 8 EXCEPTION: {e}", exc_info=True)
        else:
            logger.warning(f"[DIAG] Stage 8 SKIPPED - status='{summarization_result.get('status')}'")

        logger.info(
            f"Background task: User {user_id} uploaded URL {url_safe} as doc {doc_id} to KB {kb_id} "
            f"(chunks: {chunk_result.get('chunks', 0)}, summaries: {summarization_result.get('status', 'skipped')})"
        )

        # Broadcast WebSocket event for real-time updates
        try:
            run_async(broadcast_document_created(
                knowledge_base_id=kb_id,
                doc_id=doc_id,
                title=youtube_metadata.get('video_title', url_safe[:50]) if is_youtube else url_safe[:50],
                source_type="url",
                created_by=user_id
            ))
        except Exception as ws_err:
            logger.warning(f"WebSocket broadcast failed (non-critical): {ws_err}")

        # Broadcast job completion for progress UI
        try:
            run_async(broadcast_job_completed(
                username=user_id,
                job_id=self.request.id,
                job_type="url_upload",
                result={
                    "doc_id": doc_id,
                    "url": url_safe[:100],
                    "chunks_created": chunk_result.get("chunks", 0)
                }
            ))
        except Exception as ws_err:
            logger.warning(f"Job completion broadcast failed (non-critical): {ws_err}")

        return {
            "doc_id": doc_id,
            "cluster_id": cluster_id,
            "concepts": extraction.get("concepts", []),
            "url": url_safe,
            "user_id": user_id,
            "knowledge_base_id": kb_id,
            "chunks_created": chunk_result.get("chunks", 0)
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
        # Broadcast job failure
        try:
            run_async(broadcast_job_failed(
                username=user_id,
                job_id=self.request.id,
                job_type="url_upload",
                error=str(e)
            ))
        except Exception as ws_err:
            logger.warning(f"Job failure broadcast failed (non-critical): {ws_err}")
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
    description: Optional[str] = None,
    kb_id: str = None
) -> Dict:
    """
    Process image upload with OCR in background.

    Args:
        self: Celery task instance
        user_id: Username
        filename: Original filename
        content_base64: Base64-encoded image
        description: Optional description
        kb_id: Knowledge base ID

    Returns:
        dict: {doc_id, cluster_id, concepts, image_path, ocr_length, knowledge_base_id}
    """
    # Ensure KB exists in memory
    if kb_id:
        ensure_kb_exists(kb_id)
    try:
        # Stage 1: Decode image
        filename_safe = sanitize_filename(filename)
        image_bytes = base64.b64decode(content_base64)

        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "decoding",
                "message": f"Decoding image: {filename_safe} ({len(image_bytes):,} bytes)",
                "percent": 10
            }
        )

        if len(image_bytes) > MAX_UPLOAD_SIZE_BYTES:
            raise ValueError(f"Image too large. Maximum size is {MAX_UPLOAD_SIZE_BYTES / (1024*1024):.0f}MB")

        # Stage 2: OCR processing
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "ocr",
                "message": f"OCR: Extracting text from image using Tesseract ({len(image_bytes):,} bytes)...",
                "percent": 30
            }
        )

        ocr_text = image_processor.extract_text_from_image(image_bytes)

        # Combine OCR text with description
        if description:
            combined_text = f"{description}\n\n{ocr_text}"
        else:
            combined_text = ocr_text

        content_length = len(combined_text)

        # Stage 3: AI analysis
        cache_status = "checking cache" if settings.enable_concept_caching else "analyzing"
        ocr_length = len(ocr_text)
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "ai_analysis",
                "message": f"AI analysis: {cache_status} OCR text ({ocr_length:,} chars extracted, smart sampling: 6000)...",
                "percent": 60
            }
        )

        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # AGENTIC LEARNING: Use extract_with_learning() for image extraction
        extraction = loop.run_until_complete(
            concept_extractor.extract_with_learning(
                content=combined_text,
                source_type="image",
                username=user_id,
                knowledge_base_id=kb_id if kb_id else "default"
            )
        )

        # Log learning metadata if applied
        learning_applied = extraction.get("learning_applied", {})
        if learning_applied.get("corrections_used", 0) > 0:
            logger.info(
                f"Agentic learning applied to image {filename_safe}: "
                f"{learning_applied['corrections_used']} corrections, "
                f"preferences={learning_applied.get('preferences_applied', [])}"
            )

        # Record AI decision for concept extraction (agentic learning)
        try:
            loop.run_until_complete(feedback_service.record_ai_decision(
                decision_type="concept_extraction",
                username=user_id,
                input_data={"content_sample": combined_text[:500], "source_type": "image", "filename": filename_safe},
                output_data={"concepts": extraction.get("concepts", []), "skill_level": extraction.get("skill_level"), "learning_applied": learning_applied},
                confidence_score=extraction.get("confidence_score", 0.5),
                knowledge_base_id=kb_id if kb_id else "default",
                model_name="gpt-5-mini"
            ))
            logger.debug(f"Recorded concept extraction decision for image {filename_safe} (confidence: {extraction.get('confidence_score', 0.5):.2f})")
        except Exception as e:
            logger.warning(f"Failed to record concept extraction decision: {e}")

        # Get KB-scoped storage (use default if kb_id not provided for backward compat)
        if kb_id:
            kb_documents = get_kb_documents(kb_id)
            kb_metadata = get_kb_metadata(kb_id)
        else:
            # Fallback for backward compatibility
            kb_documents = get_kb_documents("default")
            kb_metadata = get_kb_metadata("default")
            kb_id = "default"

        # CRITICAL FIX: Sync vector_store._next_id with database to prevent collisions
        sync_vector_store_next_id()

        # Add to vector store
        doc_id = vector_store.add_document(combined_text)
        kb_documents[doc_id] = combined_text

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
            knowledge_base_id=kb_id,
            ingested_at=datetime.utcnow().isoformat(),
            content_length=len(combined_text)
        )
        kb_metadata[doc_id] = meta

        # Clustering
        concept_count = len(extraction.get('concepts', []))
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "clustering",
                "message": f"Clustering: Found {concept_count} high-confidence concepts, assigning to knowledge cluster...",
                "percent": 80
            }
        )

        cluster_id = find_or_create_cluster_sync(
            doc_id=doc_id,
            suggested_cluster=extraction.get("suggested_cluster", "General"),
            concepts_list=extraction.get("concepts", []),
            skill_level=meta.skill_level,
            kb_id=kb_id,
            primary_topic=extraction.get("primary_topic")
        )
        kb_metadata[doc_id].cluster_id = cluster_id

        # Save to database via repository
        with get_db_context() as db:
            repo = DatabaseKnowledgeBankRepository(db)
            run_async(repo.add_document(combined_text, meta))

        # Record AI decision for clustering (agentic learning)
        # Must happen AFTER document save so cluster exists in DB
        try:
            clustering_confidence = 0.75  # Default medium confidence
            if cluster_id and len(extraction.get("concepts", [])) >= 3:
                clustering_confidence = 0.85  # Higher confidence with more concepts

            loop.run_until_complete(feedback_service.record_ai_decision(
                decision_type="clustering",
                username=user_id,
                input_data={"concepts": extraction.get("concepts", []), "suggested_cluster": extraction.get("suggested_cluster")},
                output_data={"cluster_id": cluster_id, "cluster_name": extraction.get("suggested_cluster")},
                confidence_score=clustering_confidence,
                knowledge_base_id=kb_id,
                document_id=doc_id,
                cluster_id=cluster_id,
                model_name="heuristic"
            ))
            logger.debug(f"Recorded clustering decision for image doc {doc_id} → cluster {cluster_id} (confidence: {clustering_confidence:.2f})")
        except Exception as e:
            logger.warning(f"Failed to record clustering decision: {e}")
        reload_cache_from_db()
        notify_data_changed()  # Notify backend to reload

        # Stage 5: Chunk document for RAG
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "chunking",
                "message": f"Chunking: Creating searchable chunks from {content_length:,} characters for RAG system...",
                "percent": 95
            }
        )

        chunk_result = chunk_document_sync(doc_id, combined_text, kb_id)

        # Stage 6: Document Summarization
        chunk_count = chunk_result.get('chunks', 0)
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "summarizing",
                "message": f"Summarizing: Generating hierarchical summaries for {chunk_count} chunks (chunk → section → document)...",
                "percent": 97
            }
        )

        from .summarization_service import generate_hierarchical_summaries

        summarization_result = {}
        if chunk_result.get('chunks', 0) > 0:
            try:
                # Get database document and chunks
                with get_db_context() as db:
                    db_doc = db.query(DBDocument).filter_by(doc_id=doc_id).first()
                    if db_doc:
                        from .db_models import DBDocumentChunk

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

                            # Run async summarization in sync context
                            import asyncio
                            try:
                                loop = asyncio.get_event_loop()
                            except RuntimeError:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)

                            summarization_result = loop.run_until_complete(
                                generate_hierarchical_summaries(
                                    db=db,
                                    document_id=db_doc.id,
                                    knowledge_base_id=kb_id,
                                    chunks=chunks_data,
                                    generate_ideas=True
                                )
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
                    else:
                        logger.warning(f"Document {doc_id} not found in database for summarization")
            except Exception as e:
                logger.warning(f"Summarization failed (non-critical): {e}")
                # Update status to failed but don't stop the upload
                try:
                    with get_db_context() as db:
                        db_doc = db.query(DBDocument).filter_by(doc_id=doc_id).first()
                        if db_doc:
                            db_doc.summary_status = 'failed'
                            db.commit()
                except Exception as db_err:
                    logger.error(f"Failed to update summary status: {db_err}")
        else:
            logger.info(f"Summarization skipped - no chunks created for doc {doc_id}")

        # Stage 8: Generate idea seeds (auto-generate build ideas from summaries)
        logger.info(f"[DIAG] Stage 8 check: summarization_result.status={summarization_result.get('status')}")
        if summarization_result.get('status') == 'success':
            logger.info(f"[DIAG] Stage 8 ENTERED for doc {doc_id}")
            try:
                from .idea_seeds_service import generate_document_idea_seeds
                # Get document ID from database
                with get_db_context() as db:
                    db_doc = db.query(DBDocument).filter_by(doc_id=doc_id).first()
                    if db_doc:
                        internal_doc_id = db_doc.id
                        logger.info(f"[DIAG] Found internal_doc_id={internal_doc_id}")
                    else:
                        internal_doc_id = None
                        logger.warning(f"[DIAG] No db_doc found for doc_id={doc_id}")

                # Generate ideas (manages its own db session to avoid transaction warnings)
                if internal_doc_id:
                    logger.info(f"[DIAG] Calling generate_document_idea_seeds...")
                    idea_result = run_async(generate_document_idea_seeds(
                        document_id=internal_doc_id,
                        knowledge_base_id=kb_id
                    ))
                    logger.info(f"[DIAG] Seed result: {idea_result}")
                    logger.info(f"Generated {idea_result.get('ideas_generated', 0)} idea seeds for doc {doc_id}")
            except Exception as e:
                logger.error(f"[DIAG] Stage 8 EXCEPTION: {e}", exc_info=True)
        else:
            logger.warning(f"[DIAG] Stage 8 SKIPPED - status='{summarization_result.get('status')}'")

        logger.info(
            f"Background task: User {user_id} uploaded image {filename_safe} as doc {doc_id} to KB {kb_id} "
            f"(chunks: {chunk_result.get('chunks', 0)}, summaries: {summarization_result.get('status', 'skipped')})"
        )

        # Broadcast WebSocket event for real-time updates
        try:
            run_async(broadcast_document_created(
                knowledge_base_id=kb_id,
                doc_id=doc_id,
                title=filename_safe,
                source_type="image",
                created_by=user_id
            ))
        except Exception as ws_err:
            logger.warning(f"WebSocket broadcast failed (non-critical): {ws_err}")

        # Broadcast job completion for progress UI
        try:
            run_async(broadcast_job_completed(
                username=user_id,
                job_id=self.request.id,
                job_type="image_upload",
                result={
                    "doc_id": doc_id,
                    "filename": filename_safe,
                    "chunks_created": chunk_result.get("chunks", 0)
                }
            ))
        except Exception as ws_err:
            logger.warning(f"Job completion broadcast failed (non-critical): {ws_err}")

        return {
            "doc_id": doc_id,
            "cluster_id": cluster_id,
            "concepts": extraction.get("concepts", []),
            "image_path": image_path,
            "ocr_text_length": len(ocr_text),
            "user_id": user_id,
            "knowledge_base_id": kb_id,
            "chunks_created": chunk_result.get("chunks", 0)
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
        # Broadcast job failure
        try:
            run_async(broadcast_job_failed(
                username=user_id,
                job_id=self.request.id,
                job_type="image_upload",
                error=str(e)
            ))
        except Exception as ws_err:
            logger.warning(f"Job failure broadcast failed (non-critical): {ws_err}")
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
        from .duplicate_detection import DuplicateDetector
        from .dependencies import get_vector_store

        # Use duplicate detector with database context
        with get_db_context() as db:
            detector = DuplicateDetector(db, vector_store)
            result = detector.find_duplicates(
                username=user_id,
                similarity_threshold=threshold,
                limit=100
            )
            duplicate_groups = result.get("groups", [])

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

        # Get user's data (iterate over all KBs - metadata is nested {kb_id: {doc_id: meta}})
        user_docs = {}
        for kb_id, kb_meta in metadata.items():
            for doc_id, meta in kb_meta.items():
                if meta.owner == user_id:
                    user_docs[doc_id] = meta

        # Get user's clusters (clusters is nested {kb_id: {cluster_id: cluster}})
        user_cluster_ids = [meta.cluster_id for meta in user_docs.values() if meta.cluster_id is not None]
        user_clusters = {}
        for kb_id, kb_clusters in clusters.items():
            for cluster_id, cluster in kb_clusters.items():
                if cluster_id in user_cluster_ids:
                    user_clusters[cluster_id] = cluster

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


# =============================================================================
# GitHub Import Task (Phase 5)
# =============================================================================

@celery_app.task(bind=True, name="backend.tasks.import_github_files_task")
def import_github_files_task(
    self: Task,
    user_id: str,
    owner: str,
    repo: str,
    branch: str,
    files: List[str],
    kb_id: str = "default"
) -> Dict:
    """
    Import files from a GitHub repository in background.

    Progress stages:
    1. Fetching GitHub token (0%)
    2. Downloading files from GitHub (20-80%)
    3. Processing files through ingestion pipeline (80-100%)

    Args:
        self: Celery task instance
        user_id: User ID who initiated import
        owner: GitHub repository owner
        repo: GitHub repository name
        branch: Git branch to import from
        files: List of file paths to import
        kb_id: Knowledge base ID

    Returns:
        dict: Import results with doc_ids
    """
    # Ensure KB exists in memory
    ensure_kb_exists(kb_id)
    try:
        logger.info(
            f"Starting GitHub import task for user {user_id}: "
            f"{owner}/{repo}, {len(files)} files"
        )

        # Update state: Fetching token
        self.update_state(
            state="PROCESSING",
            meta={
                "stage": "Fetching GitHub token",
                "message": "Retrieving GitHub access token...",
                "percent": 0,
                "files_processed": 0,
                "files_failed": 0,
                "total_files": len(files)
            }
        )

        # Get GitHub token from database
        from .database import get_db_context
        from .db_models import DBIntegrationToken, DBIntegrationImport
        from .utils.encryption import decrypt_token

        with get_db_context() as db:
            token_record = db.query(DBIntegrationToken).filter_by(
                user_id=user_id,
                service="github"
            ).first()

            if not token_record:
                raise ValueError("GitHub not connected")

            # Decrypt token
            access_token = decrypt_token(token_record.access_token)

            # Update import record status
            import_record = db.query(DBIntegrationImport).filter_by(
                job_id=self.request.id
            ).first()

            if import_record:
                import_record.status = "processing"
                db.commit()

        # GitHub API headers
        import requests
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        # CRITICAL FIX: Sync vector_store._next_id with database before batch operations
        # This prevents doc_id collisions when processing multiple GitHub files
        # See: Non-atomic doc_id generation bug where vector store assigns IDs in-memory
        # but database is the source of truth. When these get out of sync, constraint violations occur.
        sync_vector_store_next_id()

        # Process each file
        imported_docs = []
        failed_files = []
        files_processed = 0

        for idx, file_path in enumerate(files):
            try:
                # Calculate progress (20% to 80% for downloading)
                download_progress = 20 + int((idx / len(files)) * 60)

                self.update_state(
                    state="PROCESSING",
                    meta={
                        "stage": "Downloading files",
                        "message": f"Downloading {file_path}...",
                        "percent": download_progress,
                        "files_processed": files_processed,
                        "files_failed": len(failed_files),
                        "total_files": len(files),
                        "current_file": file_path
                    }
                )

                # Fetch file content from GitHub
                file_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
                params = {"ref": branch}

                response = requests.get(
                    file_url,
                    headers=headers,
                    params=params,
                    timeout=30
                )
                response.raise_for_status()
                file_data = response.json()

                # GitHub returns base64-encoded content
                if file_data.get("encoding") == "base64":
                    content_base64 = file_data["content"]
                    # Remove newlines from GitHub's base64 encoding
                    content_base64 = content_base64.replace("\n", "")
                    file_content = base64.b64decode(content_base64).decode('utf-8', errors='ignore')
                else:
                    # Direct content (for small files)
                    file_content = file_data.get("content", "")

                # Update progress: Processing file
                process_progress = 80 + int((idx / len(files)) * 20)

                self.update_state(
                    state="PROCESSING",
                    meta={
                        "stage": "Processing files",
                        "message": f"Processing {file_path}...",
                        "percent": process_progress,
                        "files_processed": files_processed,
                        "files_failed": len(failed_files),
                        "total_files": len(files),
                        "current_file": file_path
                    }
                )

                # Get KB-scoped storage
                kb_documents = get_kb_documents(kb_id)
                kb_metadata = get_kb_metadata(kb_id)

                # AGENTIC LEARNING: Use extract_with_learning() which applies past corrections
                import asyncio
                extraction = run_async(
                    concept_extractor.extract_with_learning(
                        content=file_content,
                        source_type="github",
                        username=user_id,
                        knowledge_base_id=kb_id
                    )
                )

                # Log learning metadata if applied
                learning_applied = extraction.get("learning_applied", {})
                if learning_applied.get("corrections_used", 0) > 0:
                    logger.info(
                        f"Agentic learning applied to GitHub file {file_path}: "
                        f"{learning_applied['corrections_used']} corrections"
                    )

                # Record AI decision for concept extraction (agentic learning)
                try:
                    run_async(feedback_service.record_ai_decision(
                        decision_type="concept_extraction",
                        username=user_id,
                        input_data={"content_sample": file_content[:500], "source_type": "github", "filename": file_path},
                        output_data={"concepts": extraction.get("concepts", []), "skill_level": extraction.get("skill_level"), "learning_applied": learning_applied},
                        confidence_score=extraction.get("confidence_score", 0.5),
                        knowledge_base_id=kb_id,
                        model_name="gpt-5-mini"
                    ))
                except Exception as e:
                    logger.warning(f"Failed to record concept extraction decision: {e}")

                # Get values from extraction result (not non-existent methods)
                skill_level = extraction.get("skill_level", "unknown")
                suggested_cluster = extraction.get("suggested_cluster", "General")
                concepts_list = extraction.get("concepts", [])
                primary_topic = extraction.get("primary_topic")

                # Add to vector store
                doc_id = vector_store.add_document(file_content)
                kb_documents[doc_id] = file_content

                # Find or create cluster (with kb_id)
                cluster_id = find_or_create_cluster_sync(
                    doc_id=doc_id,
                    suggested_cluster=suggested_cluster,
                    concepts_list=concepts_list,
                    skill_level=skill_level,
                    kb_id=kb_id,
                    primary_topic=primary_topic
                )

                # Store metadata (KB-scoped)
                doc_metadata = DocumentMetadata(
                    doc_id=doc_id,
                    owner=user_id,
                    source_type="github",
                    source_url=file_data.get("html_url"),
                    filename=file_path,
                    concepts=[Concept(**c) for c in concepts_list],
                    cluster_id=cluster_id,
                    skill_level=skill_level,
                    knowledge_base_id=kb_id,
                    content_length=len(file_content),
                    ingested_at=datetime.utcnow().isoformat()
                )
                kb_metadata[doc_id] = doc_metadata

                # Save document to database via repository
                with get_db_context() as db:
                    repo = DatabaseKnowledgeBankRepository(db)
                    run_async(repo.add_document(file_content, doc_metadata))

                # Track imported doc
                imported_docs.append({
                    "doc_id": doc_id,
                    "file_path": file_path,
                    "cluster_id": cluster_id,
                    "skill_level": skill_level,
                    "size": len(file_content)
                })

                files_processed += 1

                logger.info(
                    f"GitHub import: Imported {file_path} → doc_id={doc_id}, "
                    f"cluster_id={cluster_id}"
                )

            except Exception as e:
                logger.error(f"Failed to import {file_path}: {e}", exc_info=True)
                failed_files.append({
                    "file_path": file_path,
                    "error": str(e)
                })

        # Reload cache and notify
        # Documents already saved via repository in the loop above
        try:
            reload_cache_from_db()
            notify_data_changed()  # Notify backend to reload
            logger.info(f"GitHub import: Processed {files_processed} files")
        except Exception as e:
            logger.error(f"Failed to reload cache after GitHub import: {e}")

        # Update import record
        with get_db_context() as db:
            import_record = db.query(DBIntegrationImport).filter_by(
                job_id=self.request.id
            ).first()

            if import_record:
                import_record.status = "completed" if not failed_files else "completed"
                import_record.files_processed = files_processed
                import_record.files_failed = len(failed_files)
                import_record.completed_at = datetime.utcnow()
                db.commit()

        # Final success message
        result = {
            "imported_docs": imported_docs,
            "files_processed": files_processed,
            "files_failed": len(failed_files),
            "failed_files": failed_files,
            "repository": f"{owner}/{repo}",
            "branch": branch
        }

        logger.info(
            f"GitHub import completed: {files_processed} succeeded, "
            f"{len(failed_files)} failed for user {user_id}"
        )

        return result

    except Exception as e:
        logger.error(f"GitHub import task failed: {e}", exc_info=True)

        # Update import record status
        try:
            from .database import get_db_context
            from .db_models import DBIntegrationImport

            with get_db_context() as db:
                import_record = db.query(DBIntegrationImport).filter_by(
                    job_id=self.request.id
                ).first()

                if import_record:
                    import_record.status = "failed"
                    import_record.error_message = str(e)
                    import_record.completed_at = datetime.utcnow()
                    db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update import record: {db_error}")

        self.update_state(
            state="FAILURE",
            meta={
                "error": str(e),
                "message": f"GitHub import failed: {str(e)}"
            }
        )
        raise
