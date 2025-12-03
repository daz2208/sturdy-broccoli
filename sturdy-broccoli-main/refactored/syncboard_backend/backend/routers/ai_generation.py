"""
AI Generation Router for SyncBoard 3.0 Knowledge Bank.

Endpoints:
- POST /generate - Generate AI content with RAG (Retrieval-Augmented Generation)
- POST /generate/enhanced - Generate with Enhanced RAG (hybrid search, reranking, query expansion)

Supports three modes:
1. Enhanced RAG (new) - Hybrid search + cross-encoder reranking + query expansion
2. Chunk-based RAG - Uses document chunks with embeddings for precise retrieval
3. Document-based RAG (fallback) - Uses full documents with TF-IDF search
"""

import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from ..models import User, GenerationRequest, GenerationResponse, CitationInfo
from ..dependencies import (
    get_current_user,
    get_repository,
    get_kb_documents,
    get_kb_metadata,
    get_kb_doc_ids,
    get_user_default_kb_id,
    get_vector_store,
)
from ..repository_interface import KnowledgeBankRepository
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

# Try to import enhanced RAG service
try:
    from ..enhanced_rag import EnhancedRAGService, RAGConfig
    ENHANCED_RAG_AVAILABLE = True
    logger.info("[SUCCESS] Enhanced RAG service loaded (hybrid search, reranking, query expansion)")
except ImportError as e:
    ENHANCED_RAG_AVAILABLE = False
    logger.warning(f"[WARNING] Enhanced RAG not available: {e}")

# =============================================================================
# AI Generation Endpoint
# =============================================================================

@router.post("/generate", response_model=GenerationResponse)
@limiter.limit("5/minute")
async def generate_content(
    req: GenerationRequest,
    request: Request,
    repo: KnowledgeBankRepository = Depends(get_repository),
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
        repo: Repository instance
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

    # Get KB-scoped storage from repository (properly isolated)
    kb_documents = await repo.get_documents_by_kb(kb_id)
    kb_metadata = await repo.get_metadata_by_kb(kb_id)

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


# =============================================================================
# Enhanced RAG Endpoint (NEW)
# =============================================================================

@router.post("/generate/enhanced")
@limiter.limit("5/minute")
async def generate_enhanced(
    req: GenerationRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate AI content with Enhanced RAG system.

    This endpoint uses the production-grade RAG pipeline with:
    - Hybrid Search: Combines TF-IDF lexical + embedding semantic search
    - Cross-Encoder Reranking: Uses sentence-transformers for precise reranking
    - Query Expansion: LLM-powered query enhancement for better retrieval
    - Parent-Child Chunking: Small chunks for retrieval, larger for context

    Rate limited to 5 requests per minute.

    Args:
        req: Generation request with prompt and model
        request: FastAPI request (for rate limiting)
        current_user: Authenticated user
        db: Database session

    Returns:
        Enhanced response with detailed metrics and citations
    """
    if not ENHANCED_RAG_AVAILABLE:
        return {
            "error": "Enhanced RAG not available",
            "fallback": "Use /generate endpoint instead",
            "reason": "Required dependencies not installed (sentence-transformers, pgvector)"
        }

    # Get user's knowledge base
    kb_id = get_user_default_kb_id(current_user.username, db)

    logger.info(f"Enhanced RAG request from {current_user.username} in KB {kb_id}")

    try:
        # Configure enhanced RAG
        config = RAGConfig(
            enable_query_expansion=True,
            enable_reranking=True,
            initial_retrieval_k=50,
            rerank_top_k=10,
            generation_model=req.model or "gpt-5-mini"
        )

        # Create service and generate
        rag_service = EnhancedRAGService(db, config)
        response = await rag_service.generate(
            query=req.prompt,
            user_id=current_user.username,
            kb_id=kb_id,
            model=req.model
        )

        # Build enhanced response
        return {
            "response": response.answer,
            "model": response.model_used,
            "query_expanded": response.query_expanded,
            "chunks_used": len(response.chunks_used),
            "documents_used": len(set(c.document_id for c in response.chunks_used)),
            "citations": [
                {
                    "doc_id": c.document_id,
                    "chunk_id": c.chunk_id,
                    "filename": c.filename,
                    "source_url": c.source_url,
                    "source_type": c.source_type,
                    "relevance": round(c.final_score, 3),
                    "snippet": c.content[:200] + "..." if len(c.content) > 200 else c.content
                }
                for c in response.chunks_used[:10]  # Top 10 citations
            ],
            "timing": {
                "retrieval_ms": round(response.retrieval_time_ms, 2),
                "rerank_ms": round(response.rerank_time_ms, 2),
                "generation_ms": round(response.generation_time_ms, 2),
                "total_ms": round(response.total_time_ms, 2)
            },
            "enhanced_rag": True
        }

    except Exception as e:
        logger.error(f"Enhanced RAG failed: {e}")
        return {
            "error": str(e),
            "fallback": "Use /generate endpoint for basic RAG",
            "enhanced_rag": False
        }


@router.get("/generate/status")
async def get_rag_status():
    """
    Check the status of RAG capabilities.

    Returns information about which RAG features are available.
    """
    return {
        "basic_rag_available": REAL_AI_AVAILABLE,
        "embeddings_available": EMBEDDINGS_AVAILABLE,
        "enhanced_rag_available": ENHANCED_RAG_AVAILABLE,
        "features": {
            "hybrid_search": ENHANCED_RAG_AVAILABLE,
            "cross_encoder_reranking": ENHANCED_RAG_AVAILABLE,
            "query_expansion": ENHANCED_RAG_AVAILABLE,
            "parent_child_chunking": ENHANCED_RAG_AVAILABLE,
            "pgvector_native": ENHANCED_RAG_AVAILABLE,
        },
        "recommended_endpoint": "/generate/enhanced" if ENHANCED_RAG_AVAILABLE else "/generate"
    }
