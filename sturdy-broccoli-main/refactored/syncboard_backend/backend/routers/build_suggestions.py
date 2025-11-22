"""
Build Suggestions Router for SyncBoard 3.0 Knowledge Bank.

Endpoints:
- POST /what_can_i_build - Analyze knowledge bank and suggest viable projects
- GET /idea-seeds - Get pre-computed build ideas from knowledge bank
- POST /idea-seeds/generate - Generate idea seeds for a document
- GET /idea-seeds/combined - Get ideas combining multiple documents
"""

import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from ..models import User, BuildSuggestionRequest
from ..dependencies import (
    get_current_user,
    get_kb_documents,
    get_kb_metadata,
    get_kb_clusters,
    get_user_default_kb_id,
    get_build_suggester,
)
from ..database import get_db
from ..sanitization import validate_positive_integer
from ..constants import MAX_SUGGESTIONS

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(
    prefix="",
    tags=["build-suggestions"],
    responses={401: {"description": "Unauthorized"}},
)

# =============================================================================
# Build Suggestion Endpoint
# =============================================================================

@router.post("/what_can_i_build")
@limiter.limit("3/minute")
async def what_can_i_build(
    req: BuildSuggestionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze knowledge bank and suggest viable projects.

    Rate limited to 3 requests per minute (expensive operation).

    Args:
        req: Build suggestion request with max_suggestions parameter
        request: FastAPI request (for rate limiting)
        current_user: Authenticated user
        db: Database session

    Returns:
        Project suggestions based on user's knowledge bank
    """
    # Get user's default knowledge base ID
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Get KB-scoped storage (properly isolated by KB)
    kb_documents = get_kb_documents(kb_id)
    kb_metadata = get_kb_metadata(kb_id)
    kb_clusters = get_kb_clusters(kb_id)
    build_suggester = get_build_suggester()

    # Validate max_suggestions parameter
    max_suggestions = validate_positive_integer(req.max_suggestions, "max_suggestions", max_value=MAX_SUGGESTIONS)
    if max_suggestions < 1:
        max_suggestions = 5

    # Filter to user's content within their KB
    user_clusters = {
        cid: cluster for cid, cluster in kb_clusters.items()
        if any(kb_metadata.get(did) and kb_metadata[did].owner == current_user.username for did in cluster.doc_ids)
    }

    user_metadata = {
        did: meta for did, meta in kb_metadata.items()
        if meta.owner == current_user.username
    }

    user_documents = {
        did: doc for did, doc in kb_documents.items()
        if did in user_metadata
    }
    
    if not user_clusters:
        return {
            "suggestions": [],
            "knowledge_summary": {
                "total_docs": 0,
                "total_clusters": 0,
                "clusters": []
            }
        }
    
    # Generate suggestions
    suggestions = await build_suggester.analyze_knowledge_bank(
        clusters=user_clusters,
        metadata=user_metadata,
        documents=user_documents,
        max_suggestions=max_suggestions,
        enable_quality_filter=req.enable_quality_filter
    )
    
    return {
        "suggestions": [s.dict() for s in suggestions],
        "knowledge_summary": {
            "total_docs": len(user_documents),
            "total_clusters": len(user_clusters),
            "clusters": [c.dict() for c in user_clusters.values()]
        }
    }


# =============================================================================
# Idea Seeds Endpoints (Pre-computed build ideas)
# =============================================================================

@router.get("/idea-seeds")
@limiter.limit("30/minute")
async def get_idea_seeds(
    request: Request,
    difficulty: str = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get pre-computed build ideas from the knowledge bank.

    These are ideas generated from document summaries, stored for quick retrieval.

    Args:
        difficulty: Optional filter by difficulty (beginner, intermediate, advanced)
        limit: Maximum results (default 20)
        current_user: Authenticated user
        db: Database session

    Returns:
        List of pre-computed idea seeds
    """
    from ..idea_seeds_service import get_user_idea_seeds

    # Validate difficulty
    if difficulty and difficulty not in ["beginner", "intermediate", "advanced"]:
        raise HTTPException(400, "Invalid difficulty. Use: beginner, intermediate, advanced")

    # Validate limit
    limit = min(max(1, limit), 50)

    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Get stored idea seeds
    ideas = await get_user_idea_seeds(
        db=db,
        knowledge_base_id=kb_id,
        difficulty=difficulty,
        limit=limit
    )

    return {
        "count": len(ideas),
        "ideas": ideas
    }


@router.post("/idea-seeds/generate/{doc_id}")
@limiter.limit("5/minute")
async def generate_idea_seeds(
    doc_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate idea seeds for a specific document.

    Requires the document to have summaries generated first.

    Args:
        doc_id: Document ID (doc_id, not internal ID)
        current_user: Authenticated user
        db: Database session

    Returns:
        Generation results with idea count
    """
    from ..db_models import DBDocument, DBDocumentSummary
    from ..idea_seeds_service import generate_document_idea_seeds

    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Find the document
    doc = db.query(DBDocument).filter(
        DBDocument.doc_id == doc_id,
        DBDocument.knowledge_base_id == kb_id,
        DBDocument.owner_username == current_user.username
    ).first()

    if not doc:
        raise HTTPException(404, f"Document {doc_id} not found")

    # Check if document has summaries
    summary = db.query(DBDocumentSummary).filter(
        DBDocumentSummary.document_id == doc.id,
        DBDocumentSummary.summary_level == 3
    ).first()

    if not summary:
        raise HTTPException(
            400,
            f"Document {doc_id} has no summaries. Run /documents/{doc_id}/summarize first."
        )

    # Generate idea seeds
    result = await generate_document_idea_seeds(
        db=db,
        document_id=doc.id,
        knowledge_base_id=kb_id
    )

    logger.info(f"Generated idea seeds for document {doc_id}: {result}")

    return {
        "doc_id": doc_id,
        "status": result.get("status"),
        "ideas_generated": result.get("ideas_generated", 0),
        "ideas": result.get("ideas", [])
    }


@router.get("/idea-seeds/combined")
@limiter.limit("5/minute")
async def get_combined_ideas(
    request: Request,
    max_ideas: int = 5,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get ideas that combine knowledge from multiple documents.

    Generates on-the-fly based on document summaries.

    Args:
        max_ideas: Maximum combined ideas to generate (default 5)
        current_user: Authenticated user
        db: Database session

    Returns:
        List of combined ideas synthesizing multiple documents
    """
    from ..idea_seeds_service import generate_kb_combined_ideas

    # Validate max_ideas
    max_ideas = min(max(1, max_ideas), 10)

    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Generate combined ideas
    ideas = await generate_kb_combined_ideas(
        db=db,
        knowledge_base_id=kb_id,
        max_ideas=max_ideas
    )

    return {
        "count": len(ideas),
        "type": "combined",
        "ideas": ideas
    }
