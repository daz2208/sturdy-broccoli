"""
AI Generation Router for SyncBoard 3.0 Knowledge Bank.

Endpoints:
- POST /generate - Generate AI content with RAG (Retrieval-Augmented Generation)

Supports two modes:
1. Chunk-based RAG (default) - Uses document chunks with embeddings for precise retrieval
2. Document-based RAG (fallback) - Uses full documents with TF-IDF search
"""

import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from ..models import User, GenerationRequest, GenerationResponse, CitationInfo
from ..dependencies import (
    get_current_user,
    get_kb_documents,
    get_kb_metadata,
    get_kb_doc_ids,
    get_user_default_kb_id,
    get_vector_store,
)
from ..database import get_db
from ..db_models import DBDocumentChunk

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(
    prefix="",
    tags=["ai-generation"],
    responses={401: {"description": "Unauthorized"}},
)

# Try to import AI generation
try:
    from ..ai_generation_real import generate_with_rag, generate_with_chunks, Citation, MODELS
    REAL_AI_AVAILABLE = True
    logger.info("[SUCCESS] Real AI integration loaded (with chunk support)")
except ImportError as e:
    REAL_AI_AVAILABLE = False
    logger.warning(f"[WARNING] Real AI not available: {e}")

# Try to import embedding service for chunk search
try:
    from ..embedding_service import get_embedding_service
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("[WARNING] Embedding service not available")

# =============================================================================
# AI Generation Endpoint
# =============================================================================

@router.post("/generate", response_model=GenerationResponse)
@limiter.limit("5/minute")
async def generate_content(
    req: GenerationRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate AI content with RAG (Retrieval-Augmented Generation).

    Rate limited to 5 requests per minute.

    Uses the user's knowledge bank to provide context for generation.
    Supports two modes:
    - Chunk-based RAG (default): Uses document chunks with embeddings
    - Document-based RAG (fallback): Uses full documents with TF-IDF

    Args:
        req: Generation request with prompt, model, and use_chunks flag
        request: FastAPI request (for rate limiting)
        current_user: Authenticated user
        db: Database session

    Returns:
        GenerationResponse with response text and structured citations
    """
    if not REAL_AI_AVAILABLE:
        return GenerationResponse(
            response="AI generation not available - API keys not configured"
        )

    # Get user's default knowledge base (KB-scoped, no data leakage)
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Get KB-scoped storage (properly isolated)
    kb_documents = get_kb_documents(kb_id)
    kb_metadata = get_kb_metadata(kb_id)

    # Filter to user's documents within their KB
    user_doc_ids = []
    user_documents = {}
    for doc_id, meta in kb_metadata.items():
        if meta.owner == current_user.username:
            user_doc_ids.append(doc_id)
            if doc_id in kb_documents:
                user_documents[doc_id] = kb_documents[doc_id]

    # Get metadata for citations
    user_metadata = {
        did: meta for did, meta in kb_metadata.items()
        if did in user_doc_ids
    }

    logger.info(f"RAG context: {len(user_documents)} documents for user {current_user.username} in KB {kb_id}")

    # Try chunk-based RAG if enabled and chunks exist
    use_chunks = req.use_chunks and EMBEDDINGS_AVAILABLE

    if use_chunks:
        # Check if user has any chunks
        chunk_count = db.query(DBDocumentChunk).filter(
            DBDocumentChunk.knowledge_base_id == kb_id,
            DBDocumentChunk.embedding.isnot(None)
        ).count()

        if chunk_count > 0:
            try:
                return await _generate_with_chunk_rag(
                    db, req, kb_id, user_doc_ids, user_metadata
                )
            except Exception as e:
                logger.warning(f"Chunk-based RAG failed, falling back to document RAG: {e}")

    # Fallback to document-based RAG
    return await _generate_with_document_rag(
        req, user_doc_ids, user_documents, user_metadata
    )


async def _generate_with_chunk_rag(
    db: Session,
    req: GenerationRequest,
    kb_id: str,
    user_doc_ids: list,
    user_metadata: dict
) -> GenerationResponse:
    """Generate using chunk-based RAG with embeddings."""
    embedding_service = get_embedding_service()

    # Generate embedding for the query
    query_embedding = await embedding_service.embed_text(req.prompt)

    if not query_embedding:
        raise Exception("Failed to generate query embedding")

    # Search for similar chunks
    from ..chunking_pipeline import search_chunks_by_embedding
    chunks = await search_chunks_by_embedding(
        db=db,
        query_embedding=query_embedding,
        kb_id=kb_id,
        top_k=30,
        min_similarity=0.3
    )

    # Filter to user's documents
    user_chunks = [c for c in chunks if c['document_id'] in user_doc_ids]

    logger.info(f"Chunk-based RAG: found {len(user_chunks)} relevant chunks")

    # Generate response
    response_text, citations = await generate_with_chunks(
        prompt=req.prompt,
        model=req.model,
        chunks=user_chunks,
        metadata=user_metadata
    )

    # Convert citations to response model
    citation_infos = [
        CitationInfo(
            doc_id=c.doc_id,
            chunk_id=c.chunk_id,
            filename=c.filename,
            source_url=c.source_url,
            source_type=c.source_type,
            relevance=c.relevance,
            snippet=c.snippet
        )
        for c in citations
    ]

    return GenerationResponse(
        response=response_text,
        citations=citation_infos,
        chunks_used=len(user_chunks),
        documents_used=len(set(c['document_id'] for c in user_chunks)),
        model=req.model
    )


async def _generate_with_document_rag(
    req: GenerationRequest,
    user_doc_ids: list,
    user_documents: dict,
    user_metadata: dict
) -> GenerationResponse:
    """Generate using document-based RAG with TF-IDF."""
    vector_store = get_vector_store()

    try:
        response_text = await generate_with_rag(
            prompt=req.prompt,
            model=req.model,
            vector_store=vector_store,
            allowed_doc_ids=user_doc_ids,
            documents=user_documents,
            metadata=user_metadata
        )

        return GenerationResponse(
            response=response_text,
            documents_used=len(user_documents),
            model=req.model
        )
    except Exception as e:
        logger.error(f"Document-based RAG failed: {e}")
        return GenerationResponse(
            response=f"Error: {str(e)}"
        )
