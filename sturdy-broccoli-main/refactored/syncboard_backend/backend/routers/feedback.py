"""
Feedback Router for Agentic Learning System.

Endpoints:
- POST /feedback/cluster-move - Record when user moves document to different cluster
- POST /feedback/concept-edit - Record when user edits extracted concepts
- POST /feedback/validate - Record explicit validation of AI decision
- GET /feedback/pending - Get low-confidence decisions needing validation
- GET /feedback/metrics - Get learning metrics for current user
- GET /feedback/accuracy - Get AI accuracy metrics
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ..models import User
from ..dependencies import get_current_user, get_user_default_kb_id
from ..database import get_db
from sqlalchemy.orm import Session
from ..feedback_service import feedback_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/feedback",
    tags=["feedback"],
    responses={401: {"description": "Unauthorized"}},
)


# =============================================================================
# Request Models
# =============================================================================

class ClusterMoveRequest(BaseModel):
    """Request to record cluster move feedback."""
    document_id: int
    from_cluster_id: Optional[int]
    to_cluster_id: int
    ai_decision_id: Optional[int] = None
    user_reasoning: Optional[str] = None


class ConceptEditRequest(BaseModel):
    """Request to record concept edit feedback."""
    document_id: int
    original_concepts: List[str]
    new_concepts: List[str]
    ai_decision_id: Optional[int] = None
    user_reasoning: Optional[str] = None


class ValidationRequest(BaseModel):
    """Request to validate an AI decision."""
    ai_decision_id: int
    accepted: bool
    user_reasoning: Optional[str] = None


# =============================================================================
# Feedback Recording Endpoints
# =============================================================================

@router.post("/cluster-move")
async def record_cluster_move(
    request: ClusterMoveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Record when user moves a document to a different cluster.

    This is a critical learning signal - user disagreed with clustering decision.

    Args:
        request: Cluster move details
        current_user: Authenticated user
        db: Database session

    Returns:
        Feedback ID and learning status
    """
    kb_id = get_user_default_kb_id(current_user.username, db)

    feedback_id = await feedback_service.record_cluster_move(
        username=current_user.username,
        document_id=request.document_id,
        from_cluster_id=request.from_cluster_id,
        to_cluster_id=request.to_cluster_id,
        knowledge_base_id=kb_id,
        ai_decision_id=request.ai_decision_id,
        user_reasoning=request.user_reasoning
    )

    logger.info(
        f"User {current_user.username} moved doc {request.document_id} "
        f"from cluster {request.from_cluster_id} to {request.to_cluster_id}"
    )

    return {
        "feedback_id": feedback_id,
        "message": "Cluster move recorded. System will learn from this correction.",
        "learning_active": True
    }


