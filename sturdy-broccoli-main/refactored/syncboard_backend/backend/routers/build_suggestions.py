"""
Build Suggestions Router for SyncBoard 3.0 Knowledge Bank.

Endpoints:
- POST /what_can_i_build - Analyze knowledge bank and suggest viable projects
- POST /what_can_i_build/goal-driven - Goal-driven suggestions (Phase 10)
- GET /idea-seeds - Get pre-computed build ideas from knowledge bank
- POST /idea-seeds/generate - Generate idea seeds for a document
- GET /idea-seeds/combined - Get ideas combining multiple documents
"""

import logging
import os
from fastapi import APIRouter, HTTPException, Request, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from ..models import (
    User, BuildSuggestionRequest,
    GoalDrivenSuggestionsRequest, GoalDrivenSuggestionsResponse,
    MarketValidationRequest, MarketValidationResponse
)
from ..dependencies import (
    get_current_user,
    get_kb_documents,
    get_kb_metadata,
    get_kb_clusters,
    get_user_default_kb_id,
    get_build_suggester,
)
from ..database import get_db, get_db_context
from ..sanitization import validate_positive_integer
from ..constants import MAX_SUGGESTIONS
from ..db_models import DBProjectGoal, DBProjectAttempt, DBMarketValidation, DBSavedIdea, DBBuildIdeaSeed
from ..redis_client import get_cached_build_suggestions, cache_build_suggestions

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
            },
            "empty_reason": "No clusters found in your knowledge base",
            "empty_actions": [
                "Upload documents to create your first clusters",
                "Add content via URL, file upload, or direct text input",
                "Import from connected integrations (GitHub, Google Drive, etc.)"
            ]
        }

    # Check cache first (100x faster for cached results)
    cached_suggestions = get_cached_build_suggestions(user_id=current_user.username)

    if cached_suggestions:
        logger.info(f"Cache HIT: Build suggestions for {current_user.username}")
        return cached_suggestions

    # Tier 2 Enhancement: Pull pre-computed idea seeds first
    from ..idea_seeds_service import get_user_idea_seeds

    idea_seeds = await get_user_idea_seeds(
        db=db,
        knowledge_base_id=kb_id,
        difficulty=None,  # Get all difficulties
        limit=50  # Get more seeds for better context
    )

    logger.info(f"Found {len(idea_seeds)} pre-computed idea seeds for enhanced suggestions")

    # Cache miss - generate suggestions (enhanced with idea seeds)
    logger.info(f"Cache MISS: Generating ENHANCED build suggestions for {current_user.username}")
    suggestions = await build_suggester.analyze_knowledge_bank(
        clusters=user_clusters,
        metadata=user_metadata,
        documents=user_documents,
        max_suggestions=max_suggestions,
        enable_quality_filter=req.enable_quality_filter,
        idea_seeds=idea_seeds  # Pass idea seeds for enhancement
    )

    result = {
        "suggestions": [s.dict() for s in suggestions],
        "knowledge_summary": {
            "total_docs": len(user_documents),
            "total_clusters": len(user_clusters),
            "clusters": [c.dict() for c in user_clusters.values()]
        }
    }

    # Cache the result for 30 minutes (1800 seconds)
    cache_build_suggestions(
        user_id=current_user.username,
        suggestions=result,
        ttl=1800
    )

    return result


# =============================================================================
# Goal-Driven Build Suggestions (Phase 10)
# =============================================================================

