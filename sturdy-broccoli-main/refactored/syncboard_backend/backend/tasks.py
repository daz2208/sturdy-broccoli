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
from .constants import MAX_UPLOAD_SIZE_BYTES, ENABLE_CONCEPT_CACHING
from . import ingest
from .db_storage_adapter import save_storage_to_db, load_storage_from_db
from .redis_client import notify_data_changed
from .chunking_pipeline import chunk_document_on_upload
from .db_models import DBDocument
from .database import get_db_context
from .websocket_manager import broadcast_document_created, broadcast_cluster_created
from .feedback_service import feedback_service
import asyncio

# Initialize logger
logger = logging.getLogger(__name__)

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
            result = asyncio.run(
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

def find_or_create_cluster_sync(
    doc_id: int,
    suggested_cluster: str,
    concepts_list: List[Dict],
    skill_level: str,
    kb_id: str
) -> int:
    """
    Synchronous version of find_or_create_cluster for Celery tasks.

    Args:
        doc_id: Document ID
        suggested_cluster: Suggested cluster name
        concepts_list: List of concept dictionaries
        skill_level: Document skill level
        kb_id: Knowledge base ID

    Returns:
        Cluster ID
    """
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
        asyncio.run(broadcast_cluster_created(
            knowledge_base_id=int(kb_id),
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

    # Get KB-scoped storage
    kb_documents = get_kb_documents(kb_id)
    kb_metadata = get_kb_metadata(kb_id)

    processed_docs = []
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

            # Stage: AI analysis
            extraction = asyncio.run(
                concept_extractor.extract(document_text, "file")
            )

            # Record AI decision for concept extraction (agentic learning)
            try:
                asyncio.run(feedback_service.record_ai_decision(
                    decision_type="concept_extraction",
                    username=user_id,
                    input_data={"content_sample": document_text[:500], "source_type": "file", "filename": doc_filename},
                    output_data={"concepts": extraction.get("concepts", []), "skill_level": extraction.get("skill_level")},
                    confidence_score=extraction.get("confidence_score", 0.5),
                    knowledge_base_id=kb_id,
                    model_name="gpt-4o-mini"
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
                kb_id=kb_id
            )
            kb_metadata[doc_id].cluster_id = cluster_id

            # Record AI decision for clustering (agentic learning)
            try:
                clustering_confidence = 0.75  # Default medium confidence
                if cluster_id and len(extraction.get("concepts", [])) >= 3:
                    clustering_confidence = 0.85  # Higher confidence with more concepts

                asyncio.run(feedback_service.record_ai_decision(
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

            # Save document metadata to database immediately
            # This ensures doc_id exists before chunking
            save_storage_to_db(documents, metadata, clusters, users)

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
                                        generate_ideas=False
                                    )
                                )

                                db_doc.summary_status = 'completed'
                                db.commit()
                except Exception as e:
                    logger.warning(f"Summarization failed for {doc_filename}: {e}")

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
            continue

    # Final save and cache reload
    save_storage_to_db(documents, metadata, clusters, users)
    reload_cache_from_db()
    notify_data_changed()

    logger.info(
        f"Multi-document ZIP processing complete: {filename} → "
        f"{len(processed_docs)}/{total_docs} documents successfully processed"
    )

    # Return summary
    return {
        "status": "multi_document_success",
        "original_filename": filename,
        "total_documents": len(processed_docs),
        "doc_ids": [d["doc_id"] for d in processed_docs],
        "filenames": [d["filename"] for d in processed_docs],
        "documents": processed_docs,
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
        cache_status = "checking cache" if ENABLE_CONCEPT_CACHING else "analyzing"
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

        # Note: concept_extractor.extract() is async, but we're in a sync Celery task
        # Use asyncio.run() which creates a fresh event loop, runs the coroutine, and closes it
        import asyncio
        extraction = asyncio.run(
            concept_extractor.extract(analysis_text, "file")
        )

        # Record AI decision for concept extraction (agentic learning)
        try:
            asyncio.run(feedback_service.record_ai_decision(
                decision_type="concept_extraction",
                username=user_id,
                input_data={"content_sample": analysis_text[:500], "source_type": "file", "filename": filename_safe},
                output_data={"concepts": extraction.get("concepts", []), "skill_level": extraction.get("skill_level")},
                confidence_score=extraction.get("confidence_score", 0.5),
                knowledge_base_id=kb_id,
                model_name="gpt-4o-mini"
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
            kb_id=kb_id
        )
        kb_metadata[doc_id].cluster_id = cluster_id

        # Record AI decision for clustering (agentic learning)
        try:
            clustering_confidence = 0.75  # Default medium confidence
            if cluster_id and len(extraction.get("concepts", [])) >= 3:
                clustering_confidence = 0.85  # Higher confidence with more concepts

            asyncio.run(feedback_service.record_ai_decision(
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

        # Stage 5: Save to database
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

        save_storage_to_db(documents, metadata, clusters, users)
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
                                    generate_ideas=False
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

        logger.info(
            f"Background task: User {user_id} uploaded file {filename_safe} as doc {doc_id} "
            f"to KB {kb_id} (cluster: {cluster_id}, chunks: {chunk_result.get('chunks', 0)}, "
            f"summaries: {summarization_result.get('status', 'skipped')})"
        )

        # Broadcast WebSocket event for real-time updates
        try:
            asyncio.run(broadcast_document_created(
                knowledge_base_id=int(kb_id),
                doc_id=doc_id,
                title=filename_safe,
                source_type="file",
                created_by=user_id
            ))
        except Exception as ws_err:
            logger.warning(f"WebSocket broadcast failed (non-critical): {ws_err}")

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
        cache_status = "checking cache" if ENABLE_CONCEPT_CACHING else "analyzing"
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

        # Pass 'youtube' as source_type for YouTube videos to trigger enhanced extraction
        source_type = "youtube" if is_youtube else "url"
        extraction = loop.run_until_complete(
            concept_extractor.extract(document_text, source_type)
        )

        # Record AI decision for concept extraction (agentic learning)
        try:
            loop.run_until_complete(feedback_service.record_ai_decision(
                decision_type="concept_extraction",
                username=user_id,
                input_data={"content_sample": document_text[:500], "source_type": source_type, "url": url_safe[:100]},
                output_data={"concepts": extraction.get("concepts", []), "skill_level": extraction.get("skill_level")},
                confidence_score=extraction.get("confidence_score", 0.5),
                knowledge_base_id=kb_id,
                model_name="gpt-4o-mini"
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
            kb_id=kb_id
        )
        kb_metadata[doc_id].cluster_id = cluster_id

        # Record AI decision for clustering (agentic learning)
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

        save_storage_to_db(documents, metadata, clusters, users)
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
                                    generate_ideas=False
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

        logger.info(
            f"Background task: User {user_id} uploaded URL {url_safe} as doc {doc_id} to KB {kb_id} "
            f"(chunks: {chunk_result.get('chunks', 0)}, summaries: {summarization_result.get('status', 'skipped')})"
        )

        # Broadcast WebSocket event for real-time updates
        try:
            asyncio.run(broadcast_document_created(
                knowledge_base_id=int(kb_id),
                doc_id=doc_id,
                title=youtube_metadata.get('video_title', url_safe[:50]) if is_youtube else url_safe[:50],
                source_type="url",
                created_by=user_id
            ))
        except Exception as ws_err:
            logger.warning(f"WebSocket broadcast failed (non-critical): {ws_err}")

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
        cache_status = "checking cache" if ENABLE_CONCEPT_CACHING else "analyzing"
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

        extraction = loop.run_until_complete(
            concept_extractor.extract(combined_text, "image")
        )

        # Record AI decision for concept extraction (agentic learning)
        try:
            loop.run_until_complete(feedback_service.record_ai_decision(
                decision_type="concept_extraction",
                username=user_id,
                input_data={"content_sample": combined_text[:500], "source_type": "image", "filename": filename_safe},
                output_data={"concepts": extraction.get("concepts", []), "skill_level": extraction.get("skill_level")},
                confidence_score=extraction.get("confidence_score", 0.5),
                knowledge_base_id=kb_id if kb_id else "default",
                model_name="gpt-4o-mini"
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
            kb_id=kb_id
        )
        kb_metadata[doc_id].cluster_id = cluster_id

        # Record AI decision for clustering (agentic learning)
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

        # Save
        save_storage_to_db(documents, metadata, clusters, users)
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
                                    generate_ideas=False
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

        logger.info(
            f"Background task: User {user_id} uploaded image {filename_safe} as doc {doc_id} to KB {kb_id} "
            f"(chunks: {chunk_result.get('chunks', 0)}, summaries: {summarization_result.get('status', 'skipped')})"
        )

        # Broadcast WebSocket event for real-time updates
        try:
            asyncio.run(broadcast_document_created(
                knowledge_base_id=int(kb_id) if kb_id != "default" else 0,
                doc_id=doc_id,
                title=filename_safe,
                source_type="image",
                created_by=user_id
            ))
        except Exception as ws_err:
            logger.warning(f"WebSocket broadcast failed (non-critical): {ws_err}")

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
    files: List[str]
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

    Returns:
        dict: Import results with doc_ids
    """
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

                # Extract concepts
                concepts_list = concept_extractor.extract_concepts(file_content)

                # Ingest file
                doc_id = ingest.ingest_text(
                    content=file_content,
                    user_id=user_id,
                    source_type="github",
                    source_url=file_data.get("html_url"),
                    filename=file_path,
                    vector_store=vector_store,
                    documents=documents
                )

                # Determine skill level
                skill_level = concept_extractor.determine_skill_level(file_content)

                # Suggest cluster name
                suggested_cluster = clustering_engine.suggest_cluster_name(concepts_list)

                # Find or create cluster
                cluster_id = find_or_create_cluster_sync(
                    doc_id=doc_id,
                    suggested_cluster=suggested_cluster,
                    concepts_list=concepts_list,
                    skill_level=skill_level
                )

                # Store metadata
                doc_metadata = DocumentMetadata(
                    doc_id=doc_id,
                    owner_username=user_id,
                    source_type="github",
                    source_url=file_data.get("html_url"),
                    filename=file_path,
                    cluster_id=cluster_id,
                    skill_level=skill_level,
                    content_length=len(file_content),
                    ingested_at=datetime.utcnow()
                )
                metadata[doc_id] = doc_metadata

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

        # Save to database
        try:
            save_storage_to_db(documents, metadata, clusters, users)
            reload_cache_from_db()
            notify_data_changed()  # Notify backend to reload
            logger.info(f"GitHub import: Saved {files_processed} files to database")
        except Exception as e:
            logger.error(f"Failed to save GitHub import to database: {e}")

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