@router.post("/concept-edit")
async def record_concept_edit(
    request: ConceptEditRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Record when user edits extracted concepts.

    Learn which concepts were wrong or missing.

    Args:
        request: Concept edit details
        current_user: Authenticated user
        db: Database session

    Returns:
        Feedback ID and what was learned
    """
    kb_id = get_user_default_kb_id(current_user.username, db)

    feedback_id = await feedback_service.record_concept_edit(
        username=current_user.username,
        document_id=request.document_id,
        original_concepts=request.original_concepts,
        new_concepts=request.new_concepts,
        knowledge_base_id=kb_id,
        ai_decision_id=request.ai_decision_id,
        user_reasoning=request.user_reasoning
    )

    added = set(request.new_concepts) - set(request.original_concepts)
    removed = set(request.original_concepts) - set(request.new_concepts)

    logger.info(
        f"User {current_user.username} edited concepts for doc {request.document_id}: "
        f"added={len(added)}, removed={len(removed)}"
    )

    return {
        "feedback_id": feedback_id,
        "message": "Concept edit recorded. System will improve future extractions.",
        "added_concepts": list(added),
        "removed_concepts": list(removed),
        "learning_active": True
    }


@router.post("/validate")
async def validate_ai_decision(
    request: ValidationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Explicitly validate or reject an AI decision.

    Used when system asks "Is this correct?" for low-confidence decisions.

    Args:
        request: Validation details
        current_user: Authenticated user

    Returns:
        Feedback ID and updated confidence metrics
    """
    feedback_id = await feedback_service.record_validation(
        username=current_user.username,
        ai_decision_id=request.ai_decision_id,
        accepted=request.accepted,
        user_reasoning=request.user_reasoning
    )

    logger.info(
        f"User {current_user.username} validated decision {request.ai_decision_id}: "
        f"accepted={request.accepted}"
    )

    return {
        "feedback_id": feedback_id,
        "message": "Validation recorded. System confidence updated.",
        "accepted": request.accepted,
        "learning_active": True
    }


# =============================================================================
# Feedback Query Endpoints
# =============================================================================

@router.get("/pending")
async def get_pending_validations(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get low-confidence AI decisions that need user validation.

    These are decisions where the AI is uncertain and wants user feedback.

    Args:
        limit: Maximum number of decisions to return
        current_user: Authenticated user
        db: Database session

    Returns:
        List of low-confidence decisions needing validation
    """
    kb_id = get_user_default_kb_id(current_user.username, db)

    decisions = await feedback_service.get_low_confidence_decisions(
        username=current_user.username,
        knowledge_base_id=kb_id,
        limit=limit
    )

    # Convert to dict for response
    pending = []
    for decision in decisions:
        pending.append({
            "id": decision.id,
            "decision_type": decision.decision_type,
            "confidence_score": decision.confidence_score,
            "output_data": decision.output_data,
            "document_id": decision.document_id,
            "cluster_id": decision.cluster_id,
            "created_at": decision.created_at.isoformat(),
            "needs_validation": feedback_service.should_ask_for_validation(decision.confidence_score)
        })

    logger.info(f"Retrieved {len(pending)} pending validations for {current_user.username}")

    return {
        "pending_decisions": pending,
        "count": len(pending),
        "message": "These decisions have low confidence and would benefit from your review."
    }


@router.get("/validation-prompts")
async def get_validation_prompts(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user-friendly validation prompts for low-confidence decisions (Phase C).

    Returns natural language prompts that users can easily understand and validate.
    Perfect for displaying in a validation UI.

    Args:
        limit: Maximum number of prompts to return
        current_user: Authenticated user
        db: Database session

    Returns:
        {
            "prompts": [...],  # List of user-friendly validation prompts
            "summary": {...},  # Summary stats
            "count": 5
        }
    """
    from ..validation_prompts import generate_validation_prompt, format_validation_summary

    kb_id = get_user_default_kb_id(current_user.username, db)

    decisions = await feedback_service.get_low_confidence_decisions(
        username=current_user.username,
        knowledge_base_id=kb_id,
        limit=limit
    )

    # Generate user-friendly prompts
    prompts = []
    for decision in decisions:
        prompt = generate_validation_prompt(
            decision_type=decision.decision_type,
            output_data=decision.output_data,
            confidence_score=decision.confidence_score
        )

        # Add decision metadata
        prompt["decision_id"] = decision.id
        prompt["document_id"] = decision.document_id
        prompt["cluster_id"] = decision.cluster_id
        prompt["created_at"] = decision.created_at.isoformat()

        prompts.append(prompt)

    # Generate summary
    summary = format_validation_summary(prompts)

    logger.info(
        f"Generated {len(prompts)} validation prompts for {current_user.username} "
        f"(urgency: {summary['urgency_level']}, avg confidence: {summary['average_confidence']:.2f})"
    )

    return {
        "prompts": prompts,
        "summary": summary,
        "count": len(prompts)
    }


@router.get("/metrics")
async def get_learning_metrics(
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive learning metrics for current user.

    Shows:
    - Total AI decisions made
    - Acceptance rate
    - Average confidence
    - Feedback provided
    - Improvement potential

    Args:
        current_user: Authenticated user

    Returns:
        Learning metrics and trends
    """
    metrics = await feedback_service.get_learning_metrics(current_user.username)

    logger.info(f"Retrieved learning metrics for {current_user.username}")

    return {
        "metrics": metrics,
        "interpretation": {
            "acceptance_rate": "High acceptance rate (>80%) means AI is learning your preferences",
            "average_confidence": "Average confidence reflects AI certainty",
            "unprocessed_feedback": "Feedback waiting to be incorporated into learning"
        }
    }


@router.get("/accuracy")
async def get_accuracy_metrics(
    decision_type: str,
    days: int = 30,
    current_user: User = Depends(get_current_user)
):
    """
    Get accuracy metrics for AI decisions by type.

    Shows how accurate the AI is for:
    - Concept extraction
    - Clustering
    - Classification
    - etc.

    Args:
        decision_type: Type of decision to analyze
        days: Number of days to look back
        current_user: Authenticated user

    Returns:
        Accuracy metrics by confidence level
    """
    accuracy = await feedback_service.get_decision_accuracy(
        decision_type=decision_type,
        username=current_user.username,
        days=days
    )

    logger.info(
        f"Retrieved accuracy metrics for {current_user.username}: "
        f"type={decision_type}, accuracy={accuracy.get('accuracy', 0):.2%}"
    )

    return {
        "decision_type": decision_type,
        "accuracy_metrics": accuracy,
        "interpretation": {
            "overall": f"{accuracy.get('accuracy', 0):.1%} of decisions were correct",
            "by_confidence": "Accuracy broken down by confidence level",
            "sample_size": f"Based on {accuracy.get('sample_size', 0)} validated decisions"
        }
    }


@router.get("/patterns")
async def get_feedback_patterns(
    feedback_type: Optional[str] = None,
    days: int = 90,
    current_user: User = Depends(get_current_user)
):
    """
    Get user's feedback patterns to understand preferences.

    Analyzes:
    - Most common corrections
    - Preferred cluster granularity
    - Concept preferences

    Args:
        feedback_type: Optional filter by feedback type
        days: Number of days to analyze
        current_user: Authenticated user

    Returns:
        Feedback patterns and preferences
    """
    patterns = await feedback_service.get_user_feedback_patterns(
        username=current_user.username,
        feedback_type=feedback_type,
        days=days
    )

    logger.info(f"Retrieved feedback patterns for {current_user.username}")

    return {
        "patterns": patterns,
        "interpretation": {
            "total_feedback": f"{patterns['total_feedback']} corrections in last {days} days",
            "by_type": "Breakdown of correction types",
            "learning_progress": "System is adapting to your preferences"
        }
    }


# =============================================================================
# Phase D - Frontend Compatibility Endpoints
# =============================================================================

class SubmitFeedbackRequest(BaseModel):
    """Request to submit feedback from frontend (Phase D)."""
    decision_id: int
    validation_result: str  # 'accepted', 'rejected', 'partial'
    new_value: Optional[dict] = None
    user_reasoning: Optional[str] = None


@router.post("/submit")
async def submit_feedback(
    request: SubmitFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit user feedback for an AI decision (Phase D frontend compatibility).

    Supports three validation results:
    - 'accepted': AI was correct
    - 'rejected': AI was wrong
    - 'partial': AI was partially correct, user provides corrections

    Args:
        request: Feedback details with validation result
        current_user: Authenticated user
        db: Database session

    Returns:
        User feedback record
    """
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Convert validation_result to accepted boolean
    accepted = request.validation_result == 'accepted'

    # Record validation
    feedback_id = await feedback_service.record_validation(
        username=current_user.username,
        ai_decision_id=request.decision_id,
        accepted=accepted,
        user_reasoning=request.user_reasoning
    )

    # If partial/rejected with corrections, record the new value
    if request.new_value and request.validation_result in ['partial', 'rejected']:
        # Import db_models to access DBUserFeedback
        from ..db_models import DBUserFeedback

        # Create additional feedback record for the correction
        feedback = DBUserFeedback(
            feedback_type='concept_correction',
            username=current_user.username,
            knowledge_base_id=kb_id,
            ai_decision_id=request.decision_id,
            original_value=None,  # Could fetch from decision if needed
            new_value=request.new_value,
            user_reasoning=request.user_reasoning,
            processed=False
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)

        logger.info(f"Recorded correction for decision {request.decision_id}")

        return {
            "id": feedback.id,
            "feedback_type": feedback.feedback_type,
            "username": feedback.username,
            "knowledge_base_id": feedback.knowledge_base_id,
            "document_id": feedback.document_id,
            "ai_decision_id": feedback.ai_decision_id,
            "original_value": feedback.original_value,
            "new_value": feedback.new_value,
            "user_reasoning": feedback.user_reasoning,
            "processed": feedback.processed,
            "created_at": feedback.created_at.isoformat()
        }

    # Return validation feedback
    logger.info(f"Submitted feedback for decision {request.decision_id}: {request.validation_result}")

    return {
        "id": feedback_id,
        "feedback_type": "validation",
        "validation_result": request.validation_result,
        "accepted": accepted,
        "message": "Feedback recorded successfully"
    }


@router.get("/low-confidence-decisions")
async def get_low_confidence_decisions(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get low-confidence AI decisions (Phase D frontend compatibility).

    Alias for /pending endpoint with frontend-compatible format.

    Args:
        limit: Maximum number of decisions to return
        current_user: Authenticated user
        db: Database session

    Returns:
        List of low-confidence AI decisions
    """
    kb_id = get_user_default_kb_id(current_user.username, db)

    decisions = await feedback_service.get_low_confidence_decisions(
        username=current_user.username,
        knowledge_base_id=kb_id,
        limit=limit
    )

    # Convert to frontend format
    result = []
    for decision in decisions:
        result.append({
            "id": decision.id,
            "decision_type": decision.decision_type,
            "username": decision.username,
            "knowledge_base_id": decision.knowledge_base_id,
            "document_id": decision.document_id,
            "cluster_id": decision.cluster_id,
            "input_data": decision.input_data,
            "output_data": decision.output_data,
            "confidence_score": decision.confidence_score,
            "model_name": decision.model_name,
            "model_version": decision.model_version,
            "validated": decision.validated,
            "validation_result": decision.validation_result,
            "validation_timestamp": decision.validation_timestamp.isoformat() if decision.validation_timestamp else None,
            "created_at": decision.created_at.isoformat()
        })

    return result


@router.get("/accuracy-metrics")
async def get_accuracy_metrics_all(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get overall accuracy metrics across all decision types (Phase D frontend compatibility).

    Returns:
        Comprehensive accuracy metrics with breakdown by confidence range
    """
    from ..db_models import DBAIDecision
    from sqlalchemy import func

    # Get all validated decisions for this user
    validated_decisions = db.query(DBAIDecision).filter(
        DBAIDecision.username == current_user.username,
        DBAIDecision.validated == True,
        DBAIDecision.validation_result.isnot(None)
    ).all()

    if not validated_decisions:
        return {
            "overall_accuracy": 0.0,
            "by_confidence_range": {},
            "improvement_trend": 0.0,
            "total_decisions": 0,
            "validated_decisions": 0
        }

    # Calculate overall accuracy
    correct = sum(1 for d in validated_decisions if d.validation_result == 'accepted')
    overall_accuracy = correct / len(validated_decisions) if validated_decisions else 0.0

    # Calculate accuracy by confidence range
    confidence_ranges = {
        "0-50%": {"correct": 0, "total": 0},
        "50-70%": {"correct": 0, "total": 0},
        "70-90%": {"correct": 0, "total": 0},
        "90%+": {"correct": 0, "total": 0}
    }

    for decision in validated_decisions:
        conf = decision.confidence_score
        is_correct = decision.validation_result == 'accepted'

        if conf < 0.5:
            range_key = "0-50%"
        elif conf < 0.7:
            range_key = "50-70%"
        elif conf < 0.9:
            range_key = "70-90%"
        else:
            range_key = "90%+"

        confidence_ranges[range_key]["total"] += 1
        if is_correct:
            confidence_ranges[range_key]["correct"] += 1

    # Convert to frontend format
    by_confidence_range = {}
    for range_key, data in confidence_ranges.items():
        if data["total"] > 0:
            by_confidence_range[range_key] = {
                "accuracy": data["correct"] / data["total"],
                "count": data["total"]
            }

    # Calculate improvement trend (compare first half vs second half)
    mid_point = len(validated_decisions) // 2
    if mid_point > 0:
        first_half_accuracy = sum(1 for d in validated_decisions[:mid_point] if d.validation_result == 'accepted') / mid_point
        second_half_accuracy = sum(1 for d in validated_decisions[mid_point:] if d.validation_result == 'accepted') / (len(validated_decisions) - mid_point)
        improvement_trend = second_half_accuracy - first_half_accuracy
    else:
        improvement_trend = 0.0

    # Get total decisions (including unvalidated)
    total_decisions = db.query(func.count(DBAIDecision.id)).filter(
        DBAIDecision.username == current_user.username
    ).scalar()

    return {
        "overall_accuracy": overall_accuracy,
        "by_confidence_range": by_confidence_range,
        "improvement_trend": improvement_trend,
        "total_decisions": total_decisions,
        "validated_decisions": len(validated_decisions)
    }


@router.get("/decisions/document/{document_id}")
async def get_decision_history_for_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get AI decision history for a specific document (Phase D frontend compatibility).

    Args:
        document_id: Document ID to get decisions for
        current_user: Authenticated user
        db: Database session

    Returns:
        List of AI decisions for this document
    """
    from ..db_models import DBAIDecision

    decisions = db.query(DBAIDecision).filter(
        DBAIDecision.username == current_user.username,
        DBAIDecision.document_id == document_id
    ).order_by(DBAIDecision.created_at.desc()).all()

    result = []
    for decision in decisions:
        result.append({
            "id": decision.id,
            "decision_type": decision.decision_type,
            "username": decision.username,
            "knowledge_base_id": decision.knowledge_base_id,
            "document_id": decision.document_id,
            "cluster_id": decision.cluster_id,
            "input_data": decision.input_data,
            "output_data": decision.output_data,
            "confidence_score": decision.confidence_score,
            "model_name": decision.model_name,
            "model_version": decision.model_version,
            "validated": decision.validated,
            "validation_result": decision.validation_result,
            "validation_timestamp": decision.validation_timestamp.isoformat() if decision.validation_timestamp else None,
            "created_at": decision.created_at.isoformat()
        })

    return result


@router.get("/user-feedback")
async def get_user_feedback_list(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all user feedback submitted (Phase D frontend compatibility).

    Args:
        limit: Maximum number of feedback records to return
        current_user: Authenticated user
        db: Database session

    Returns:
        List of user feedback records
    """
    from ..db_models import DBUserFeedback

    feedback_records = db.query(DBUserFeedback).filter(
        DBUserFeedback.username == current_user.username
    ).order_by(DBUserFeedback.created_at.desc()).limit(limit).all()

    result = []
    for feedback in feedback_records:
        result.append({
            "id": feedback.id,
            "feedback_type": feedback.feedback_type,
            "username": feedback.username,
            "knowledge_base_id": feedback.knowledge_base_id,
            "document_id": feedback.document_id,
            "ai_decision_id": feedback.ai_decision_id,
            "original_value": feedback.original_value,
            "new_value": feedback.new_value,
            "context": feedback.context,
            "user_reasoning": feedback.user_reasoning,
            "processed": feedback.processed,
            "processed_at": feedback.processed_at.isoformat() if feedback.processed_at else None,
            "improvement_score": feedback.improvement_score,
            "created_at": feedback.created_at.isoformat()
        })

    return result
