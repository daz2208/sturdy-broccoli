"""
Documents Router for SyncBoard 3.0 Knowledge Bank.

Endpoints:
- GET /documents - List all user documents
- GET /documents/{doc_id} - Get a single document
- DELETE /documents/{doc_id} - Delete a document
- PUT /documents/{doc_id}/metadata - Update document metadata
- GET /documents/{doc_id}/summaries - Get document summaries
- POST /documents/{doc_id}/summarize - Generate summaries for a document
"""

import logging
from fastapi import APIRouter, HTTPException, Request, Depends

from ..models import User
from ..dependencies import (
    get_current_user,
    get_repository,
    get_user_default_kb_id,
)
from ..repository_interface import KnowledgeBankRepository
from ..database import get_db
from sqlalchemy.orm import Session
from ..constants import SKILL_LEVELS
from ..redis_client import (
    invalidate_analytics,
    invalidate_build_suggestions,
    invalidate_search
)
from ..websocket_manager import broadcast_document_deleted, broadcast_document_updated
from ..feedback_service import feedback_service

# Initialize logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    responses={401: {"description": "Unauthorized"}},
)

# =============================================================================
# List Documents Endpoint
# =============================================================================

@router.get("")
async def list_documents(
    repo: KnowledgeBankRepository = Depends(get_repository),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all user documents with basic information.

    Args:
        repo: Repository instance (injected)
        user: Authenticated user
        db: Database session

    Returns:
        List of documents with id, title, source_type, ingested_at, chunking_status
    """
    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(user.username, db)

    # Get KB-scoped storage using repository
    kb_metadata = await repo.get_metadata_by_kb(kb_id)

    # Filter documents by user ownership with null coalescing for all optional fields
    # BUG FIX: Handle case where meta.owner might be None
    user_docs = [
        {
            "id": doc_id,
            "title": getattr(meta, 'filename', None) or f"Document {doc_id}",
            "source_type": meta.source_type or "unknown",
            "ingested_at": meta.ingested_at,
            "chunking_status": getattr(meta, 'chunking_status', None) or "unknown",
            "cluster_id": meta.cluster_id,
            "primary_topic": getattr(meta, 'primary_topic', None) or "Uncategorized",
            "skill_level": getattr(meta, 'skill_level', None) or "unknown",
            "filename": getattr(meta, 'filename', None),
            "owner": meta.owner,  # Include owner for debugging
            "knowledge_base_id": meta.knowledge_base_id,  # Required for frontend filtering
            "source_zip_filename": getattr(meta, 'source_zip_filename', None)  # Parent ZIP if extracted from archive
        }
        for doc_id, meta in kb_metadata.items()
        if meta.owner == user.username or meta.owner is None  # Show docs with no owner too
    ]

    # Log for debugging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Documents query for {user.username} in KB {kb_id}: found {len(user_docs)} docs out of {len(kb_metadata)} total")

    return {
        "documents": user_docs,
        "total": len(user_docs),
        "knowledge_base_id": kb_id
    }

# =============================================================================
# Get Document Endpoint
# =============================================================================

@router.get("/{doc_id}")
async def get_document(
    doc_id: int,
    repo: KnowledgeBankRepository = Depends(get_repository),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a single document with metadata.

    Args:
        doc_id: Document ID
        repo: Repository instance (injected)
        user: Authenticated user
        db: Database session

    Returns:
        Document content, metadata, and cluster information

    Raises:
        HTTPException 404: If document not found
    """
    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(user.username, db)

    # Get KB-scoped storage using repository
    kb_documents = await repo.get_documents_by_kb(kb_id)
    kb_metadata = await repo.get_metadata_by_kb(kb_id)
    kb_clusters = await repo.get_clusters_by_kb(kb_id)

    if doc_id not in kb_documents:
        raise HTTPException(404, f"Document {doc_id} not found")

    meta = kb_metadata.get(doc_id)
    cluster_info = None

    if meta and meta.cluster_id is not None:
        cluster = kb_clusters.get(meta.cluster_id)
        if cluster:
            cluster_info = {
                "id": cluster.id,
                "name": cluster.name
            }

    return {
        "doc_id": doc_id,
        "content": kb_documents[doc_id],
        "metadata": meta.dict() if meta else None,
        "cluster": cluster_info,
        "knowledge_base_id": kb_id
    }

# =============================================================================
# Download Document Endpoint
# =============================================================================

@router.get("/{doc_id}/download")
async def download_document(
    doc_id: int,
    repo: KnowledgeBankRepository = Depends(get_repository),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Download a document as a text file.

    Args:
        doc_id: Document ID
        repo: Repository instance (injected)
        user: Authenticated user
        db: Database session

    Returns:
        Plain text file download

    Raises:
        HTTPException 404: If document not found
    """
    from fastapi.responses import Response

    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(user.username, db)

    # Get KB-scoped storage using repository
    kb_documents = await repo.get_documents_by_kb(kb_id)
    kb_metadata = await repo.get_metadata_by_kb(kb_id)

    if doc_id not in kb_documents:
        raise HTTPException(404, f"Document {doc_id} not found")

    meta = kb_metadata.get(doc_id)
    content = kb_documents[doc_id]

    # Create filename
    if meta and meta.filename:
        # Use existing filename without extension, add .txt
        safe_filename = "".join(c for c in meta.filename if c.isalnum() or c in (' ', '-', '_', '.')).strip()
        # Remove extension if present and add .txt
        if '.' in safe_filename:
            safe_filename = safe_filename.rsplit('.', 1)[0]
        filename = f"{safe_filename}.txt"
    else:
        filename = f"document_{doc_id}.txt"

    return Response(
        content=content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\""
        }
    )

# =============================================================================
# Delete Document Endpoint
# =============================================================================

@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    request: Request,
    repo: KnowledgeBankRepository = Depends(get_repository),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a document from the knowledge bank.

    Args:
        doc_id: Document ID
        request: FastAPI request (for logging)
        repo: Repository instance (injected)
        user: Authenticated user
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException 404: If document not found
    """
    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(user.username, db)

    # Get metadata to check ownership and cluster info
    meta = await repo.get_document_metadata(doc_id)
    if not meta:
        raise HTTPException(404, f"Document {doc_id} not found")

    # Verify document belongs to user's KB
    if meta.knowledge_base_id != kb_id:
        raise HTTPException(404, f"Document {doc_id} not found")

    # Store cluster_id and source_type for logging before deletion
    cluster_id = meta.cluster_id
    source_type = meta.source_type

    # Delete document using repository
    success = await repo.delete_document(doc_id)
    if not success:
        raise HTTPException(500, "Failed to delete document")

    # Update document count in KB
    from ..db_models import DBKnowledgeBase
    kb = db.query(DBKnowledgeBase).filter_by(id=kb_id).first()
    if kb:
        # Count documents in this KB
        kb_documents = await repo.get_documents_by_kb(kb_id)
        kb.document_count = len(kb_documents)
        db.commit()

    # Invalidate caches (knowledge bank content changed)
    invalidate_analytics(user.username)
    invalidate_build_suggestions(user.username)
    invalidate_search(user.username)
    logger.info(f"Invalidated caches for {user.username} after document deletion")

    # Structured logging with request context
    logger.info(
        f"[{request.state.request_id}] User {user.username} deleted document {doc_id} "
        f"from KB {kb_id} (cluster: {cluster_id}, source: {source_type})"
    )

    # Broadcast WebSocket event for real-time updates
    try:
        await broadcast_document_deleted(
            knowledge_base_id=kb_id,
            doc_id=doc_id,
            deleted_by=user.username
        )
    except Exception as ws_err:
        logger.warning(f"WebSocket broadcast failed (non-critical): {ws_err}")

    return {"message": f"Document {doc_id} deleted successfully"}

# =============================================================================
# Update Document Metadata Endpoint
# =============================================================================

@router.put("/{doc_id}/metadata")
async def update_document_metadata(
    doc_id: int,
    updates: dict,
    repo: KnowledgeBankRepository = Depends(get_repository),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update document metadata (cluster_id, primary_topic, etc).

    Args:
        doc_id: Document ID
        updates: Dictionary of fields to update
        repo: Repository instance (injected)
        user: Authenticated user
        db: Database session

    Returns:
        Updated metadata

    Raises:
        HTTPException 404: If document not found
    """
    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(user.username, db)

    # Get current metadata
    meta = await repo.get_document_metadata(doc_id)
    if not meta:
        raise HTTPException(404, f"Document {doc_id} not found")

    # Verify document belongs to user's KB
    if meta.knowledge_base_id != kb_id:
        raise HTTPException(404, f"Document {doc_id} not found")

    # Update allowed fields
    if 'skill_level' in updates:
        if updates['skill_level'] in SKILL_LEVELS:
            meta.skill_level = updates['skill_level']

    if 'cluster_id' in updates:
        new_cluster_id = updates['cluster_id']
        old_cluster_id = meta.cluster_id

        # Record feedback for cluster move (agentic learning)
        if old_cluster_id != new_cluster_id:
            try:
                await feedback_service.record_cluster_move(
                    username=user.username,
                    document_id=doc_id,
                    from_cluster_id=old_cluster_id,
                    to_cluster_id=new_cluster_id,
                    knowledge_base_id=kb_id
                )
                logger.info(f"Recorded cluster move feedback: doc {doc_id}, {old_cluster_id} → {new_cluster_id}")
            except Exception as e:
                logger.warning(f"Failed to record cluster move feedback: {e}")

        # Validate new cluster exists
        if new_cluster_id is not None:
            cluster = await repo.get_cluster(new_cluster_id)
            if not cluster:
                raise HTTPException(404, f"Cluster {new_cluster_id} not found")

        meta.cluster_id = new_cluster_id

    # Update metadata using repository
    success = await repo.update_document_metadata(doc_id, meta)
    if not success:
        raise HTTPException(500, "Failed to update metadata")

    logger.info(f"Updated metadata for document {doc_id} in KB {kb_id}")

    # Broadcast WebSocket event for real-time updates
    try:
        await broadcast_document_updated(
            knowledge_base_id=kb_id,
            doc_id=doc_id,
            updated_by=user.username,
            changes=updates
        )
    except Exception as ws_err:
        logger.warning(f"WebSocket broadcast failed (non-critical): {ws_err}")

    return {"message": "Metadata updated", "metadata": meta.dict()}


# =============================================================================
# Document Summaries Endpoints
# =============================================================================

@router.get("/{doc_id}/summaries")
async def get_document_summaries(
    doc_id: int,
    level: int = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get hierarchical summaries for a document.

    Args:
        doc_id: Document ID (doc_id, not internal ID)
        level: Optional filter by level (1=chunk, 2=section, 3=document)
        user: Authenticated user
        db: Database session

    Returns:
        List of summaries at requested levels
    """
    from ..db_models import DBDocument, DBDocumentSummary

    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(user.username, db)

    # Find the document
    doc = db.query(DBDocument).filter(
        DBDocument.doc_id == doc_id,
        DBDocument.knowledge_base_id == kb_id,
        DBDocument.owner_username == user.username
    ).first()

    if not doc:
        raise HTTPException(404, f"Document {doc_id} not found")

    # Get summaries
    query = db.query(DBDocumentSummary).filter(
        DBDocumentSummary.document_id == doc.id
    )

    if level:
        query = query.filter(DBDocumentSummary.summary_level == level)

    summaries = query.order_by(
        DBDocumentSummary.summary_level.desc(),
        DBDocumentSummary.id
    ).all()

    return {
        "doc_id": doc_id,
        "summary_count": len(summaries),
        "summaries": [
            {
                "id": s.id,
                "summary_type": s.summary_type,
                "summary_level": s.summary_level,
                "short_summary": s.short_summary,
                "long_summary": s.long_summary,
                "key_concepts": s.key_concepts,
                "tech_stack": s.tech_stack,
                "skill_profile": s.skill_profile,
                "chunk_id": s.chunk_id,
                "created_at": s.created_at.isoformat() if s.created_at else None
            }
            for s in summaries
        ]
    }


@router.post("/{doc_id}/summarize")
async def generate_document_summaries(
    doc_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate hierarchical summaries for a document.

    Requires document to have been chunked first.

    Args:
        doc_id: Document ID (doc_id, not internal ID)
        user: Authenticated user
        db: Database session

    Returns:
        Summary generation results
    """
    from ..db_models import DBDocument, DBDocumentChunk, DBDocumentSummary
    from ..summarization_service import generate_hierarchical_summaries

    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(user.username, db)

    # Find the document
    doc = db.query(DBDocument).filter(
        DBDocument.doc_id == doc_id,
        DBDocument.knowledge_base_id == kb_id,
        DBDocument.owner_username == user.username
    ).first()

    if not doc:
        raise HTTPException(404, f"Document {doc_id} not found")

    # Check if document has chunks
    chunks = db.query(DBDocumentChunk).filter(
        DBDocumentChunk.document_id == doc.id
    ).order_by(DBDocumentChunk.chunk_index).all()

    if not chunks:
        raise HTTPException(400, f"Document {doc_id} has no chunks. Run chunking first.")

    # Delete existing summaries
    db.query(DBDocumentSummary).filter(
        DBDocumentSummary.document_id == doc.id
    ).delete()
    db.commit()

    # Prepare chunk data
    chunk_data = [
        {
            'id': c.id,
            'content': c.content,
            'chunk_index': c.chunk_index
        }
        for c in chunks
    ]

    # Generate summaries
    try:
        result = await generate_hierarchical_summaries(
            db=db,
            document_id=doc.id,
            knowledge_base_id=kb_id,
            chunks=chunk_data
        )

        logger.info(f"Generated summaries for document {doc_id}: {result}")

        return {
            "doc_id": doc_id,
            "status": result.get("status", "unknown"),
            "chunk_summaries": result.get("chunk_summaries", 0),
            "section_summaries": result.get("section_summaries", 0),
            "document_summary": result.get("document_summary", 0)
        }

    except Exception as e:
        logger.error(f"Summary generation failed for doc {doc_id}: {e}")
        raise HTTPException(500, f"Summary generation failed: {str(e)}")