@router.post("/what_can_i_build/goal-driven")
@limiter.limit("3/minute")
async def what_can_i_build_goal_driven(
    req: GoalDrivenSuggestionsRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate goal-driven build suggestions based on user's goals and past projects.

    This enhanced version considers:
    - User's primary goal (revenue, learning, portfolio, automation)
    - Constraints (time, budget, tech stack preferences)
    - Past project attempts and learnings

    Rate limited to 3 requests per minute (expensive operation).

    Args:
        req: Request with max_suggestions and quality filter options
        request: FastAPI request (for rate limiting)
        current_user: Authenticated user
        db: Database session

    Returns:
        Comprehensive project suggestions with code, learning paths, and market validation
    """
    from ..llm_providers import OpenAIProvider

    # Get user's default knowledge base ID
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Get KB-scoped storage
    kb_documents = get_kb_documents(kb_id)
    kb_metadata = get_kb_metadata(kb_id)
    kb_clusters = get_kb_clusters(kb_id)
    build_suggester = get_build_suggester()

    # Get user's primary goal and constraints
    primary_goal = db.query(DBProjectGoal).filter(
        DBProjectGoal.user_id == current_user.username
    ).order_by(DBProjectGoal.priority.desc()).first()

    if not primary_goal:
        # Default goal if none set
        user_goals = {
            'primary_goal': 'revenue',
            'constraints': {
                'time_available': 'weekends',
                'budget': 0,
                'target_market': 'B2B SaaS',
                'tech_stack_preference': 'Python/FastAPI',
                'deployment_preference': 'Docker'
            }
        }
    else:
        user_goals = {
            'primary_goal': primary_goal.goal_type,
            'constraints': primary_goal.constraints or {}
        }

    # Get past project attempts for learning
    past_attempts_db = db.query(DBProjectAttempt).filter(
        DBProjectAttempt.user_id == current_user.username
    ).order_by(DBProjectAttempt.created_at.desc()).limit(10).all()

    past_attempts = []
    for attempt in past_attempts_db:
        past_attempts.append({
            'title': attempt.title,
            'status': attempt.status,
            'time_spent_hours': attempt.time_spent_hours,
            'learnings': attempt.learnings,
            'difficulty_rating': attempt.difficulty_rating
        })

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

    if not user_documents:
        return GoalDrivenSuggestionsResponse(
            suggestions=[],
            user_goal=user_goals['primary_goal'],
            total_documents=0,
            total_clusters=0
        )

    # Build knowledge summary
    knowledge_summary = build_suggester._build_knowledge_summary(
        user_clusters, user_metadata, user_documents
    )

    # Build knowledge areas
    knowledge_areas = []
    for cid, cluster in user_clusters.items():
        knowledge_areas.append({
            'name': cluster.name,
            'document_count': len(cluster.doc_ids),
            'core_concepts': cluster.primary_concepts,
            'skill_level': cluster.skill_level
        })

    # Build validation info
    validation_info = {
        'stats': {
            'total_documents': len(user_documents),
            'unique_concepts': len(set(
                c.name for meta in user_metadata.values()
                for c in meta.concepts
            )),
            'total_clusters': len(user_clusters),
            'skill_distribution': {}
        }
    }

    # Calculate skill distribution
    skill_counts = {}
    for meta in user_metadata.values():
        level = meta.skill_level or 'unknown'
        skill_counts[level] = skill_counts.get(level, 0) + 1
    validation_info['stats']['skill_distribution'] = skill_counts

    # Initialize LLM provider
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")

    provider = OpenAIProvider(
        api_key=api_key,
        suggestion_model="gpt-4o"
    )

    # Generate goal-driven suggestions
    suggestions = await provider.generate_goal_driven_suggestions(
        knowledge_summary=knowledge_summary,
        knowledge_areas=knowledge_areas,
        validation_info=validation_info,
        user_goals=user_goals,
        past_attempts=past_attempts,
        max_suggestions=req.max_suggestions
    )

    logger.info(f"Generated {len(suggestions)} goal-driven suggestions for {current_user.username}")

    return GoalDrivenSuggestionsResponse(
        suggestions=suggestions,
        user_goal=user_goals['primary_goal'],
        total_documents=len(user_documents),
        total_clusters=len(user_clusters)
    )


@router.post("/validate-market")
@limiter.limit("5/minute")
async def validate_market(
    req: MarketValidationRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Validate market viability for a project idea.

    Uses AI to analyze competition, market size, and unique advantages.

    Args:
        req: Market validation request with project details
        current_user: Authenticated user
        db: Database session

    Returns:
        Comprehensive market validation analysis
    """
    from ..market_validator import MarketValidator
    from ..llm_providers import OpenAIProvider

    # Get user's knowledge for context
    kb_id = get_user_default_kb_id(current_user.username, db)
    kb_documents = get_kb_documents(kb_id)
    kb_metadata = get_kb_metadata(kb_id)

    # Build knowledge summary
    user_metadata = {
        did: meta for did, meta in kb_metadata.items()
        if meta.owner == current_user.username
    }
    user_documents = {
        did: doc for did, doc in kb_documents.items()
        if did in user_metadata
    }

    knowledge_summary = ""
    for did, content in list(user_documents.items())[:5]:
        meta = user_metadata.get(did)
        if meta:
            knowledge_summary += f"\n{meta.filename or 'Document'}: {content[:500]}...\n"

    # Initialize services
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")

    provider = OpenAIProvider(api_key=api_key, suggestion_model="gpt-4o")
    validator = MarketValidator(provider)

    # Perform validation
    validation = await validator.validate_idea(
        project_title=req.project_title,
        project_description=req.project_description,
        target_market=req.target_market,
        user_knowledge_summary=knowledge_summary
    )

    # Store validation in database
    db_validation = DBMarketValidation(
        user_id=current_user.username,
        market_size_estimate=validation.market_size_estimate,
        competition_level=validation.competition_level,
        competitors=validation.competitors,
        unique_advantage=validation.unique_advantage,
        potential_revenue_estimate=validation.potential_revenue,
        validation_sources=validation.validation_sources,
        recommendation=validation.recommendation,
        reasoning=validation.reasoning,
        confidence_score=validation.confidence_score,
        full_analysis=validation.to_dict()
    )
    db.add(db_validation)
    db.commit()
    db.refresh(db_validation)

    logger.info(f"Market validation completed for {current_user.username}: {validation.recommendation}")

    return MarketValidationResponse.model_validate(db_validation)


# =============================================================================
# Quick Ideas Endpoint (Tier 1: Instant, Free)
# =============================================================================

@router.get("/quick-ideas")
@limiter.limit("30/minute")
async def quick_ideas(
    request: Request,
    difficulty: str = None,
    limit: int = 15,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get instant build ideas from pre-computed idea seeds (Tier 1).

    Fast, free, no AI calls - pulls from database only.

    Args:
        difficulty: Optional filter by difficulty (beginner, intermediate, advanced)
        limit: Maximum results (default 15)
        current_user: Authenticated user
        db: Database session

    Returns:
        Instant build ideas from knowledge bank
    """
    from ..idea_seeds_service import get_user_idea_seeds

    # Validate difficulty
    if difficulty and difficulty not in ["beginner", "intermediate", "advanced"]:
        raise HTTPException(400, "Invalid difficulty. Use: beginner, intermediate, advanced")

    # Validate limit
    limit = min(max(1, limit), 30)

    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Get stored idea seeds (instant, from DB)
    ideas = await get_user_idea_seeds(
        db=db,
        knowledge_base_id=kb_id,
        difficulty=difficulty,
        limit=limit
    )

    return {
        "count": len(ideas),
        "ideas": ideas,
        "tier": "quick",
        "message": "Pre-computed ideas from your knowledge bank (instant, free)"
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


# =============================================================================
# Saved Ideas Endpoints (Bookmarking)
# =============================================================================

@router.post("/ideas/save")
@limiter.limit("30/minute")
async def save_idea(
    request: Request,
    idea_seed_id: int = None,
    title: str = None,
    description: str = None,
    suggestion_data: dict = None,
    notes: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Save an idea for later reference.

    Can save either:
    - A pre-computed idea seed (by idea_seed_id)
    - A custom suggestion from /what_can_i_build (by title, description, suggestion_data)

    Args:
        idea_seed_id: ID of an existing idea seed to save
        title: Custom title (for non-seed ideas)
        description: Custom description (for non-seed ideas)
        suggestion_data: Full suggestion JSON (for non-seed ideas)
        notes: Optional user notes
        current_user: Authenticated user
        db: Database session

    Returns:
        Saved idea details
    """
    # Validate input - need either idea_seed_id or title
    if not idea_seed_id and not title:
        raise HTTPException(400, "Must provide either idea_seed_id or title")

    # If saving an idea seed, verify it exists
    if idea_seed_id:
        seed = db.query(DBBuildIdeaSeed).filter_by(id=idea_seed_id).first()
        if not seed:
            raise HTTPException(404, f"Idea seed {idea_seed_id} not found")

        # Check if already saved
        existing = db.query(DBSavedIdea).filter_by(
            user_id=current_user.username,
            idea_seed_id=idea_seed_id
        ).first()
        if existing:
            return {
                "message": "Idea already saved",
                "saved_idea": {
                    "id": existing.id,
                    "title": seed.title,
                    "status": existing.status,
                    "saved_at": existing.created_at.isoformat()
                }
            }

    # Create saved idea
    saved_idea = DBSavedIdea(
        user_id=current_user.username,
        idea_seed_id=idea_seed_id,
        custom_title=title if not idea_seed_id else None,
        custom_description=description if not idea_seed_id else None,
        custom_data=suggestion_data if not idea_seed_id else None,
        notes=notes,
        status="saved"
    )
    db.add(saved_idea)
    db.commit()
    db.refresh(saved_idea)

    logger.info(f"User {current_user.username} saved idea: {title or idea_seed_id}")

    return {
        "message": "Idea saved successfully",
        "saved_idea": {
            "id": saved_idea.id,
            "title": title or (saved_idea.idea_seed.title if saved_idea.idea_seed else "Unknown"),
            "status": saved_idea.status,
            "saved_at": saved_idea.created_at.isoformat()
        }
    }


@router.get("/ideas/saved")
@limiter.limit("30/minute")
async def get_saved_ideas(
    request: Request,
    status: str = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's saved ideas.

    Args:
        status: Optional filter by status (saved, started, completed)
        limit: Maximum results (default 50)
        current_user: Authenticated user
        db: Database session

    Returns:
        List of saved ideas
    """
    query = db.query(DBSavedIdea).filter_by(user_id=current_user.username)

    if status:
        if status not in ["saved", "started", "completed"]:
            raise HTTPException(400, "Invalid status. Use: saved, started, completed")
        query = query.filter_by(status=status)

    saved_ideas = query.order_by(DBSavedIdea.created_at.desc()).limit(limit).all()

    ideas = []
    for si in saved_ideas:
        if si.idea_seed:
            ideas.append({
                "id": si.id,
                "title": si.idea_seed.title,
                "description": si.idea_seed.description,
                "difficulty": si.idea_seed.difficulty,
                "feasibility": si.idea_seed.feasibility,
                "effort_estimate": si.idea_seed.effort_estimate,
                "notes": si.notes,
                "status": si.status,
                "source": "seed",
                "seed_id": si.idea_seed_id,
                "saved_at": si.created_at.isoformat()
            })
        else:
            ideas.append({
                "id": si.id,
                "title": si.custom_title,
                "description": si.custom_description,
                "data": si.custom_data,
                "notes": si.notes,
                "status": si.status,
                "source": "custom",
                "saved_at": si.created_at.isoformat()
            })

    return {
        "count": len(ideas),
        "saved_ideas": ideas
    }


@router.put("/ideas/saved/{saved_id}")
@limiter.limit("30/minute")
async def update_saved_idea(
    saved_id: int,
    request: Request,
    status: str = None,
    notes: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a saved idea (status, notes).

    Args:
        saved_id: ID of saved idea to update
        status: New status (saved, started, completed)
        notes: Updated notes
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated saved idea
    """
    saved_idea = db.query(DBSavedIdea).filter_by(
        id=saved_id,
        user_id=current_user.username
    ).first()

    if not saved_idea:
        raise HTTPException(404, f"Saved idea {saved_id} not found")

    if status:
        if status not in ["saved", "started", "completed"]:
            raise HTTPException(400, "Invalid status. Use: saved, started, completed")
        saved_idea.status = status

    if notes is not None:
        saved_idea.notes = notes

    db.commit()

    return {
        "message": "Saved idea updated",
        "id": saved_idea.id,
        "status": saved_idea.status,
        "notes": saved_idea.notes
    }


@router.delete("/ideas/saved/{saved_id}")
@limiter.limit("30/minute")
async def delete_saved_idea(
    saved_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Remove a saved idea.

    Args:
        saved_id: ID of saved idea to delete
        current_user: Authenticated user
        db: Database session

    Returns:
        Confirmation message
    """
    saved_idea = db.query(DBSavedIdea).filter_by(
        id=saved_id,
        user_id=current_user.username
    ).first()

    if not saved_idea:
        raise HTTPException(404, f"Saved idea {saved_id} not found")

    db.delete(saved_idea)
    db.commit()

    logger.info(f"User {current_user.username} deleted saved idea {saved_id}")

    return {"message": f"Saved idea {saved_id} deleted"}
