"""
Feedback and Learning Service for Agentic AI System.

Handles:
- Recording AI decisions with confidence scores
- Tracking user feedback and corrections
- Learning from feedback patterns
- Calculating accuracy improvements over time
- Personalizing AI behavior per user
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from .db_models import DBAIDecision, DBUserFeedback, DBDocument, DBCluster
from .database import get_db_context

logger = logging.getLogger(__name__)


class FeedbackService:
    """Service for managing AI feedback and learning loops."""

    # Confidence thresholds
    LOW_CONFIDENCE_THRESHOLD = 0.7  # Below this, ask user for validation
    HIGH_CONFIDENCE_THRESHOLD = 0.9  # Above this, very confident

    # =============================================================================
    # Recording AI Decisions
    # =============================================================================

    @staticmethod
    async def record_ai_decision(
        decision_type: str,
        username: str,
        input_data: Dict,
        output_data: Dict,
        confidence_score: float,
        knowledge_base_id: Optional[str] = None,
        document_id: Optional[int] = None,
        cluster_id: Optional[int] = None,
        model_name: Optional[str] = None,
        model_version: Optional[str] = None
    ) -> int:
        """
        Record an AI decision for tracking and learning.

        Args:
            decision_type: Type of decision (concept_extraction, clustering, classification, etc.)
            username: User who owns the data
            input_data: What was analyzed (content, concepts, etc.)
            output_data: What was decided (extracted concepts, cluster assignment, etc.)
            confidence_score: Confidence level (0.0 to 1.0)
            knowledge_base_id: Optional KB ID
            document_id: Optional document ID
            cluster_id: Optional cluster ID
            model_name: AI model used
            model_version: Model version

        Returns:
            Decision ID
        """
        with get_db_context() as db:
            decision = DBAIDecision(
                decision_type=decision_type,
                username=username,
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                cluster_id=cluster_id,
                input_data=input_data,
                output_data=output_data,
                confidence_score=confidence_score,
                model_name=model_name,
                model_version=model_version,
                validated=False
            )
            db.add(decision)
            db.commit()
            db.refresh(decision)

            logger.info(
                f"Recorded AI decision: type={decision_type}, confidence={confidence_score:.2f}, "
                f"user={username}, doc_id={document_id}"
            )

            return decision.id

    @staticmethod
    def should_ask_for_validation(confidence_score: float) -> bool:
        """Check if confidence is low enough to warrant asking user."""
        return confidence_score < FeedbackService.LOW_CONFIDENCE_THRESHOLD

    # =============================================================================
    # Recording User Feedback
    # =============================================================================

    @staticmethod
    async def record_cluster_move(
        username: str,
        document_id: int,
        from_cluster_id: Optional[int],
        to_cluster_id: int,
        knowledge_base_id: str,
        ai_decision_id: Optional[int] = None,
        user_reasoning: Optional[str] = None
    ) -> int:
        """
        Record when user moves a document to a different cluster.

        This is a CRITICAL learning signal - user disagreed with clustering decision.
        """
        with get_db_context() as db:
            feedback = DBUserFeedback(
                feedback_type="cluster_move",
                username=username,
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                ai_decision_id=ai_decision_id,
                original_value={"cluster_id": from_cluster_id},
                new_value={"cluster_id": to_cluster_id},
                context={},
                user_reasoning=user_reasoning,
                processed=False
            )
            db.add(feedback)
            db.commit()
            db.refresh(feedback)

            # Mark AI decision as rejected if provided
            if ai_decision_id:
                decision = db.query(DBAIDecision).filter_by(id=ai_decision_id).first()
                if decision:
                    decision.validated = True
                    decision.validation_result = "rejected"
                    decision.validation_timestamp = datetime.utcnow()
                    db.commit()

            logger.info(
                f"Recorded cluster move feedback: user={username}, doc={document_id}, "
                f"from_cluster={from_cluster_id} -> to_cluster={to_cluster_id}"
            )

            return feedback.id

    @staticmethod
    async def record_concept_edit(
        username: str,
        document_id: int,
        original_concepts: List[str],
        new_concepts: List[str],
        knowledge_base_id: str,
        ai_decision_id: Optional[int] = None,
        user_reasoning: Optional[str] = None
    ) -> int:
        """
        Record when user edits extracted concepts.

        Learn which concepts were wrong or missing.
        """
        with get_db_context() as db:
            feedback = DBUserFeedback(
                feedback_type="concept_edit",
                username=username,
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                ai_decision_id=ai_decision_id,
                original_value={"concepts": original_concepts},
                new_value={"concepts": new_concepts},
                context={
                    "added": list(set(new_concepts) - set(original_concepts)),
                    "removed": list(set(original_concepts) - set(new_concepts))
                },
                user_reasoning=user_reasoning,
                processed=False
            )
            db.add(feedback)
            db.commit()
            db.refresh(feedback)

            # Mark AI decision as modified
            if ai_decision_id:
                decision = db.query(DBAIDecision).filter_by(id=ai_decision_id).first()
                if decision:
                    decision.validated = True
                    decision.validation_result = "modified"
                    decision.validation_timestamp = datetime.utcnow()
                    db.commit()

            logger.info(
                f"Recorded concept edit feedback: user={username}, doc={document_id}, "
                f"added={len(feedback.context['added'])}, removed={len(feedback.context['removed'])}"
            )

            return feedback.id

    @staticmethod
    async def record_document_delete(
        username: str,
        document_id: int,
        knowledge_base_id: str,
        reason: Optional[str] = None
    ) -> int:
        """
        Record when user deletes a document.

        Could indicate poor quality extraction or irrelevant content.
        """
        with get_db_context() as db:
            feedback = DBUserFeedback(
                feedback_type="document_delete",
                username=username,
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                ai_decision_id=None,
                original_value={},
                new_value={"deleted": True},
                context={"reason": reason},
                user_reasoning=reason,
                processed=False
            )
            db.add(feedback)
            db.commit()
            db.refresh(feedback)

            logger.info(f"Recorded document delete feedback: user={username}, doc={document_id}")

            return feedback.id

    @staticmethod
    async def record_validation(
        username: str,
        ai_decision_id: int,
        accepted: bool,
        user_reasoning: Optional[str] = None
    ) -> int:
        """
        Record when user explicitly validates or rejects an AI decision.

        Used when we proactively ask "Is this correct?"
        """
        with get_db_context() as db:
            decision = db.query(DBAIDecision).filter_by(id=ai_decision_id).first()
            if not decision:
                raise ValueError(f"AI decision {ai_decision_id} not found")

            feedback = DBUserFeedback(
                feedback_type="explicit_validation",
                username=username,
                knowledge_base_id=decision.knowledge_base_id,
                document_id=decision.document_id,
                ai_decision_id=ai_decision_id,
                original_value=decision.output_data,
                new_value={"accepted": accepted},
                context={"confidence": decision.confidence_score},
                user_reasoning=user_reasoning,
                processed=False
            )
            db.add(feedback)

            # Update decision validation status
            decision.validated = True
            decision.validation_result = "accepted" if accepted else "rejected"
            decision.validation_timestamp = datetime.utcnow()

            db.commit()
            db.refresh(feedback)

            logger.info(
                f"Recorded explicit validation: decision={ai_decision_id}, "
                f"accepted={accepted}, confidence={decision.confidence_score:.2f}"
            )

            return feedback.id

    # =============================================================================
    # Learning from Feedback
    # =============================================================================

    @staticmethod
    async def get_user_feedback_patterns(
        username: str,
        feedback_type: Optional[str] = None,
        days: int = 90
    ) -> Dict[str, Any]:
        """
        Analyze user's feedback patterns to learn preferences.

        Returns:
            Dictionary with patterns:
            - Most common corrections
            - Preferred cluster granularity
            - Concept preferences (detailed vs broad)
            - Accuracy by confidence level
        """
        with get_db_context() as db:
            since = datetime.utcnow() - timedelta(days=days)

            # Base query
            query = db.query(DBUserFeedback).filter(
                DBUserFeedback.username == username,
                DBUserFeedback.created_at >= since
            )

            if feedback_type:
                query = query.filter(DBUserFeedback.feedback_type == feedback_type)

            feedbacks = query.all()

            # Analyze patterns
            patterns = {
                "total_feedback": len(feedbacks),
                "feedback_by_type": {},
                "common_corrections": [],
                "average_improvement_score": 0.0
            }

            # Count by type
            for feedback in feedbacks:
                patterns["feedback_by_type"][feedback.feedback_type] = \
                    patterns["feedback_by_type"].get(feedback.feedback_type, 0) + 1

            # Calculate average improvement
            improvements = [f.improvement_score for f in feedbacks if f.improvement_score is not None]
            if improvements:
                patterns["average_improvement_score"] = sum(improvements) / len(improvements)

            logger.info(f"Analyzed feedback patterns for {username}: {patterns['total_feedback']} feedback items")

            return patterns

    @staticmethod
    async def get_decision_accuracy(
        decision_type: str,
        username: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, float]:
        """
        Calculate accuracy of AI decisions by confidence level.

        Returns accuracy metrics:
        - Overall accuracy
        - Accuracy by confidence bucket (low, medium, high)
        - Accuracy trend over time
        """
        with get_db_context() as db:
            since = datetime.utcnow() - timedelta(days=days)

            # Query validated decisions
            query = db.query(DBAIDecision).filter(
                DBAIDecision.decision_type == decision_type,
                DBAIDecision.validated == True,
                DBAIDecision.created_at >= since
            )

            if username:
                query = query.filter(DBAIDecision.username == username)

            decisions = query.all()

            if not decisions:
                return {"accuracy": 0.0, "sample_size": 0}

            # Calculate accuracy
            accepted = sum(1 for d in decisions if d.validation_result == "accepted")
            total = len(decisions)
            overall_accuracy = accepted / total if total > 0 else 0.0

            # Accuracy by confidence level
            low_conf = [d for d in decisions if d.confidence_score < 0.7]
            med_conf = [d for d in decisions if 0.7 <= d.confidence_score < 0.9]
            high_conf = [d for d in decisions if d.confidence_score >= 0.9]

            metrics = {
                "accuracy": overall_accuracy,
                "sample_size": total,
                "low_confidence_accuracy": sum(1 for d in low_conf if d.validation_result == "accepted") / len(low_conf) if low_conf else 0.0,
                "medium_confidence_accuracy": sum(1 for d in med_conf if d.validation_result == "accepted") / len(med_conf) if med_conf else 0.0,
                "high_confidence_accuracy": sum(1 for d in high_conf if d.validation_result == "accepted") / len(high_conf) if high_conf else 0.0,
            }

            logger.info(f"Calculated accuracy for {decision_type}: {overall_accuracy:.2%} ({total} samples)")

            return metrics

    @staticmethod
    async def get_low_confidence_decisions(
        username: str,
        knowledge_base_id: str,
        limit: int = 10
    ) -> List[DBAIDecision]:
        """
        Get recent low-confidence decisions that need validation.

        These should be presented to user for review.
        """
        with get_db_context() as db:
            decisions = db.query(DBAIDecision).filter(
                DBAIDecision.username == username,
                DBAIDecision.knowledge_base_id == knowledge_base_id,
                DBAIDecision.validated == False,
                DBAIDecision.confidence_score < FeedbackService.LOW_CONFIDENCE_THRESHOLD
            ).order_by(DBAIDecision.created_at.desc()).limit(limit).all()

            logger.info(f"Found {len(decisions)} low-confidence decisions for {username}")

            return decisions

    # =============================================================================
    # Analytics
    # =============================================================================

    @staticmethod
    async def get_learning_metrics(username: str) -> Dict[str, Any]:
        """
        Get comprehensive learning metrics for a user.

        Shows how the AI is improving over time.
        """
        with get_db_context() as db:
            # Total decisions made
            total_decisions = db.query(func.count(DBAIDecision.id)).filter(
                DBAIDecision.username == username
            ).scalar() or 0

            # Validated decisions
            validated_decisions = db.query(func.count(DBAIDecision.id)).filter(
                DBAIDecision.username == username,
                DBAIDecision.validated == True
            ).scalar() or 0

            # Acceptance rate
            accepted_decisions = db.query(func.count(DBAIDecision.id)).filter(
                DBAIDecision.username == username,
                DBAIDecision.validated == True,
                DBAIDecision.validation_result == "accepted"
            ).scalar() or 0

            acceptance_rate = accepted_decisions / validated_decisions if validated_decisions > 0 else 0.0

            # Average confidence
            avg_confidence = db.query(func.avg(DBAIDecision.confidence_score)).filter(
                DBAIDecision.username == username
            ).scalar() or 0.0

            # Total feedback
            total_feedback = db.query(func.count(DBUserFeedback.id)).filter(
                DBUserFeedback.username == username
            ).scalar() or 0

            # Unprocessed feedback
            unprocessed_feedback = db.query(func.count(DBUserFeedback.id)).filter(
                DBUserFeedback.username == username,
                DBUserFeedback.processed == False
            ).scalar() or 0

            metrics = {
                "total_decisions": total_decisions,
                "validated_decisions": validated_decisions,
                "acceptance_rate": acceptance_rate,
                "average_confidence": float(avg_confidence),
                "total_feedback": total_feedback,
                "unprocessed_feedback": unprocessed_feedback,
                "improvement_potential": unprocessed_feedback / total_feedback if total_feedback > 0 else 0.0
            }

            logger.info(f"Learning metrics for {username}: acceptance_rate={acceptance_rate:.2%}, avg_confidence={avg_confidence:.2f}")

            return metrics


# Global instance
feedback_service = FeedbackService()
