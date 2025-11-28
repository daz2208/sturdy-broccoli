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
from sqlalchemy import func, case
from pydantic import BaseModel, Field

from ..models import User
from ..dependencies import (
    get_current_user,
    get_repository,
    get_kb_documents,
    get_user_default_kb_id,
)
from ..repository_interface import KnowledgeBankRepository
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

    # Single query for all document status counts using conditional aggregation
    # Reduces 4 separate queries to 1 (75% reduction in DB load)
    doc_stats = db.query(
        func.count(DBDocument.id).label('total'),
        func.sum(case((DBDocument.chunking_status == 'completed', 1), else_=0)).label('chunked'),
        func.sum(case((DBDocument.chunking_status == 'pending', 1), else_=0)).label('pending'),
        func.sum(case((DBDocument.chunking_status == 'failed', 1), else_=0)).label('failed')
    ).filter(
        DBDocument.knowledge_base_id == kb_id,
        DBDocument.owner_username == current_user.username
    ).first()

    # Single query for chunk counts using conditional aggregation
    # Reduces 2 separate queries to 1
    chunk_stats = db.query(
        func.count(DBDocumentChunk.id).label('total_chunks'),
        func.sum(case((DBDocumentChunk.embedding.isnot(None), 1), else_=0)).label('with_embeddings')
    ).filter(
        DBDocumentChunk.knowledge_base_id == kb_id
    ).first()

    return ChunkStatusResponse(
        total_documents=doc_stats.total or 0,
        chunked_documents=int(doc_stats.chunked or 0),
        pending_documents=int(doc_stats.pending or 0),
        failed_documents=int(doc_stats.failed or 0),
        total_chunks=chunk_stats.total_chunks or 0,
        chunks_with_embeddings=int(chunk_stats.with_embeddings or 0)
    )


# =============================================================================
# Backfill Chunks Endpoint
# =============================================================================

@router.post("/backfill-chunks", response_model=BackfillResponse)
@limiter.limit("5/minute")
async def backfill_chunks(
    req: BackfillRequest,
    request: Request,
    repo: KnowledgeBankRepository = Depends(get_repository),
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
        repo: Repository instance
        current_user: Authenticated user
        db: Database session

    Returns:
        BackfillResponse with processing results
    """
    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Get KB documents from repository (for content lookup)
    kb_documents = await repo.get_documents_by_kb(kb_id)

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
    repo: KnowledgeBankRepository = Depends(get_repository),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reprocess a single document through chunking pipeline.

    Useful for re-generating chunks/embeddings after content updates.

    Args:
        doc_id: Document ID to reprocess
        request: FastAPI request
        repo: Repository instance
        current_user: Authenticated user
        db: Database session
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

    # Get content from repository
    kb_documents = await repo.get_documents_by_kb(kb_id)
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


# =============================================================================
# LLM Provider Management
# =============================================================================

class LLMProviderStatus(BaseModel):
    """Status of current LLM provider configuration."""
    provider: str
    status: str
    details: dict


@router.get("/llm-provider", response_model=LLMProviderStatus)
async def get_llm_provider_status(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Get current LLM provider configuration and status.

    Returns the configured provider (openai/ollama/mock) and connection status.
    """
    import os
    import httpx

    provider = os.environ.get("LLM_PROVIDER", "openai").lower()

    details = {
        "provider_type": provider,
        "available_providers": ["openai", "ollama", "mock"]
    }

    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
        details["configured"] = bool(api_key and api_key != "sk-replace-with-your-actual-openai-key")
        details["model_concept"] = os.environ.get("OPENAI_CONCEPT_MODEL", "gpt-5-nano")
        details["model_suggestion"] = os.environ.get("OPENAI_SUGGESTION_MODEL", "gpt-5-mini")
        status = "configured" if details["configured"] else "not_configured"

    elif provider == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        concept_model = os.environ.get("OLLAMA_CONCEPT_MODEL", "llama2")
        suggestion_model = os.environ.get("OLLAMA_SUGGESTION_MODEL", "llama2")

        details["base_url"] = base_url
        details["model_concept"] = concept_model
        details["model_suggestion"] = suggestion_model

        # Check connection to Ollama
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{base_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m.get("name", "").split(":")[0] for m in models]
                    details["available_models"] = model_names
                    details["connected"] = True

                    # Check if configured models are available
                    concept_available = any(concept_model in m for m in model_names)
                    suggestion_available = any(suggestion_model in m for m in model_names)

                    if concept_available and suggestion_available:
                        status = "ready"
                    else:
                        status = "models_missing"
                        details["missing_models"] = []
                        if not concept_available:
                            details["missing_models"].append(concept_model)
                        if not suggestion_available:
                            details["missing_models"].append(suggestion_model)
                else:
                    status = "connection_error"
                    details["connected"] = False
        except Exception as e:
            status = "connection_error"
            details["connected"] = False
            details["error"] = str(e)

    elif provider == "mock":
        status = "ready"
        details["note"] = "Mock provider for testing - no external API calls"

    else:
        status = "unknown_provider"

    return LLMProviderStatus(
        provider=provider,
        status=status,
        details=details
    )


@router.post("/llm-provider/test")
@limiter.limit("5/minute")
async def test_llm_provider(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Test the current LLM provider with a simple completion.

    Sends a test prompt and returns the result to verify the provider is working.
    """
    from ..llm_providers import get_llm_provider

    try:
        provider = get_llm_provider()

        # Simple test prompt
        test_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Reply with exactly: 'LLM provider test successful'"}
        ]

        response = await provider.chat_completion(test_messages, temperature=0)

        return {
            "status": "success",
            "provider": type(provider).__name__,
            "response": response[:200]  # Truncate long responses
        }

    except Exception as e:
        logger.error(f"LLM provider test failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"LLM provider test failed: {str(e)}"
        )
