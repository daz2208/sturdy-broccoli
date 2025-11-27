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

# Import vector store for semantic similarity search
# This is lazy-imported to avoid circular dependencies
_vector_store = None

def _get_vector_store():
    """Lazy-load vector store to avoid circular imports."""
    global _vector_store
    if _vector_store is None:
        from .dependencies import get_vector_store
        _vector_store = get_vector_store()
    return _vector_store


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
    ) -> List[Dict]:
        """
        Get recent low-confidence decisions that need validation.

        These should be presented to user for review.

        Returns dictionaries instead of ORM objects to avoid session detachment issues.
        """
        with get_db_context() as db:
            decisions = db.query(DBAIDecision).filter(
                DBAIDecision.username == username,
                DBAIDecision.knowledge_base_id == knowledge_base_id,
                DBAIDecision.validated == False,
                DBAIDecision.confidence_score < FeedbackService.LOW_CONFIDENCE_THRESHOLD
            ).order_by(DBAIDecision.created_at.desc()).limit(limit).all()

            logger.info(f"Found {len(decisions)} low-confidence decisions for {username}")

            # Convert to dictionaries while session is active to avoid DetachedInstanceError
            result = []
            for decision in decisions:
                result.append({
                    "id": decision.id,
                    "decision_type": decision.decision_type,
                    "output_data": decision.output_data,
                    "input_data": decision.input_data,
                    "confidence_score": decision.confidence_score,
                    "document_id": decision.document_id,
                    "cluster_id": decision.cluster_id,
                    "created_at": decision.created_at.isoformat() if decision.created_at else None,
                    "validated": decision.validated,
                    "username": decision.username,
                    "knowledge_base_id": decision.knowledge_base_id
                })

            return result

    # =============================================================================
    # LEARNING LOOP: Feedback Retrieval for Extraction
    # These methods CLOSE THE LOOP by feeding past corrections back into extraction
    # =============================================================================

    @staticmethod
    async def get_recent_corrections(
        username: str,
        decision_type: str = "concept_extraction",
        limit: int = 10,
        days: int = 90
    ) -> List[Dict[str, Any]]:
        """
        Get user's recent corrections for a specific decision type.

        THIS IS THE KEY METHOD THAT CLOSES THE LEARNING LOOP.
        These corrections become few-shot examples in future extraction prompts.

        Args:
            username: User whose corrections to fetch
            decision_type: Type of AI decision (concept_extraction, clustering, etc.)
            limit: Max corrections to return
            days: How far back to look

        Returns:
            List of correction dictionaries with:
            - original_value: What AI extracted
            - new_value: What user corrected it to
            - user_reasoning: Why user made the change
            - context: Additional context (added/removed concepts)
            - confidence_at_decision: How confident AI was when it made the mistake
        """
        with get_db_context() as db:
            since = datetime.utcnow() - timedelta(days=days)

            # Get feedback where user made actual corrections (not just acceptances)
            # Join with ai_decisions to get the decision context
            feedbacks = db.query(DBUserFeedback).join(
                DBAIDecision,
                DBUserFeedback.ai_decision_id == DBAIDecision.id,
                isouter=True
            ).filter(
                DBUserFeedback.username == username,
                DBUserFeedback.created_at >= since,
                DBUserFeedback.feedback_type.in_(["concept_edit", "explicit_validation"]),
                # Only get corrections, not acceptances
                or_(
                    DBUserFeedback.feedback_type == "concept_edit",
                    and_(
                        DBUserFeedback.feedback_type == "explicit_validation",
                        DBUserFeedback.new_value.op('->>')('accepted') == 'false'
                    )
                )
            ).order_by(DBUserFeedback.created_at.desc()).limit(limit).all()

            corrections = []
            for feedback in feedbacks:
                correction = {
                    "original_value": feedback.original_value,
                    "new_value": feedback.new_value,
                    "user_reasoning": feedback.user_reasoning,
                    "context": feedback.context or {},
                    "feedback_type": feedback.feedback_type,
                    "created_at": feedback.created_at.isoformat() if feedback.created_at else None
                }

                # Get confidence from linked decision if available
                if feedback.ai_decision_id:
                    decision = db.query(DBAIDecision).filter_by(id=feedback.ai_decision_id).first()
                    if decision:
                        correction["confidence_at_decision"] = decision.confidence_score
                        correction["decision_type"] = decision.decision_type

                corrections.append(correction)

            logger.info(
                f"Retrieved {len(corrections)} corrections for {username} "
                f"(type={decision_type}, last {days} days)"
            )

            return corrections

    @staticmethod
    async def get_similar_document_corrections(
        username: str,
        content_sample: str,
        decision_type: str = "concept_extraction",
        limit: int = 5,
        similarity_threshold: float = 0.3,
        days: int = 180
    ) -> List[Dict[str, Any]]:
        """
        Find corrections from documents semantically similar to the given content.

        THIS METHOD CLOSES THE SEMANTIC LEARNING LOOP.
        Instead of just using recent corrections (by time), this finds corrections
        from documents with SIMILAR CONTENT, making the learning more contextually relevant.

        For example: corrections made on Docker documentation will apply more
        strongly when processing new Docker-related content.

        Args:
            username: User whose corrections to search
            content_sample: Sample of content being processed (for similarity matching)
            decision_type: Type of AI decision
            limit: Max corrections to return
            similarity_threshold: Minimum similarity score (0.0-1.0) for relevance
            days: How far back to look for corrections

        Returns:
            List of correction dictionaries with similarity scores, sorted by relevance
        """
        if not content_sample or len(content_sample.strip()) < 20:
            logger.debug("Content sample too short for semantic similarity search")
            return []

        try:
            vector_store = _get_vector_store()
        except Exception as e:
            logger.warning(f"Vector store not available for semantic search: {e}")
            return []

        # Search for similar documents using the vector store
        similar_docs = vector_store.search(
            query=content_sample[:2000],  # Limit query length for efficiency
            top_k=20  # Get more candidates, will filter by corrections
        )

        if not similar_docs:
            logger.debug("No similar documents found in vector store")
            return []

        # Extract document IDs that have high enough similarity
        similar_doc_ids = [
            doc_id for doc_id, score, _ in similar_docs
            if score >= similarity_threshold
        ]

        if not similar_doc_ids:
            logger.debug(f"No documents above similarity threshold {similarity_threshold}")
            return []

        logger.debug(f"Found {len(similar_doc_ids)} similar documents above threshold")

        # Query corrections for these similar documents
        with get_db_context() as db:
            since = datetime.utcnow() - timedelta(days=days)

            # Get feedback records associated with similar documents
            feedbacks = db.query(DBUserFeedback).join(
                DBAIDecision,
                DBUserFeedback.ai_decision_id == DBAIDecision.id,
                isouter=True
            ).filter(
                DBUserFeedback.username == username,
                DBUserFeedback.created_at >= since,
                DBUserFeedback.feedback_type.in_(["concept_edit", "explicit_validation"]),
                DBUserFeedback.document_id.in_(similar_doc_ids),
                # Only get corrections, not acceptances
                or_(
                    DBUserFeedback.feedback_type == "concept_edit",
                    and_(
                        DBUserFeedback.feedback_type == "explicit_validation",
                        DBUserFeedback.new_value.op('->>')('accepted') == 'false'
                    )
                )
            ).all()

            if not feedbacks:
                logger.debug("No corrections found for similar documents")
                return []

            # Build corrections list with similarity scores
            corrections = []
            similarity_map = {doc_id: score for doc_id, score, _ in similar_docs}

            for feedback in feedbacks:
                similarity_score = similarity_map.get(feedback.document_id, 0.0)

                correction = {
                    "original_value": feedback.original_value,
                    "new_value": feedback.new_value,
                    "user_reasoning": feedback.user_reasoning,
                    "context": feedback.context or {},
                    "feedback_type": feedback.feedback_type,
                    "document_id": feedback.document_id,
                    "similarity_score": similarity_score,
                    "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
                    "source": "semantic_similarity"  # Mark the source for debugging
                }

                # Get confidence from linked decision if available
                if feedback.ai_decision_id:
                    decision = db.query(DBAIDecision).filter_by(id=feedback.ai_decision_id).first()
                    if decision:
                        correction["confidence_at_decision"] = decision.confidence_score
                        correction["decision_type"] = decision.decision_type

                corrections.append(correction)

            # Sort by similarity score (most similar documents first)
            corrections.sort(key=lambda x: x["similarity_score"], reverse=True)
            corrections = corrections[:limit]

            logger.info(
                f"Retrieved {len(corrections)} corrections from similar documents for {username} "
                f"(similarity threshold={similarity_threshold}, decision_type={decision_type})"
            )

            return corrections

    @staticmethod
    async def get_concept_correction_patterns(
        username: str,
        days: int = 90
    ) -> Dict[str, Any]:
        """
        Analyze patterns in concept corrections to learn user preferences.

        Returns actionable insights like:
        - Concepts user frequently removes (too vague/wrong)
        - Concepts user frequently adds (AI keeps missing)
        - Whether user prefers specific or generic terms
        - Average number of concepts per document user prefers

        Args:
            username: User to analyze
            days: How far back to look

        Returns:
            Dictionary with actionable preference patterns
        """
        with get_db_context() as db:
            since = datetime.utcnow() - timedelta(days=days)

            # Get concept edit feedback
            feedbacks = db.query(DBUserFeedback).filter(
                DBUserFeedback.username == username,
                DBUserFeedback.created_at >= since,
                DBUserFeedback.feedback_type == "concept_edit"
            ).all()

            if not feedbacks:
                return {
                    "has_feedback": False,
                    "total_corrections": 0,
                    "frequently_removed": [],
                    "frequently_added": [],
                    "prefers_specific_names": None,
                    "avg_concepts_preferred": None,
                    "removal_patterns": [],
                    "addition_patterns": []
                }

            # Aggregate removed and added concepts
            removed_concepts = {}
            added_concepts = {}
            original_counts = []
            corrected_counts = []

            for feedback in feedbacks:
                context = feedback.context or {}

                # Track removed concepts
                for concept in context.get("removed", []):
                    concept_lower = concept.lower()
                    removed_concepts[concept_lower] = removed_concepts.get(concept_lower, 0) + 1

                # Track added concepts
                for concept in context.get("added", []):
                    concept_lower = concept.lower()
                    added_concepts[concept_lower] = added_concepts.get(concept_lower, 0) + 1

                # Track concept counts
                original = feedback.original_value or {}
                new = feedback.new_value or {}
                if "concepts" in original:
                    original_counts.append(len(original["concepts"]))
                if "concepts" in new:
                    corrected_counts.append(len(new["concepts"]))

            # Sort by frequency
            frequently_removed = sorted(
                removed_concepts.items(), key=lambda x: x[1], reverse=True
            )[:10]
            frequently_added = sorted(
                added_concepts.items(), key=lambda x: x[1], reverse=True
            )[:10]

            # Determine if user prefers specific names
            # Heuristic: if added concepts are longer on average than removed, user prefers specific
            avg_removed_len = sum(len(c) for c, _ in frequently_removed) / len(frequently_removed) if frequently_removed else 0
            avg_added_len = sum(len(c) for c, _ in frequently_added) / len(frequently_added) if frequently_added else 0
            prefers_specific = avg_added_len > avg_removed_len + 2 if frequently_added and frequently_removed else None

            # Calculate average preferred concept count
            avg_preferred = sum(corrected_counts) / len(corrected_counts) if corrected_counts else None

            patterns = {
                "has_feedback": True,
                "total_corrections": len(feedbacks),
                "frequently_removed": [{"concept": c, "count": n} for c, n in frequently_removed],
                "frequently_added": [{"concept": c, "count": n} for c, n in frequently_added],
                "prefers_specific_names": prefers_specific,
                "avg_concepts_preferred": avg_preferred,
                "removal_patterns": FeedbackService._extract_removal_patterns(frequently_removed),
                "addition_patterns": FeedbackService._extract_addition_patterns(frequently_added)
            }

            logger.info(
                f"Analyzed concept patterns for {username}: "
                f"{len(feedbacks)} corrections, prefers_specific={prefers_specific}"
            )

            return patterns

    @staticmethod
    def _extract_removal_patterns(frequently_removed: List[Tuple[str, int]]) -> List[str]:
        """Extract human-readable patterns from removed concepts."""
        patterns = []

        vague_terms = ["web", "api", "data", "code", "app", "system", "service", "tool"]
        removed_names = [c.lower() for c, _ in frequently_removed]

        vague_removed = [c for c in removed_names if c in vague_terms]
        if vague_removed:
            patterns.append(f"User removes vague terms like: {', '.join(vague_removed)}")

        return patterns

    @staticmethod
    def _extract_addition_patterns(frequently_added: List[Tuple[str, int]]) -> List[str]:
        """Extract human-readable patterns from added concepts."""
        patterns = []

        # Check for specific technology names
        added_names = [c for c, _ in frequently_added]
        if any(len(c) > 10 for c in added_names):
            patterns.append("User prefers specific technology names over generic terms")

        return patterns

    @staticmethod
    async def get_accuracy_for_confidence_range(
        username: str,
        confidence_min: float,
        confidence_max: float,
        decision_type: str = "concept_extraction",
        days: int = 90
    ) -> Dict[str, Any]:
        """
        Get historical accuracy for a specific confidence range.

        Used for CONFIDENCE CALIBRATION - adjusting displayed confidence
        based on actual track record at that confidence level.

        Args:
            username: User to analyze
            confidence_min: Lower bound of confidence range
            confidence_max: Upper bound of confidence range
            decision_type: Type of decision
            days: How far back to look

        Returns:
            Accuracy metrics for that confidence range
        """
        with get_db_context() as db:
            since = datetime.utcnow() - timedelta(days=days)

            # Get validated decisions in this confidence range
            decisions = db.query(DBAIDecision).filter(
                DBAIDecision.username == username,
                DBAIDecision.decision_type == decision_type,
                DBAIDecision.validated == True,
                DBAIDecision.confidence_score >= confidence_min,
                DBAIDecision.confidence_score < confidence_max,
                DBAIDecision.created_at >= since
            ).all()

            if not decisions:
                return {
                    "confidence_range": f"{confidence_min:.0%}-{confidence_max:.0%}",
                    "sample_size": 0,
                    "actual_accuracy": None,
                    "calibration_needed": False
                }

            # Calculate actual accuracy
            accepted = sum(1 for d in decisions if d.validation_result == "accepted")
            total = len(decisions)
            actual_accuracy = accepted / total

            # Calculate average stated confidence
            avg_stated_confidence = sum(d.confidence_score for d in decisions) / total

            # Determine if calibration is needed
            # If actual accuracy differs significantly from stated confidence, calibrate
            calibration_delta = actual_accuracy - avg_stated_confidence
            calibration_needed = abs(calibration_delta) > 0.1  # More than 10% off

            result = {
                "confidence_range": f"{confidence_min:.0%}-{confidence_max:.0%}",
                "sample_size": total,
                "actual_accuracy": actual_accuracy,
                "avg_stated_confidence": avg_stated_confidence,
                "calibration_delta": calibration_delta,
                "calibration_needed": calibration_needed,
                "suggested_adjustment": calibration_delta if calibration_needed else 0.0
            }

            logger.info(
                f"Accuracy for {username} at {confidence_min:.0%}-{confidence_max:.0%}: "
                f"{actual_accuracy:.1%} actual vs {avg_stated_confidence:.1%} stated "
                f"(delta={calibration_delta:+.1%})"
            )

            return result

    @staticmethod
    async def get_learning_context_for_extraction(
        username: str,
        content_sample: str = "",
        decision_type: str = "concept_extraction",
        max_corrections: int = 5
    ) -> Dict[str, Any]:
        """
        Get complete learning context for a new extraction.

        THIS IS THE MAIN ENTRY POINT FOR THE LEARNING LOOP.
        Call this before extraction to get all relevant learning context.

        Now includes SEMANTIC SIMILARITY SEARCH - corrections from documents
        with similar content are prioritized over just recent corrections.

        Args:
            username: User making the extraction
            content_sample: Sample of content being extracted (for similarity matching)
            decision_type: Type of decision
            max_corrections: Max number of past corrections to include

        Returns:
            Complete learning context including:
            - recent_corrections: Few-shot examples from past mistakes (by time)
            - similar_corrections: Few-shot examples from similar documents (by content)
            - user_preferences: Learned user preferences
            - confidence_calibration: How to adjust confidence based on history
            - prompt_additions: Ready-to-use prompt text
        """
        # Gather all learning context
        # 1. Recent corrections (by time) - fallback when no similar content exists
        recent_corrections = await FeedbackService.get_recent_corrections(
            username=username,
            decision_type=decision_type,
            limit=max_corrections
        )

        # 2. Similar document corrections (by content) - PRIORITIZED
        # These are more relevant because they come from similar documents
        similar_corrections = []
        if content_sample and len(content_sample.strip()) >= 20:
            similar_corrections = await FeedbackService.get_similar_document_corrections(
                username=username,
                content_sample=content_sample,
                decision_type=decision_type,
                limit=max_corrections,
                similarity_threshold=0.3
            )

        # 3. User preference patterns
        patterns = await FeedbackService.get_concept_correction_patterns(
            username=username
        )

        # Get calibration data for different confidence ranges
        calibration_low = await FeedbackService.get_accuracy_for_confidence_range(
            username=username,
            confidence_min=0.0,
            confidence_max=0.7,
            decision_type=decision_type
        )
        calibration_med = await FeedbackService.get_accuracy_for_confidence_range(
            username=username,
            confidence_min=0.7,
            confidence_max=0.9,
            decision_type=decision_type
        )
        calibration_high = await FeedbackService.get_accuracy_for_confidence_range(
            username=username,
            confidence_min=0.9,
            confidence_max=1.0,
            decision_type=decision_type
        )

        # Combine corrections: prioritize similar docs, then fall back to recent
        # Deduplicate by document_id to avoid showing same correction twice
        combined_corrections = []
        seen_doc_ids = set()

        # First add similar corrections (higher priority)
        for correction in similar_corrections:
            doc_id = correction.get("document_id")
            if doc_id and doc_id not in seen_doc_ids:
                seen_doc_ids.add(doc_id)
                combined_corrections.append(correction)

        # Then add recent corrections (fill remaining slots)
        for correction in recent_corrections:
            doc_id = correction.get("document_id")
            if doc_id not in seen_doc_ids:
                seen_doc_ids.add(doc_id)
                # Mark as recent (no similarity score)
                correction["source"] = "recent"
                combined_corrections.append(correction)

        # Limit to max_corrections
        combined_corrections = combined_corrections[:max_corrections]

        # Build prompt additions from learning context
        prompt_additions = FeedbackService._build_prompt_additions(
            corrections=combined_corrections,
            patterns=patterns,
            has_similar=len(similar_corrections) > 0
        )

        context = {
            "has_learning_data": len(combined_corrections) > 0 or patterns.get("has_feedback", False),
            "recent_corrections": recent_corrections,
            "similar_corrections": similar_corrections,
            "combined_corrections": combined_corrections,
            "user_preferences": patterns,
            "confidence_calibration": {
                "low": calibration_low,
                "medium": calibration_med,
                "high": calibration_high
            },
            "prompt_additions": prompt_additions
        }

        logger.info(
            f"Built learning context for {username}: "
            f"{len(recent_corrections)} recent, {len(similar_corrections)} similar corrections, "
            f"has_patterns={patterns.get('has_feedback', False)}"
        )

        return context

    @staticmethod
    def _build_prompt_additions(
        corrections: List[Dict[str, Any]],
        patterns: Dict[str, Any],
        has_similar: bool = False
    ) -> str:
        """
        Build prompt text from learning context.

        This text gets injected into extraction prompts to apply past learning.
        Now includes semantic similarity awareness - corrections from similar
        documents are marked as HIGHLY RELEVANT.

        Args:
            corrections: List of correction dictionaries
            patterns: User preference patterns
            has_similar: Whether any corrections are from semantically similar documents
        """
        additions = []

        # Add user preference guidance
        if patterns.get("has_feedback"):
            if patterns.get("prefers_specific_names") is True:
                additions.append(
                    "IMPORTANT: This user prefers SPECIFIC, detailed concept names. "
                    "Avoid generic terms like 'API', 'Web', 'Data'. "
                    "Use precise names like 'REST API', 'WebSocket', 'PostgreSQL'."
                )
            elif patterns.get("prefers_specific_names") is False:
                additions.append(
                    "Note: This user prefers broader, more general concept categories."
                )

            # Add frequently removed concepts as negative examples
            frequently_removed = patterns.get("frequently_removed", [])
            if frequently_removed:
                removed_names = [item["concept"] for item in frequently_removed[:5]]
                additions.append(
                    f"AVOID these concepts (user has repeatedly removed them): {', '.join(removed_names)}"
                )

            # Add average concept count preference
            avg_concepts = patterns.get("avg_concepts_preferred")
            if avg_concepts:
                additions.append(
                    f"Target approximately {int(avg_concepts)} concepts per document."
                )

        # Add few-shot examples from corrections
        if corrections:
            if has_similar:
                additions.append(
                    "\n--- LEARN FROM CORRECTIONS ON SIMILAR DOCUMENTS ---"
                )
                additions.append(
                    "These corrections are from documents with SIMILAR CONTENT to what you're analyzing."
                )
                additions.append(
                    "PAY CLOSE ATTENTION - these are highly relevant to the current task."
                )
            else:
                additions.append("\n--- LEARN FROM PAST CORRECTIONS ---")

            for i, correction in enumerate(corrections[:3], 1):
                original = correction.get("original_value", {})
                new = correction.get("new_value", {})
                reasoning = correction.get("user_reasoning", "")
                source = correction.get("source", "unknown")
                similarity_score = correction.get("similarity_score")

                if "concepts" in original and "concepts" in new:
                    orig_concepts = original.get("concepts", [])
                    new_concepts = new.get("concepts", [])

                    # Handle both list of strings and list of dicts
                    if orig_concepts and isinstance(orig_concepts[0], dict):
                        orig_names = [c.get("name", str(c)) for c in orig_concepts]
                    else:
                        orig_names = orig_concepts

                    if new_concepts and isinstance(new_concepts[0], dict):
                        new_names = [c.get("name", str(c)) for c in new_concepts]
                    else:
                        new_names = new_concepts

                    # Mark similar document corrections as more important
                    if source == "semantic_similarity" and similarity_score:
                        additions.append(
                            f"Example {i} [HIGHLY RELEVANT - {similarity_score:.0%} similar document]:"
                        )
                    else:
                        additions.append(f"Example {i}:")

                    additions.append(f"  AI extracted: {', '.join(orig_names[:5])}")
                    additions.append(f"  User corrected to: {', '.join(new_names[:5])}")
                    if reasoning:
                        additions.append(f"  User's reason: \"{reasoning}\"")

            additions.append("--- END CORRECTIONS ---\n")

        return "\n".join(additions) if additions else ""

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
