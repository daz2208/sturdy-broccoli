"""
True Agentic Learning Engine for SyncBoard 3.0.

This module provides REAL learning from user corrections, not just prompt injection.

Key capabilities:
1. Rule Extraction: Analyze corrections to create deterministic rules
2. Concept Vocabulary: Learn user's preferred terminology
3. Confidence Calibration: Adjust thresholds based on acceptance rates
4. Rule Application: Apply learned rules during extraction (pre/post processing)

Unlike prompt-based "learning" (few-shot examples), this system:
- Persists learned knowledge in the database
- Applies rules deterministically (not probabilistically via LLM)
- Scales to unlimited rules (vs ~5 examples in prompts)
- Improves consistently over time
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter, defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from .db_models import (
    DBLearnedRule,
    DBConceptVocabulary,
    DBUserLearningProfile,
    DBUserFeedback,
    DBAIDecision
)
from .database import get_db_context

logger = logging.getLogger(__name__)


class LearningEngine:
    """
    True agentic learning engine that extracts and applies rules from user feedback.
    """

    # ==========================================================================
    # Rule Extraction from Corrections
    # ==========================================================================

    @staticmethod
    async def extract_rules_from_feedback(
        username: str,
        days: int = 90,
        min_occurrences: int = 2
    ) -> Dict[str, Any]:
        """
        Analyze user feedback and extract deterministic rules.

        This is the LEARNING step - runs periodically or on-demand.

        Args:
            username: User whose feedback to analyze
            days: Look back period
            min_occurrences: Minimum times a pattern must appear to become a rule

        Returns:
            Summary of extracted rules
        """
        with get_db_context() as db:
            since = datetime.utcnow() - timedelta(days=days)

            # Get unprocessed feedback
            feedbacks = db.query(DBUserFeedback).filter(
                DBUserFeedback.username == username,
                DBUserFeedback.created_at >= since,
                DBUserFeedback.processed == False
            ).all()

            if not feedbacks:
                logger.info(f"No unprocessed feedback for {username}")
                return {"rules_created": 0, "vocabulary_updated": 0}

            # Analyze patterns
            concept_renames = defaultdict(list)  # {old_concept: [new_concept, ...]}
            concept_removals = Counter()  # {concept: count}
            concept_additions = Counter()  # {concept: count}

            for fb in feedbacks:
                if fb.feedback_type == "concept_edit":
                    old_concepts = set(
                        c.get("name", c) if isinstance(c, dict) else c
                        for c in (fb.original_value or {}).get("concepts", [])
                    )
                    new_concepts = set(
                        c.get("name", c) if isinstance(c, dict) else c
                        for c in (fb.new_value or {}).get("concepts", [])
                    )

                    # Removed concepts
                    for removed in old_concepts - new_concepts:
                        concept_removals[removed.lower()] += 1

                    # Added concepts
                    for added in new_concepts - old_concepts:
                        concept_additions[added.lower()] += 1

                    # Renames: concepts that were replaced with similar ones
                    for old in old_concepts - new_concepts:
                        for new in new_concepts - old_concepts:
                            # Heuristic: if old and new share words, it's a rename
                            old_words = set(old.lower().split())
                            new_words = set(new.lower().split())
                            if old_words & new_words:
                                concept_renames[old.lower()].append(new.lower())

            rules_created = 0
            vocabulary_updated = 0

            # Create REJECT rules for frequently removed concepts
            for concept, count in concept_removals.items():
                if count >= min_occurrences:
                    existing = db.query(DBLearnedRule).filter_by(
                        username=username,
                        rule_type="concept_reject",
                        active=True
                    ).filter(
                        DBLearnedRule.condition.contains({"concept_matches": concept})
                    ).first()

                    if not existing:
                        rule = DBLearnedRule(
                            username=username,
                            rule_type="concept_reject",
                            condition={"concept_matches": concept},
                            action={"reject": True},
                            confidence=min(0.9, 0.5 + count * 0.1),
                            source_feedback_ids=[fb.id for fb in feedbacks if concept in str(fb.original_value).lower()]
                        )
                        db.add(rule)
                        rules_created += 1
                        logger.info(f"Created REJECT rule for '{concept}' (seen {count} times)")

            # Create RENAME rules for consistent replacements
            for old_concept, new_concepts in concept_renames.items():
                if len(new_concepts) >= min_occurrences:
                    # Find most common replacement
                    most_common = Counter(new_concepts).most_common(1)
                    if most_common:
                        new_concept = most_common[0][0]
                        count = most_common[0][1]

                        existing = db.query(DBLearnedRule).filter_by(
                            username=username,
                            rule_type="concept_rename",
                            active=True
                        ).filter(
                            DBLearnedRule.condition.contains({"concept_matches": old_concept})
                        ).first()

                        if not existing:
                            rule = DBLearnedRule(
                                username=username,
                                rule_type="concept_rename",
                                condition={"concept_matches": old_concept},
                                action={"rename_to": new_concept},
                                confidence=min(0.9, 0.5 + count * 0.1)
                            )
                            db.add(rule)
                            rules_created += 1
                            logger.info(f"Created RENAME rule: '{old_concept}' → '{new_concept}'")

                        # Also update vocabulary
                        vocabulary_updated += await LearningEngine._update_vocabulary(
                            db, username, new_concept, [old_concept]
                        )

            # Mark feedback as processed
            for fb in feedbacks:
                fb.processed = True
                fb.processed_at = datetime.utcnow()

            # Update learning profile
            profile = db.query(DBUserLearningProfile).filter_by(username=username).first()
            if not profile:
                profile = DBUserLearningProfile(username=username)
                db.add(profile)

            profile.rules_generated = db.query(DBLearnedRule).filter_by(
                username=username, active=True
            ).count()
            profile.vocabulary_size = db.query(DBConceptVocabulary).filter_by(
                username=username
            ).count()
            profile.last_learning_run = datetime.utcnow()

            db.commit()

            logger.info(
                f"Learning complete for {username}: "
                f"{rules_created} rules created, {vocabulary_updated} vocabulary updates"
            )

            return {
                "rules_created": rules_created,
                "vocabulary_updated": vocabulary_updated,
                "feedback_processed": len(feedbacks)
            }

    @staticmethod
    async def _update_vocabulary(
        db: Session,
        username: str,
        canonical: str,
        variants: List[str]
    ) -> int:
        """Update or create vocabulary entry."""
        existing = db.query(DBConceptVocabulary).filter_by(
            username=username,
            canonical_name=canonical.lower()
        ).first()

        if existing:
            current_variants = set(existing.variants or [])
            new_variants = current_variants | set(v.lower() for v in variants)
            existing.variants = list(new_variants)
            return 0
        else:
            vocab = DBConceptVocabulary(
                username=username,
                canonical_name=canonical.lower(),
                variants=[v.lower() for v in variants]
            )
            db.add(vocab)
            return 1

    # ==========================================================================
    # Confidence Calibration
    # ==========================================================================

    @staticmethod
    async def calibrate_confidence_thresholds(username: str) -> Dict[str, float]:
        """
        Calibrate confidence thresholds based on historical accuracy.

        If user accepts 90% of decisions at 0.7 confidence, we can lower threshold.
        If user rejects 50% of decisions at 0.8 confidence, we should raise threshold.

        Returns:
            New calibrated thresholds
        """
        with get_db_context() as db:
            # Get accuracy at different confidence levels
            decisions = db.query(DBAIDecision).filter(
                DBAIDecision.username == username,
                DBAIDecision.validated == True
            ).all()

            if len(decisions) < 10:
                logger.info(f"Not enough validated decisions for {username} to calibrate")
                return {}

            # Bucket by confidence
            buckets = defaultdict(lambda: {"total": 0, "accepted": 0})
            for d in decisions:
                bucket = int(d.confidence_score * 10) / 10  # 0.0, 0.1, ..., 0.9
                buckets[bucket]["total"] += 1
                if d.validation_result == "accepted":
                    buckets[bucket]["accepted"] += 1

            # Find optimal threshold (where acceptance rate > 80%)
            optimal_threshold = 0.7  # Default
            for threshold in sorted(buckets.keys()):
                stats = buckets[threshold]
                if stats["total"] > 0:
                    acceptance_rate = stats["accepted"] / stats["total"]
                    if acceptance_rate >= 0.8:
                        optimal_threshold = threshold
                        break

            # Update profile
            profile = db.query(DBUserLearningProfile).filter_by(username=username).first()
            if not profile:
                profile = DBUserLearningProfile(username=username)
                db.add(profile)

            old_threshold = profile.concept_confidence_threshold
            profile.concept_confidence_threshold = optimal_threshold

            # Update accuracy stats
            total = len(decisions)
            accepted = sum(1 for d in decisions if d.validation_result == "accepted")
            profile.total_decisions = total
            profile.decisions_accepted = accepted
            profile.accuracy_rate = accepted / total if total > 0 else 0

            db.commit()

            logger.info(
                f"Calibrated thresholds for {username}: "
                f"{old_threshold:.2f} → {optimal_threshold:.2f} "
                f"(accuracy: {profile.accuracy_rate:.1%})"
            )

            return {
                "concept_threshold": optimal_threshold,
                "old_threshold": old_threshold,
                "accuracy_rate": profile.accuracy_rate
            }

    # ==========================================================================
    # Rule Application (Used during extraction)
    # ==========================================================================

    @staticmethod
    def apply_learned_rules(
        username: str,
        concepts: List[Dict[str, Any]],
        content_sample: str = None
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Apply learned rules to extracted concepts.

        This is DETERMINISTIC post-processing, not LLM-based.
        Called after AI extraction, before returning results.

        Args:
            username: User whose rules to apply
            concepts: List of extracted concepts [{"name": "...", "confidence": 0.8}, ...]
            content_sample: Original content (for context-based rules)

        Returns:
            Tuple of (modified_concepts, applied_rules_log)
        """
        with get_db_context() as db:
            # Load active rules
            rules = db.query(DBLearnedRule).filter_by(
                username=username,
                active=True
            ).order_by(DBLearnedRule.confidence.desc()).all()

            # Load vocabulary
            vocab = db.query(DBConceptVocabulary).filter_by(
                username=username
            ).all()

            # Build vocabulary lookup
            vocab_map = {}  # variant -> canonical
            for v in vocab:
                for variant in v.variants:
                    vocab_map[variant.lower()] = v.canonical_name

            applied_log = []
            modified_concepts = []

            for concept in concepts:
                name = concept.get("name", "")
                name_lower = name.lower()
                confidence = concept.get("confidence", 0.5)
                should_include = True
                final_name = name

                # Apply vocabulary normalization
                if name_lower in vocab_map:
                    old_name = name
                    final_name = vocab_map[name_lower]
                    applied_log.append(f"VOCAB: '{old_name}' → '{final_name}'")

                # Apply rules
                for rule in rules:
                    condition = rule.condition or {}
                    action = rule.action or {}

                    # Check if rule applies
                    matches = False
                    if "concept_matches" in condition:
                        pattern = condition["concept_matches"]
                        if pattern.endswith("*"):
                            matches = name_lower.startswith(pattern[:-1])
                        else:
                            matches = name_lower == pattern.lower()

                    if matches:
                        # Apply action
                        if rule.rule_type == "concept_reject" and action.get("reject"):
                            should_include = False
                            applied_log.append(f"REJECT: '{name}' (rule #{rule.id})")
                            # Update rule stats
                            rule.times_applied += 1
                            break

                        elif rule.rule_type == "concept_rename" and "rename_to" in action:
                            old_name = final_name
                            final_name = action["rename_to"]
                            applied_log.append(f"RENAME: '{old_name}' → '{final_name}' (rule #{rule.id})")
                            rule.times_applied += 1

                        elif rule.rule_type == "confidence_adjust" and "adjust_confidence" in action:
                            old_conf = confidence
                            confidence = max(0, min(1, confidence + action["adjust_confidence"]))
                            applied_log.append(f"CONFIDENCE: {old_conf:.2f} → {confidence:.2f}")
                            rule.times_applied += 1

                if should_include:
                    modified_concepts.append({
                        **concept,
                        "name": final_name,
                        "confidence": confidence
                    })

            db.commit()

            if applied_log:
                logger.info(f"Applied {len(applied_log)} rules for {username}")

            return modified_concepts, applied_log

    @staticmethod
    def get_user_learning_profile(username: str) -> Optional[Dict[str, Any]]:
        """Get user's learning profile with calibrated thresholds."""
        with get_db_context() as db:
            profile = db.query(DBUserLearningProfile).filter_by(username=username).first()

            if not profile:
                return None

            return {
                "concept_confidence_threshold": profile.concept_confidence_threshold,
                "cluster_confidence_threshold": profile.cluster_confidence_threshold,
                "prefers_specific_concepts": profile.prefers_specific_concepts,
                "prefers_fewer_concepts": profile.prefers_fewer_concepts,
                "avg_concepts_per_doc": profile.avg_concepts_per_doc,
                "accuracy_rate": profile.accuracy_rate,
                "rules_generated": profile.rules_generated,
                "vocabulary_size": profile.vocabulary_size,
                "last_learning_run": profile.last_learning_run.isoformat() if profile.last_learning_run else None
            }

    # ==========================================================================
    # Learning Status and Metrics
    # ==========================================================================

    @staticmethod
    async def get_learning_status(username: str) -> Dict[str, Any]:
        """Get comprehensive learning status for a user."""
        with get_db_context() as db:
            profile = db.query(DBUserLearningProfile).filter_by(username=username).first()

            rules = db.query(DBLearnedRule).filter_by(username=username, active=True).all()
            vocab = db.query(DBConceptVocabulary).filter_by(username=username).all()

            unprocessed = db.query(DBUserFeedback).filter_by(
                username=username,
                processed=False
            ).count()

            return {
                "has_learning_data": profile is not None,
                "profile": {
                    "accuracy_rate": profile.accuracy_rate if profile else 0,
                    "total_decisions": profile.total_decisions if profile else 0,
                    "concept_threshold": profile.concept_confidence_threshold if profile else 0.7,
                    "last_learning_run": profile.last_learning_run.isoformat() if profile and profile.last_learning_run else None
                },
                "rules": {
                    "total": len(rules),
                    "by_type": Counter(r.rule_type for r in rules),
                    "top_rules": [
                        {
                            "type": r.rule_type,
                            "condition": r.condition,
                            "action": r.action,
                            "times_applied": r.times_applied
                        }
                        for r in sorted(rules, key=lambda x: x.times_applied, reverse=True)[:5]
                    ]
                },
                "vocabulary": {
                    "total": len(vocab),
                    "top_terms": [
                        {"canonical": v.canonical_name, "variants": len(v.variants)}
                        for v in sorted(vocab, key=lambda x: len(x.variants), reverse=True)[:5]
                    ]
                },
                "pending_feedback": unprocessed
            }


# Global instance
learning_engine = LearningEngine()
