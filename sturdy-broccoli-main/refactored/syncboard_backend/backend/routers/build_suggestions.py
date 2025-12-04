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
from fastapi import APIRouter, HTTPException, Request, Depends, Body
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from ..models import (
    User, BuildSuggestionRequest,
    GoalDrivenSuggestionsRequest, GoalDrivenSuggestionsResponse,
    MarketValidationRequest, MarketValidationResponse,
    SaveIdeaRequest, UpdateSavedIdeaRequest, SavedIdeaResponse, MegaProjectRequest
)
from ..dependencies import (
    get_current_user,
    get_repository,
    get_kb_documents,
    get_kb_metadata,
    get_kb_clusters,
    get_user_default_kb_id,
    get_build_suggester,
)
from ..repository_interface import KnowledgeBankRepository
from ..database import get_db, get_db_context
from ..sanitization import validate_positive_integer
from ..constants import MAX_SUGGESTIONS
from ..db_models import DBProjectGoal, DBProjectAttempt, DBMarketValidation, DBSavedIdea, DBBuildIdeaSeed
from ..redis_client import get_cached_build_suggestions, cache_build_suggestions
from ..config import settings

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

@router.get("/quick-ideas")
@limiter.limit("30/minute")
async def quick_ideas(
    request: Request,
    difficulty: str = None,
    limit: int = 15,
    repo: KnowledgeBankRepository = Depends(get_repository),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get instant build ideas by analyzing documents directly (no pre-computation).

    This endpoint now calls the main build suggestion logic and formats results
    as QuickIdea objects for backward compatibility.

    Args:
        difficulty: Optional filter by difficulty (beginner, intermediate, advanced)
        limit: Maximum results (default 15, max 30)
        current_user: Authenticated user
        repo: Repository instance
        db: Database session

    Returns:
        Instant build ideas generated from knowledge bank analysis
    """
    from datetime import datetime

    # Validate difficulty
    if difficulty and difficulty not in ["beginner", "intermediate", "advanced"]:
        raise HTTPException(400, "Invalid difficulty. Use: beginner, intermediate, advanced")

    # Validate limit
    limit = min(max(1, limit), 30)

    # Get user's default knowledge base ID
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Get KB-scoped storage from repository
    kb_documents = await repo.get_documents_by_kb(kb_id)
    kb_metadata = await repo.get_metadata_by_kb(kb_id)
    kb_clusters = await repo.get_clusters_by_kb(kb_id)
    build_suggester = get_build_suggester()

    # KB is already user-scoped via get_user_default_kb_id()
    # No need for additional filtering - all KB documents/clusters belong to this user
    user_clusters = kb_clusters
    user_metadata = kb_metadata
    user_documents = kb_documents

    # Return early if no clusters exist in the knowledge base
    if not user_clusters:
        return {
            "count": 0,
            "ideas": [],
            "tier": "quick",
            "message": "No knowledge found. Upload documents to generate ideas."
        }

    # Generate suggestions using the main build suggester
    suggestions = await build_suggester.analyze_knowledge_bank(
        clusters=user_clusters,
        metadata=user_metadata,
        documents=user_documents,
        max_suggestions=limit,
        enable_quality_filter=True
    )

    # Map BuildSuggestion -> QuickIdea format for frontend compatibility
    # Difficulty mapping: complexity_level -> difficulty
    difficulty_map = {
        "beginner": "easy",
        "intermediate": "medium",
        "advanced": "hard"
    }

    quick_ideas = []
    for idx, suggestion in enumerate(suggestions):
        # Map complexity_level to difficulty
        complexity = suggestion.complexity_level or "intermediate"
        mapped_difficulty = difficulty_map.get(complexity, "medium")

        # Filter by difficulty if specified
        if difficulty and mapped_difficulty != difficulty.replace("easy", "beginner").replace("medium", "intermediate").replace("hard", "advanced"):
            continue

        # Get first relevant document as source (if any)
        source_doc_id = None
        source_filename = None
        source_type = None
        if suggestion.relevant_clusters and len(suggestion.relevant_clusters) > 0:
            cluster_id = suggestion.relevant_clusters[0]
            cluster_docs = [did for did, meta in user_metadata.items() if meta.cluster_id == cluster_id]
            if cluster_docs:
                source_doc_id = cluster_docs[0]
                source_meta = user_metadata.get(source_doc_id)
                if source_meta:
                    source_filename = source_meta.title or f"Document {source_doc_id}"
                    source_type = source_meta.source_type

        quick_ideas.append({
            "id": idx + 1,  # Generate sequential ID
            "title": suggestion.title,
            "description": suggestion.description,
            "difficulty": mapped_difficulty,
            "feasibility": suggestion.feasibility,
            "effort_estimate": suggestion.effort_estimate,
            "dependencies": suggestion.required_skills or [],
            "source_document": {
                "id": str(source_doc_id) if source_doc_id else None,
                "filename": source_filename,
                "source_type": source_type
            },
            "created_at": datetime.utcnow().isoformat()
        })

    return {
        "count": len(quick_ideas),
        "ideas": quick_ideas,
        "tier": "quick",
        "message": f"Generated {len(quick_ideas)} ideas from document analysis"
    }


@router.post("/what_can_i_build")
@limiter.limit("3/minute")
async def what_can_i_build(
    req: BuildSuggestionRequest,
    request: Request,
    repo: KnowledgeBankRepository = Depends(get_repository),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze knowledge bank and suggest viable projects.

    Rate limited to 3 requests per minute (expensive operation).

    Args:
        req: Build suggestion request with max_suggestions parameter
        request: FastAPI request (for rate limiting)
        repo: Repository instance
        current_user: Authenticated user
        db: Database session

    Returns:
        Project suggestions based on user's knowledge bank
    """
    # Get user's default knowledge base ID
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Get KB-scoped storage from repository
    kb_documents = await repo.get_documents_by_kb(kb_id)
    kb_metadata = await repo.get_metadata_by_kb(kb_id)
    kb_clusters = await repo.get_clusters_by_kb(kb_id)
    build_suggester = get_build_suggester()

    # Validate max_suggestions parameter
    max_suggestions = validate_positive_integer(req.max_suggestions, "max_suggestions", max_value=MAX_SUGGESTIONS)
    if max_suggestions < 1:
        max_suggestions = 5

    # KB is already user-scoped via get_user_default_kb_id()
    # No need for additional filtering - all KB documents/clusters belong to this user
    user_clusters = kb_clusters
    user_metadata = kb_metadata
    user_documents = kb_documents

    # Return early if no clusters exist in the knowledge base
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

    # Validate cache has ENOUGH suggestions for the request
    if cached_suggestions:
        suggestions_list = cached_suggestions.get("suggestions", [])
        cached_count = len(suggestions_list)

        if cached_count >= max_suggestions and suggestions_list:
            logger.info(f"Cache HIT: {cached_count} cached, {max_suggestions} requested for {current_user.username}")
            # Return only the requested amount from cache
            cached_suggestions["suggestions"] = suggestions_list[:max_suggestions]
            return cached_suggestions
        elif cached_count > 0:
            logger.info(f"Cache INSUFFICIENT: has {cached_count}, need {max_suggestions} for {current_user.username} – regenerating")
        else:
            logger.info(f"Cache STALE (empty suggestions) for {current_user.username} – regenerating")

    # Cache miss - generate suggestions from knowledge bank analysis
    logger.info(f"Cache MISS: Generating build suggestions for {current_user.username}")
    suggestions = await build_suggester.analyze_knowledge_bank(
        clusters=user_clusters,
        metadata=user_metadata,
        documents=user_documents,
        max_suggestions=max_suggestions,
        enable_quality_filter=req.enable_quality_filter
    )

    result = {
        "suggestions": [s.dict() for s in suggestions],
        "knowledge_summary": {
            "total_docs": len(user_documents),
            "total_clusters": len(user_clusters),
            "clusters": [c.dict() for c in user_clusters.values()]
        }
    }

    # Cache the result for 30 minutes (1800 seconds) only if we have suggestions
    if result["suggestions"]:
        cache_build_suggestions(
            user_id=current_user.username,
            suggestions=result,
            ttl=1800
        )
    else:
        logger.info(f"Not caching empty build suggestions for {current_user.username}")

    return result


# =============================================================================
# Goal-Driven Build Suggestions (Phase 10)
# =============================================================================

@router.post("/what_can_i_build/goal-driven")
@limiter.limit("3/minute")
async def what_can_i_build_goal_driven(
    req: GoalDrivenSuggestionsRequest,
    request: Request,
    repo: KnowledgeBankRepository = Depends(get_repository),
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
        repo: Repository instance
        current_user: Authenticated user
        db: Database session

    Returns:
        Comprehensive project suggestions with code, learning paths, and market validation
    """
    from ..llm_providers import OpenAIProvider

    # Get user's default knowledge base ID
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Get KB-scoped storage from repository
    kb_documents = await repo.get_documents_by_kb(kb_id)
    kb_metadata = await repo.get_metadata_by_kb(kb_id)
    kb_clusters = await repo.get_clusters_by_kb(kb_id)
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
    api_key = settings.openai_api_key
    if not api_key:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")

    provider = OpenAIProvider(
        api_key=api_key,
        suggestion_model="gpt-5-mini"
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
    repo: KnowledgeBankRepository = Depends(get_repository),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Validate market viability for a project idea.

    Uses AI to analyze competition, market size, and unique advantages.

    Args:
        req: Market validation request with project details
        repo: Repository instance
        current_user: Authenticated user
        db: Database session

    Returns:
        Comprehensive market validation analysis
    """
    from ..market_validator import MarketValidator
    from ..llm_providers import OpenAIProvider

    # Get user's knowledge for context
    kb_id = get_user_default_kb_id(current_user.username, db)
    kb_documents = await repo.get_documents_by_kb(kb_id)
    kb_metadata = await repo.get_metadata_by_kb(kb_id)

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
    api_key = settings.openai_api_key
    if not api_key:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")

    provider = OpenAIProvider(api_key=api_key, suggestion_model="gpt-5-mini")
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
# Saved Ideas Endpoints (Bookmarking)
# =============================================================================

@router.post("/ideas/save")
@limiter.limit("30/minute")
async def save_idea(
    request: Request,
    idea_data: SaveIdeaRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Save an idea for later reference.

    Can save either:
    - A pre-computed idea seed (by idea_seed_id)
    - A custom suggestion from /what_can_i_build (by title, description, suggestion_data)

    Args:
        idea_data: Validated request containing idea_seed_id OR (title, description, suggestion_data)
        current_user: Authenticated user
        db: Database session

    Returns:
        Saved idea details
    """
    # Extract fields from validated request
    idea_seed_id = idea_data.idea_seed_id
    title = idea_data.title
    description = idea_data.description
    suggestion_data = idea_data.suggestion_data
    notes = idea_data.notes

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
    update_data: UpdateSavedIdeaRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a saved idea (status, notes).

    Args:
        saved_id: ID of saved idea to update
        update_data: Validated update request
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

    # Update fields if provided
    if update_data.status:
        saved_idea.status = update_data.status

    if update_data.notes is not None:
        saved_idea.notes = update_data.notes

    db.commit()
    db.refresh(saved_idea)

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


# =============================================================================
# Mega-Project Endpoint (Combine Multiple Ideas)
# =============================================================================

@router.post("/ideas/mega-project")
@limiter.limit("3/minute")
async def create_mega_project(
    request: Request,
    project_data: MegaProjectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Combine multiple saved ideas into a unified mega-project.

    Takes selected saved ideas and uses AI to synthesize them into a single
    comprehensive project with:
    - Combined tech stack
    - Unified file structure
    - Integrated starter code
    - Merged learning path
    - Single implementation roadmap

    Args:
        project_data: Validated request with idea IDs and optional title
        current_user: Authenticated user
        db: Database session

    Returns:
        Comprehensive mega-project combining all selected ideas
    """
    from ..llm_providers import OpenAIProvider

    idea_ids = project_data.idea_ids
    title = project_data.custom_title

    # Fetch all saved ideas
    saved_ideas = db.query(DBSavedIdea).filter(
        DBSavedIdea.id.in_(idea_ids),
        DBSavedIdea.user_id == current_user.username
    ).all()

    if len(saved_ideas) != len(idea_ids):
        found_ids = {si.id for si in saved_ideas}
        missing = [i for i in idea_ids if i not in found_ids]
        raise HTTPException(404, f"Saved ideas not found: {missing}")

    # Collect all idea data
    ideas_data = []
    all_skills = set()
    all_learning = []

    for si in saved_ideas:
        if si.idea_seed:
            idea = {
                "title": si.idea_seed.title,
                "description": si.idea_seed.description,
                "difficulty": si.idea_seed.difficulty,
                "skills": si.idea_seed.required_skills or [],
                "starter_steps": si.idea_seed.starter_steps or [],
                "file_structure": si.idea_seed.file_structure,
                "starter_code": si.idea_seed.starter_code,
            }
            all_skills.update(si.idea_seed.required_skills or [])
        else:
            custom_data = si.custom_data or {}
            idea = {
                "title": si.custom_title,
                "description": si.custom_description,
                "difficulty": custom_data.get("complexity_level"),
                "skills": custom_data.get("required_skills", []),
                "starter_steps": custom_data.get("starter_steps", []),
                "file_structure": custom_data.get("file_structure"),
                "starter_code": custom_data.get("starter_code"),
                "learning_path": custom_data.get("learning_path", []),
            }
            all_skills.update(custom_data.get("required_skills", []))
            all_learning.extend(custom_data.get("learning_path", []))
        ideas_data.append(idea)

    # Initialize LLM provider
    api_key = settings.openai_api_key
    if not api_key:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")

    provider = OpenAIProvider(api_key=api_key, suggestion_model="gpt-5-mini")

    # Build the mega-project prompt
    ideas_summary = "\n\n".join([
        f"**Idea {i+1}: {idea['title']}**\n"
        f"Description: {idea['description']}\n"
        f"Skills: {', '.join(idea.get('skills', []))}\n"
        f"Steps: {'; '.join(idea.get('starter_steps', [])[:5])}"
        for i, idea in enumerate(ideas_data)
    ])

    prompt = f"""You are an expert software architect. Combine these {len(ideas_data)} project ideas into ONE unified mega-project.

## Ideas to Combine:
{ideas_summary}

## Your Task:
Create a comprehensive mega-project that intelligently combines all these ideas into a single, cohesive application.

Return a JSON object with this exact structure:
{{
    "title": "Compelling mega-project title",
    "description": "2-3 sentence description of the unified project",
    "value_proposition": "What unique value does combining these ideas provide?",
    "tech_stack": {{
        "languages": ["list of programming languages"],
        "frameworks": ["list of frameworks"],
        "databases": ["list of databases if needed"],
        "tools": ["supporting tools"]
    }},
    "architecture": "Brief description of how the components fit together",
    "file_structure": "Multi-line string showing complete project structure",
    "starter_code": "Complete starter code for the main entry point",
    "modules": [
        {{
            "name": "module name",
            "purpose": "what this module does",
            "files": ["list of files"],
            "from_idea": "which original idea this relates to"
        }}
    ],
    "implementation_roadmap": [
        {{
            "phase": 1,
            "title": "Phase title",
            "tasks": ["list of tasks"],
            "estimated_hours": 10
        }}
    ],
    "learning_path": ["ordered list of things to learn/master"],
    "complexity_level": "beginner|intermediate|advanced",
    "total_effort_estimate": "e.g., '40-60 hours'",
    "expected_outcomes": ["what the user will achieve"],
    "potential_extensions": ["future enhancement ideas"]
}}

Be creative but practical. The mega-project should feel natural, not forced."""

    try:
        # Use chat_completion instead of non-existent complete() method
        response = await provider.chat_completion([
            {"role": "system", "content": "You are an expert project architect who creates comprehensive mega-projects."},
            {"role": "user", "content": prompt}
        ])

        # Parse the JSON response
        import json
        import re

        # Extract JSON from potential markdown code blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
        if json_match:
            response = json_match.group(1)

        try:
            mega_project = json.loads(response.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse mega-project JSON: {e}\nResponse: {response[:500]}")
            raise HTTPException(500, "AI returned invalid response. Please try again.")

        # Validate required fields
        required_fields = ["title", "description", "tech_stack"]
        missing_fields = [f for f in required_fields if f not in mega_project]
        if missing_fields:
            logger.error(f"Mega-project missing required fields: {missing_fields}")
            raise HTTPException(500, "Generated project is incomplete. Please try again.")

        # Add metadata
        mega_project["source_ideas"] = [
            {"id": si.id, "title": ideas_data[i]["title"]}
            for i, si in enumerate(saved_ideas)
        ]
        mega_project["combined_skills"] = list(all_skills)
        mega_project["created_by"] = current_user.username

        logger.info(f"Created mega-project '{mega_project['title']}' from {len(ideas_data)} ideas for {current_user.username}")

        return {
            "status": "success",
            "mega_project": mega_project
        }
    except HTTPException:
        # Re-raise HTTP exceptions (validation errors, etc.)
        raise
    except Exception as e:
        logger.error(f"Mega-project generation failed: {e}")
        raise HTTPException(500, f"Failed to create mega-project: {str(e)}")
