"""
Admin Router for SyncBoard 3.0 Knowledge Bank.

Endpoints for administrative and maintenance operations:
- POST /admin/backfill-chunks - Process existing documents through chunking pipeline
- GET /admin/chunk-status - Get chunking status for user's documents
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends, BackgroundTasks
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ..models import User
from ..dependencies import (
    get_current_user,
    get_kb_documents,
    get_user_default_kb_id,
)
from ..database import get_db
from ..db_models import DBDocument, DBDocumentChunk, DBKnowledgeBase
from ..chunking_pipeline import chunk_document_on_upload

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses={401: {"description": "Unauthorized"}},
)


# =============================================================================
# Request/Response Models
# =============================================================================

class BackfillRequest(BaseModel):
    """Request to backfill chunks for existing documents."""
    max_documents: int = Field(10, ge=1, le=100, description="Maximum documents to process")
    generate_embeddings: bool = Field(True, description="Generate embeddings (requires OpenAI API)")


class BackfillResponse(BaseModel):
    """Response from backfill operation."""
    processed: int
    succeeded: int
    failed: int
    skipped: int
    results: list


class ChunkStatusResponse(BaseModel):
    """Status of chunking for user's documents."""
    total_documents: int
    chunked_documents: int
    pending_documents: int
    failed_documents: int
    total_chunks: int
    chunks_with_embeddings: int


# =============================================================================
# Chunk Status Endpoint
# =============================================================================

@router.get("/chunk-status", response_model=ChunkStatusResponse)
@limiter.limit("30/minute")
async def get_chunk_status(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get chunking status for user's documents.

    Returns counts of documents by chunking status and total chunks.
    """
    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Count documents by status
    total = db.query(DBDocument).filter(
        DBDocument.knowledge_base_id == kb_id,
        DBDocument.owner_username == current_user.username
    ).count()

    chunked = db.query(DBDocument).filter(
        DBDocument.knowledge_base_id == kb_id,
        DBDocument.owner_username == current_user.username,
        DBDocument.chunking_status == 'completed'
    ).count()

    pending = db.query(DBDocument).filter(
        DBDocument.knowledge_base_id == kb_id,
        DBDocument.owner_username == current_user.username,
        DBDocument.chunking_status == 'pending'
    ).count()

    failed = db.query(DBDocument).filter(
        DBDocument.knowledge_base_id == kb_id,
        DBDocument.owner_username == current_user.username,
        DBDocument.chunking_status == 'failed'
    ).count()

    # Count chunks
    total_chunks = db.query(DBDocumentChunk).filter(
        DBDocumentChunk.knowledge_base_id == kb_id
    ).count()

    chunks_with_embeddings = db.query(DBDocumentChunk).filter(
        DBDocumentChunk.knowledge_base_id == kb_id,
        DBDocumentChunk.embedding.isnot(None)
    ).count()

    return ChunkStatusResponse(
        total_documents=total,
        chunked_documents=chunked,
        pending_documents=pending,
        failed_documents=failed,
        total_chunks=total_chunks,
        chunks_with_embeddings=chunks_with_embeddings
    )


# =============================================================================
# Backfill Chunks Endpoint
# =============================================================================

@router.post("/backfill-chunks", response_model=BackfillResponse)
@limiter.limit("5/minute")
async def backfill_chunks(
    req: BackfillRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Process existing documents through chunking pipeline.

    This endpoint finds documents that haven't been chunked yet and
    processes them to enable chunk-based RAG.

    Rate limited to 5 requests per minute.

    Args:
        req: Backfill request with max_documents and generate_embeddings options

    Returns:
        BackfillResponse with processing results
    """
    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Get KB documents (for content lookup)
    kb_documents = get_kb_documents(kb_id)

    # Find documents needing chunking (pending or failed)
    pending_docs = db.query(DBDocument).filter(
        DBDocument.knowledge_base_id == kb_id,
        DBDocument.owner_username == current_user.username,
        DBDocument.chunking_status.in_(['pending', 'failed'])
    ).limit(req.max_documents).all()

    if not pending_docs:
        return BackfillResponse(
            processed=0,
            succeeded=0,
            failed=0,
            skipped=0,
            results=[{"message": "No documents need chunking"}]
        )

    results = []
    succeeded = 0
    failed = 0
    skipped = 0

    for doc in pending_docs:
        doc_id = doc.doc_id

        # Get content from in-memory storage
        content = kb_documents.get(doc_id)

        if not content:
            # Try to get from vector store via DB
            from ..db_models import DBVectorDocument
            vdoc = db.query(DBVectorDocument).filter_by(doc_id=doc_id).first()
            if vdoc:
                content = vdoc.content

        if not content:
            skipped += 1
            results.append({
                "doc_id": doc_id,
                "status": "skipped",
                "reason": "Content not found"
            })
            continue

        try:
            # Process document through chunking pipeline
            chunk_result = await chunk_document_on_upload(
                db=db,
                document=doc,
                content=content,
                generate_embeddings=req.generate_embeddings
            )

            succeeded += 1
            results.append({
                "doc_id": doc_id,
                "status": "success",
                "chunks": chunk_result.get("chunks", 0),
                "embeddings": chunk_result.get("embeddings", 0)
            })

            logger.info(f"Backfilled doc {doc_id}: {chunk_result.get('chunks', 0)} chunks")

        except Exception as e:
            failed += 1
            results.append({
                "doc_id": doc_id,
                "status": "failed",
                "error": str(e)
            })
            logger.error(f"Backfill failed for doc {doc_id}: {e}")

    logger.info(
        f"Backfill complete for user {current_user.username}: "
        f"{succeeded} succeeded, {failed} failed, {skipped} skipped"
    )

    return BackfillResponse(
        processed=len(pending_docs),
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        results=results
    )


# =============================================================================
# Reprocess Single Document
# =============================================================================

@router.post("/reprocess-document/{doc_id}")
@limiter.limit("10/minute")
async def reprocess_document(
    doc_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reprocess a single document through chunking pipeline.

    Useful for re-generating chunks/embeddings after content updates.
    """
    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Find document and verify ownership
    doc = db.query(DBDocument).filter(
        DBDocument.doc_id == doc_id,
        DBDocument.knowledge_base_id == kb_id,
        DBDocument.owner_username == current_user.username
    ).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get content
    kb_documents = get_kb_documents(kb_id)
    content = kb_documents.get(doc_id)

    if not content:
        from ..db_models import DBVectorDocument
        vdoc = db.query(DBVectorDocument).filter_by(doc_id=doc_id).first()
        if vdoc:
            content = vdoc.content

    if not content:
        raise HTTPException(status_code=404, detail="Document content not found")

    try:
        # Delete existing chunks
        db.query(DBDocumentChunk).filter(
            DBDocumentChunk.document_id == doc.id
        ).delete()
        db.commit()

        # Reprocess
        chunk_result = await chunk_document_on_upload(
            db=db,
            document=doc,
            content=content,
            generate_embeddings=True
        )

        return {
            "doc_id": doc_id,
            "status": "success",
            "chunks": chunk_result.get("chunks", 0),
            "embeddings": chunk_result.get("embeddings", 0)
        }

    except Exception as e:
        logger.error(f"Reprocess failed for doc {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Reprocessing failed: {str(e)}")
