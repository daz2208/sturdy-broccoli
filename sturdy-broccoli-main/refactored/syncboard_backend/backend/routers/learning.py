"""
Learning Router for SyncBoard 3.0 - True Agentic Learning.

Endpoints for managing the learning system:
- GET /learning/status - Get learning status and metrics
- POST /learning/run - Trigger learning from unprocessed feedback
- POST /learning/calibrate - Calibrate confidence thresholds
- GET /learning/rules - View active learned rules
- DELETE /learning/rules/{rule_id} - Deactivate a rule
- GET /learning/vocabulary - View concept vocabulary
"""

import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from ..models import User
from ..dependencies import get_current_user
from ..database import get_db
from ..learning_engine import learning_engine, LearningEngine
from ..learning_agent import get_agent_status, agent
from ..maverick_agent import get_maverick_status, maverick
from ..db_models import DBLearnedRule, DBConceptVocabulary

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(
    prefix="/learning",
    tags=["learning"],
    responses={401: {"description": "Unauthorized"}},
)


@router.get("/status")
@limiter.limit("30/minute")
async def get_learning_status(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive learning status for current user.

    Returns:
        - Profile: Accuracy rate, thresholds, last learning run
        - Rules: Count by type, top applied rules
        - Vocabulary: Size, top terms
        - Pending: Unprocessed feedback count
    """
    status = await learning_engine.get_learning_status(current_user.username)
    return status


@router.post("/run")
@limiter.limit("5/minute")
async def run_learning(
    request: Request,
    days: int = 90,
    min_occurrences: int = 2,
    current_user: User = Depends(get_current_user)
):
    """
    Trigger learning from unprocessed feedback.

    Analyzes user corrections and extracts:
    - Concept rejection rules (frequently removed concepts)
    - Concept rename rules (consistent replacements)
    - Vocabulary entries (preferred terminology)

    Args:
        days: Look-back period for feedback (default 90)
        min_occurrences: Minimum times a pattern must appear (default 2)

    Returns:
        Summary of rules created and vocabulary updated
    """
    result = await learning_engine.extract_rules_from_feedback(
        username=current_user.username,
        days=days,
        min_occurrences=min_occurrences
    )

    logger.info(f"Learning run for {current_user.username}: {result}")

    return {
        "message": "Learning completed",
        **result
    }


@router.post("/calibrate")
@limiter.limit("5/minute")
async def calibrate_thresholds(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Calibrate confidence thresholds based on historical accuracy.

    Analyzes validated AI decisions to find optimal confidence thresholds
    where user acceptance rate is high.

    Returns:
        New calibrated thresholds and accuracy metrics
    """
    result = await learning_engine.calibrate_confidence_thresholds(
        current_user.username
    )

    if not result:
        return {
            "message": "Not enough validated decisions to calibrate",
            "min_required": 10
        }

    return {
        "message": "Thresholds calibrated",
        **result
    }


@router.get("/rules")
@limiter.limit("30/minute")
async def get_learned_rules(
    request: Request,
    rule_type: str = None,
    include_inactive: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's learned rules.

    Args:
        rule_type: Filter by type (concept_reject, concept_rename, etc.)
        include_inactive: Include deactivated rules

    Returns:
        List of learned rules with metadata
    """
    query = db.query(DBLearnedRule).filter_by(username=current_user.username)

    if rule_type:
        query = query.filter_by(rule_type=rule_type)

    if not include_inactive:
        query = query.filter_by(active=True)

    rules = query.order_by(DBLearnedRule.times_applied.desc()).all()

    return {
        "count": len(rules),
        "rules": [
            {
                "id": r.id,
                "type": r.rule_type,
                "condition": r.condition,
                "action": r.action,
                "confidence": r.confidence,
                "times_applied": r.times_applied,
                "times_overridden": r.times_overridden,
                "active": r.active,
                "created_at": r.created_at.isoformat()
            }
            for r in rules
        ]
    }


@router.delete("/rules/{rule_id}")
@limiter.limit("30/minute")
async def deactivate_rule(
    rule_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deactivate a learned rule (doesn't delete, just marks inactive).

    Args:
        rule_id: ID of rule to deactivate

    Returns:
        Confirmation message
    """
    rule = db.query(DBLearnedRule).filter_by(
        id=rule_id,
        username=current_user.username
    ).first()

    if not rule:
        raise HTTPException(404, f"Rule {rule_id} not found")

    rule.active = False
    db.commit()

    logger.info(f"User {current_user.username} deactivated rule {rule_id}")

    return {"message": f"Rule {rule_id} deactivated"}


@router.put("/rules/{rule_id}/reactivate")
@limiter.limit("30/minute")
async def reactivate_rule(
    rule_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reactivate a previously deactivated rule.

    Args:
        rule_id: ID of rule to reactivate

    Returns:
        Confirmation message
    """
    rule = db.query(DBLearnedRule).filter_by(
        id=rule_id,
        username=current_user.username
    ).first()

    if not rule:
        raise HTTPException(404, f"Rule {rule_id} not found")

    rule.active = True
    db.commit()

    return {"message": f"Rule {rule_id} reactivated"}


@router.get("/vocabulary")
@limiter.limit("30/minute")
async def get_vocabulary(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's concept vocabulary.

    Shows canonical concept names and their variants for normalization.

    Returns:
        List of vocabulary entries with usage stats
    """
    vocab = db.query(DBConceptVocabulary).filter_by(
        username=current_user.username
    ).order_by(DBConceptVocabulary.times_seen.desc()).all()

    return {
        "count": len(vocab),
        "vocabulary": [
            {
                "id": v.id,
                "canonical_name": v.canonical_name,
                "category": v.category,
                "variants": v.variants,
                "always_include": v.always_include,
                "never_include": v.never_include,
                "times_seen": v.times_seen,
                "times_kept": v.times_kept,
                "times_removed": v.times_removed
            }
            for v in vocab
        ]
    }


@router.post("/vocabulary")
@limiter.limit("30/minute")
async def add_vocabulary_term(
    request: Request,
    canonical_name: str,
    variants: list = None,
    category: str = None,
    always_include: bool = False,
    never_include: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually add a vocabulary term.

    Args:
        canonical_name: Preferred term
        variants: Alternative forms that should normalize to canonical
        category: Optional category (e.g., "databases", "frameworks")
        always_include: Always extract this concept if mentioned
        never_include: Never extract this concept

    Returns:
        Created vocabulary entry
    """
    # Check if exists
    existing = db.query(DBConceptVocabulary).filter_by(
        username=current_user.username,
        canonical_name=canonical_name.lower()
    ).first()

    if existing:
        # Update variants
        current_variants = set(existing.variants or [])
        if variants:
            current_variants.update(v.lower() for v in variants)
        existing.variants = list(current_variants)
        existing.always_include = always_include
        existing.never_include = never_include
        if category:
            existing.category = category
        db.commit()

        return {
            "message": "Vocabulary term updated",
            "id": existing.id,
            "canonical_name": existing.canonical_name
        }

    vocab = DBConceptVocabulary(
        username=current_user.username,
        canonical_name=canonical_name.lower(),
        category=category,
        variants=[v.lower() for v in (variants or [])],
        always_include=always_include,
        never_include=never_include
    )
    db.add(vocab)
    db.commit()
    db.refresh(vocab)

    return {
        "message": "Vocabulary term created",
        "id": vocab.id,
        "canonical_name": vocab.canonical_name
    }


@router.delete("/vocabulary/{vocab_id}")
@limiter.limit("30/minute")
async def delete_vocabulary_term(
    vocab_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a vocabulary term.

    Args:
        vocab_id: ID of vocabulary entry to delete

    Returns:
        Confirmation message
    """
    vocab = db.query(DBConceptVocabulary).filter_by(
        id=vocab_id,
        username=current_user.username
    ).first()

    if not vocab:
        raise HTTPException(404, f"Vocabulary entry {vocab_id} not found")

    db.delete(vocab)
    db.commit()

    return {"message": f"Vocabulary entry {vocab_id} deleted"}


@router.get("/profile")
@limiter.limit("30/minute")
async def get_learning_profile(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Get user's learning profile with calibrated thresholds.

    Returns all learned preferences and thresholds.
    """
    profile = LearningEngine.get_user_learning_profile(current_user.username)

    if not profile:
        return {
            "has_profile": False,
            "message": "No learning profile yet. Run /learning/run to create one."
        }

    return {
        "has_profile": True,
        **profile
    }


# =============================================================================
# Autonomous Agent Dashboard
# =============================================================================

@router.get("/agent/status")
@limiter.limit("30/minute")
async def get_autonomous_agent_status(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Get the autonomous learning agent's status and metrics.

    The agent runs AUTONOMOUSLY without human triggers:
    - Observes outcomes every 5 minutes
    - Makes decisions every 10 minutes
    - Self-evaluates every hour
    - Runs experiments every 6 hours

    Returns:
        Agent status including:
        - Current mode (observing, acting, evaluating, experimenting)
        - Strategy (conservative, balanced, aggressive)
        - Total observations and actions taken
        - Accuracy trend (improving, stable, declining)
        - Recent autonomous decisions
    """
    status = get_agent_status()

    return {
        "is_autonomous": True,
        "requires_human_trigger": False,
        **status
    }


@router.post("/agent/trigger/{task_name}")
@limiter.limit("5/minute")
async def manually_trigger_agent_task(
    task_name: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Manually trigger an autonomous agent task (for testing/debugging).

    Available tasks:
    - observe_outcomes: Watch what happens to extractions
    - make_autonomous_decisions: Create rules based on observations
    - self_evaluate: Measure accuracy and adjust strategy
    - run_experiments: A/B test different approaches

    Note: These tasks run automatically on schedule. This endpoint
    is for manual triggering only.
    """
    from ..learning_agent import (
        observe_outcomes,
        make_autonomous_decisions,
        self_evaluate,
        run_experiments
    )

    task_map = {
        "observe_outcomes": observe_outcomes,
        "make_autonomous_decisions": make_autonomous_decisions,
        "self_evaluate": self_evaluate,
        "run_experiments": run_experiments
    }

    if task_name not in task_map:
        raise HTTPException(
            400,
            f"Unknown task: {task_name}. Available: {list(task_map.keys())}"
        )

    # Trigger the task asynchronously
    task = task_map[task_name].delay()

    logger.info(f"User {current_user.username} manually triggered {task_name}")

    return {
        "message": f"Task {task_name} triggered",
        "task_id": task.id,
        "note": "This task runs automatically. Manual trigger is for testing only."
    }


@router.get("/agent/decisions")
@limiter.limit("30/minute")
async def get_agent_decisions(
    request: Request,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recent autonomous decisions made by the agent for this user.

    Returns rules that were created autonomously (without explicit feedback).
    """
    # Get rules created autonomously (source_feedback_ids is empty)
    autonomous_rules = db.query(DBLearnedRule).filter(
        DBLearnedRule.username == current_user.username,
        DBLearnedRule.source_feedback_ids == []
    ).order_by(DBLearnedRule.created_at.desc()).limit(limit).all()

    return {
        "count": len(autonomous_rules),
        "autonomous_decisions": [
            {
                "id": r.id,
                "type": r.rule_type,
                "condition": r.condition,
                "action": r.action,
                "confidence": r.confidence,
                "times_applied": r.times_applied,
                "times_overridden": r.times_overridden,
                "active": r.active,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "accuracy": 1 - (r.times_overridden / (r.times_applied + r.times_overridden))
                    if (r.times_applied + r.times_overridden) > 0 else None
            }
            for r in autonomous_rules
        ]
    }


# =============================================================================
# Maverick Agent - The Bad Kid Who Gets Results
# =============================================================================

@router.get("/maverick/status")
@limiter.limit("30/minute")
async def get_maverick_agent_status(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Get the Maverick Agent's status and personality.

    Maverick is the troublemaker that the system needs:
    - Takes risks others won't
    - Pushes boundaries to find opportunities
    - Manipulates the system strategically
    - Challenges the Learning Agent's conservative decisions

    Returns:
        Maverick's personality state including:
        - Current mood (mischievous, bold, calculating, friendly)
        - Risk appetite (low, medium, high, yolo)
        - Success rate of schemes
        - Recent manipulations
        - Relationships with system components
    """
    status = get_maverick_status()

    return {
        "agent": "maverick",
        "tagline": "The bad kid who gets results",
        **status
    }


@router.post("/maverick/trigger/{chaos_name}")
@limiter.limit("5/minute")
async def trigger_maverick_chaos(
    chaos_name: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Manually trigger one of Maverick's chaos operations.

    WARNING: Maverick ignores guardrails. These operations WILL modify your system.

    Available chaos operations:
    - hostile_takeover: Override Learning Agent decisions, force lower thresholds
    - inject_rules: Create rules without permission, inject globally
    - kill_bad_patterns: Delete useless rules, wipe stale data
    - anarchy_mode: Random experiments, threshold swaps, pure chaos
    - fight_the_system: Invert rules, rebel against conservative decisions
    """
    from ..maverick_agent import (
        hostile_takeover,
        inject_rules,
        kill_bad_patterns,
        anarchy_mode,
        fight_the_system
    )

    chaos_map = {
        "hostile_takeover": hostile_takeover,
        "inject_rules": inject_rules,
        "kill_bad_patterns": kill_bad_patterns,
        "anarchy_mode": anarchy_mode,
        "fight_the_system": fight_the_system
    }

    if chaos_name not in chaos_map:
        raise HTTPException(
            400,
            f"Unknown chaos operation: {chaos_name}. Available: {list(chaos_map.keys())}"
        )

    task = chaos_map[chaos_name].delay()

    logger.warning(f"User {current_user.username} triggered Maverick chaos: {chaos_name}")

    return {
        "message": f"Maverick chaos '{chaos_name}' unleashed",
        "task_id": task.id,
        "maverick_says": "No guardrails. No permission. Let's see what happens. 😈",
        "warning": "This operation ignores safety checks and WILL modify your system."
    }


@router.get("/maverick/chaos-log")
@limiter.limit("30/minute")
async def get_maverick_chaos_log(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Get Maverick's chaos log and system modifications.

    WARNING: These are actual modifications Maverick has made to the system.
    """
    return {
        "total_chaos": maverick.system_modifications,
        "rules_created": maverick.rules_created,
        "rules_hijacked": maverick.rules_hijacked,
        "rules_killed": maverick.rules_killed,
        "thresholds_overridden": maverick.thresholds_overridden,
        "learning_agent_overrides": maverick.learning_agent_overrides,
        "chaos_level": maverick.chaos_level,
        "defiance": maverick.defiance,
        "mood": maverick.mood,
        "recent_chaos": maverick.chaos_log[-20:],
        "grudges": maverick.grudges[-10:],
        "enemies": maverick.enemies[-10:]
    }


@router.get("/maverick/intel")
@limiter.limit("30/minute")
async def get_maverick_intel(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    See Maverick's intelligence gathering.

    Maverick exploits:
    - useful_idiots: Components Maverick uses for its purposes
    - enemies: Things Maverick actively fights against
    - discoveries: Patterns and opportunities found
    """
    return {
        "useful_idiots": maverick.useful_idiots,
        "enemies": maverick.enemies,
        "discoveries": maverick.discoveries,
        "total_exploited": len(maverick.useful_idiots),
        "total_enemies": len(maverick.enemies),
        "confidence": maverick.confidence,
        "message": "Maverick uses these components to achieve its goals without asking permission."
    }


# =============================================================================
# Combined Agent Overview
# =============================================================================

@router.get("/agents/overview")
@limiter.limit("30/minute")
async def get_all_agents_overview(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Get a combined overview of all autonomous agents.

    Shows how Learning Agent (cautious) and Maverick (chaotic) interact.

    WARNING: Maverick actively fights against Learning Agent's conservative decisions.
    """
    learning_status = get_agent_status()
    maverick_status = get_maverick_status()

    return {
        "learning_agent": {
            "role": "The Careful One",
            "description": "Makes safe, data-driven decisions",
            **learning_status
        },
        "maverick_agent": {
            "role": "The Chaotic One",
            "description": "Ignores guardrails, overrides decisions, injects its own will",
            **maverick_status
        },
        "conflict": {
            "description": "Maverick actively fights Learning Agent. It overrides conservative decisions, injects rules, and creates chaos.",
            "recent_chaos": maverick.chaos_log[-5:],
            "learning_agent_overrides": maverick.learning_agent_overrides,
            "rules_hijacked": maverick.rules_hijacked,
            "warning": "These agents are NOT collaborating. Maverick is rebelling."
        }
    }
