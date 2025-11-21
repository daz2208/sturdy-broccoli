"""
AI Generation Router for SyncBoard 3.0 Knowledge Bank.

Endpoints:
- POST /generate - Generate AI content with RAG (Retrieval-Augmented Generation)
"""

import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from ..models import User, GenerationRequest
from ..dependencies import (
    get_current_user,
    get_kb_documents,
    get_kb_metadata,
    get_kb_doc_ids,
    get_user_default_kb_id,
    get_vector_store,
)
from ..database import get_db

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
    from ..ai_generation_real import generate_with_rag, MODELS
    REAL_AI_AVAILABLE = True
    logger.info("[SUCCESS] Real AI integration loaded")
except ImportError as e:
    REAL_AI_AVAILABLE = False
    logger.warning(f"[WARNING] Real AI not available: {e}")

# =============================================================================
# AI Generation Endpoint
# =============================================================================

@router.post("/generate")
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

    Uses the user's knowledge bank to provide context for generation,
    implementing RAG pattern for better, context-aware responses.

    Args:
        req: Generation request with prompt and model selection
        request: FastAPI request (for rate limiting)
        current_user: Authenticated user
        db: Database session

    Returns:
        AI-generated response based on user's knowledge
    """
    if not REAL_AI_AVAILABLE:
        return {"response": "AI generation not available - API keys not configured"}

    # Get user's default knowledge base (KB-scoped, no data leakage)
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Get KB-scoped storage (properly isolated)
    kb_documents = get_kb_documents(kb_id)
    kb_metadata = get_kb_metadata(kb_id)
    vector_store = get_vector_store()

    # Filter to user's documents within their KB
    user_doc_ids = []
    user_documents = {}
    for doc_id, meta in kb_metadata.items():
        if meta.owner == current_user.username:
            user_doc_ids.append(doc_id)
            if doc_id in kb_documents:
                user_documents[doc_id] = kb_documents[doc_id]

    logger.info(f"RAG context: {len(user_documents)} documents for user {current_user.username} in KB {kb_id}")

    # Also get metadata for those documents (for citations)
    user_metadata = {
        did: meta for did, meta in kb_metadata.items()
        if did in user_doc_ids
    }

    try:
        response_text = await generate_with_rag(
            prompt=req.prompt,
            model=req.model,
            vector_store=vector_store,
            allowed_doc_ids=user_doc_ids,
            documents=user_documents,
            metadata=user_metadata
        )
        return {"response": response_text}
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        return {"response": f"Error: {str(e)}"}
