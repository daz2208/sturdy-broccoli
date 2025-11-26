"""
Autonomous Learning Agent for SyncBoard 3.0 - TRUE Agentic Learning.

This agent ACTS AUTONOMOUSLY without human intervention:
1. Observes extraction outcomes (kept vs deleted concepts/documents)
2. Detects patterns from IMPLICIT signals (no feedback needed)
3. Makes decisions independently (creates/adjusts rules)
4. Self-corrects based on observed accuracy
5. Experiments with strategies and adopts what works

NO HUMAN TRIGGERS - runs continuously in background.
"""

import logging
import random
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter, defaultdict
from sqlalchemy import func, and_, or_
from celery.schedules import crontab

from .celery_app import celery_app
from .database import get_db_context
from .db_models import (
    DBLearnedRule,
    DBConceptVocabulary,
    DBUserLearningProfile,
    DBUserFeedback,
    DBAIDecision,
    DBDocument,
    DBConcept,
    DBCluster,
    DBDocumentChunk,
    DBLearningAgentState
)

logger = logging.getLogger(__name__)


# =============================================================================
# Autonomous Agent State (Singleton)
# =============================================================================

class AutonomousAgentState:
    """
    Tracks the agent's autonomous decision-making state.
    Persists metrics to database so they survive restarts.
    """

    _instance = None
    AGENT_KEY = "default"  # For future multi-tenant support

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_state()
            cls._instance._load_from_db()
        return cls._instance

    def _init_state(self):
        self.status = "idle"
        self.mode = "observing"  # observing, learning, experimenting, acting
        self.last_observation = None
        self.last_action = None
        self.total_observations = 0
        self.total_actions = 0
        self.autonomous_rules_created = 0
        self.autonomous_decisions = 0
        self.experiments_active = {}
        self.accuracy_history = []
        self.current_strategy = "conservative"  # conservative, balanced, aggressive

    def _load_from_db(self):
        """Load persisted state from database."""
        try:
            with get_db_context() as db:
                state = db.query(DBLearningAgentState).filter_by(
                    agent_key=self.AGENT_KEY
                ).first()

                if state:
                    self.status = state.status or "idle"
                    self.mode = state.mode or "observing"
                    self.current_strategy = state.current_strategy or "conservative"
                    self.total_observations = state.total_observations or 0
                    self.total_actions = state.total_actions or 0
                    self.autonomous_rules_created = state.autonomous_rules_created or 0
                    self.autonomous_decisions = state.autonomous_decisions or 0
                    self.experiments_active = state.experiments_active or {}
                    self.accuracy_history = state.accuracy_history or []
                    self.last_observation = state.last_observation
                    self.last_action = state.last_action
                    logger.info(f"🤖 Learning Agent: Loaded state from database (observations={self.total_observations})")
                else:
                    logger.info("🤖 Learning Agent: No existing state found, starting fresh")
        except Exception as e:
            logger.warning(f"🤖 Learning Agent: Could not load state from database: {e}")

    def _save_to_db(self):
        """Persist current state to database."""
        try:
            with get_db_context() as db:
                state = db.query(DBLearningAgentState).filter_by(
                    agent_key=self.AGENT_KEY
                ).first()

                if not state:
                    state = DBLearningAgentState(agent_key=self.AGENT_KEY)
                    db.add(state)

                state.status = self.status
                state.mode = self.mode
                state.current_strategy = self.current_strategy
                state.total_observations = self.total_observations
                state.total_actions = self.total_actions
                state.autonomous_rules_created = self.autonomous_rules_created
                state.autonomous_decisions = self.autonomous_decisions
                state.experiments_active = self.experiments_active
                state.accuracy_history = self.accuracy_history[-100:]  # Keep last 100
                state.last_observation = self.last_observation
                state.last_action = self.last_action

                db.commit()
        except Exception as e:
            logger.warning(f"🤖 Learning Agent: Could not save state to database: {e}")

    def record_observation(self, observation_type: str, data: Dict):
        """Record an observation made by the agent."""
        self.last_observation = {
            "type": observation_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.total_observations += 1
        self.mode = "observing"
        self._save_to_db()

    def record_action(self, action_type: str, details: Dict):
        """Record an autonomous action taken."""
        self.last_action = {
            "type": action_type,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.total_actions += 1
        self.autonomous_decisions += 1
        self.mode = "acting"
        self._save_to_db()

    def record_accuracy(self, accuracy: float, sample_size: int):
        """Track accuracy over time to detect trends."""
        self.accuracy_history.append({
            "accuracy": accuracy,
            "sample_size": sample_size,
            "timestamp": datetime.utcnow().isoformat()
        })
        # Keep last 100 measurements
        self.accuracy_history = self.accuracy_history[-100:]
        self._save_to_db()

    def get_accuracy_trend(self) -> str:
        """Determine if accuracy is improving, stable, or declining."""
        if len(self.accuracy_history) < 5:
            return "insufficient_data"

        recent = self.accuracy_history[-5:]
        older = self.accuracy_history[-10:-5] if len(self.accuracy_history) >= 10 else []

        if not older:
            return "baseline"

        recent_avg = sum(h["accuracy"] for h in recent) / len(recent)
        older_avg = sum(h["accuracy"] for h in older) / len(older)

        if recent_avg > older_avg + 0.05:
            return "improving"
        elif recent_avg < older_avg - 0.05:
            return "declining"
        return "stable"

    def to_dict(self) -> Dict[str, Any]:
        """Export state for monitoring."""
        return {
            "status": self.status,
            "mode": self.mode,
            "strategy": self.current_strategy,
            "total_observations": self.total_observations,
            "total_actions": self.total_actions,
            "autonomous_rules_created": self.autonomous_rules_created,
            "autonomous_decisions": self.autonomous_decisions,
            "accuracy_trend": self.get_accuracy_trend(),
            "experiments_active": len(self.experiments_active),
            "last_observation": self.last_observation,
            "last_action": self.last_action
        }


agent = AutonomousAgentState()


# =============================================================================
# AUTONOMOUS OBSERVATION: Learn from what happens, not what users say
# =============================================================================

@celery_app.task(name="backend.learning_agent.observe_outcomes")
def observe_outcomes():
    """
    CORE AUTONOMOUS OBSERVATION - The agent watches what happens.

    Learns from IMPLICIT signals without any user feedback:
    1. Documents that were deleted soon after upload = bad extraction
    2. Documents that stayed and were accessed = good extraction
    3. Concepts that appear in successful docs vs failed ones
    4. Cluster assignments that stick vs get changed

    This is TRUE autonomous learning - no human input required.
    """
    agent.status = "running"
    agent.mode = "observing"

    logger.info("👁️ Autonomous Agent: Observing outcomes...")

    observations = []

    try:
        with get_db_context() as db:
            # -----------------------------------------------------------------
            # OBSERVATION 1: Deleted documents = extraction failures
            # If a document is deleted within 1 hour of upload, something was wrong
            # -----------------------------------------------------------------
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            one_week_ago = datetime.utcnow() - timedelta(days=7)

            # Find documents that "failed" (deleted quickly)
            # We can't query deleted docs directly, but we can track deletions
            # For now, look at AI decisions without corresponding documents
            orphan_decisions = db.query(DBAIDecision).filter(
                DBAIDecision.created_at >= one_week_ago,
                DBAIDecision.document_id != None
            ).all()

            deleted_doc_ids = set()
            for decision in orphan_decisions:
                doc = db.query(DBDocument).filter_by(doc_id=decision.document_id).first()
                if not doc:  # Document was deleted
                    deleted_doc_ids.add(decision.document_id)

            if deleted_doc_ids:
                observations.append({
                    "type": "deleted_documents",
                    "count": len(deleted_doc_ids),
                    "insight": "Documents were deleted after extraction - may indicate poor extraction quality"
                })

                # Learn: What concepts were in deleted docs?
                failed_concepts = defaultdict(int)
                for decision in orphan_decisions:
                    if decision.document_id in deleted_doc_ids:
                        concepts = decision.output_data.get("concepts", [])
                        for c in concepts:
                            name = c.get("name", c) if isinstance(c, dict) else c
                            failed_concepts[name.lower()] += 1

                agent.record_observation("deletion_patterns", {
                    "deleted_count": len(deleted_doc_ids),
                    "failed_concepts": dict(failed_concepts)
                })

            # -----------------------------------------------------------------
            # OBSERVATION 2: Successful documents = good patterns to learn from
            # Documents that exist and have been accessed = good extractions
            # -----------------------------------------------------------------
            successful_docs = db.query(DBDocument).filter(
                DBDocument.ingested_at >= one_week_ago
            ).all()

            success_concepts = defaultdict(int)
            success_clusters = defaultdict(int)

            for doc in successful_docs:
                # Get concepts for this doc
                concepts = db.query(DBConcept).filter_by(document_id=doc.id).all()
                for c in concepts:
                    success_concepts[c.name.lower()] += 1

                if doc.cluster_id:
                    cluster = db.query(DBCluster).filter_by(id=doc.cluster_id).first()
                    if cluster:
                        success_clusters[cluster.name.lower()] += 1

            if success_concepts:
                observations.append({
                    "type": "successful_patterns",
                    "concept_count": len(success_concepts),
                    "cluster_count": len(success_clusters)
                })

                agent.record_observation("success_patterns", {
                    "top_concepts": dict(Counter(success_concepts).most_common(20)),
                    "top_clusters": dict(Counter(success_clusters).most_common(10))
                })

            # -----------------------------------------------------------------
            # OBSERVATION 3: Confidence calibration from actual outcomes
            # What confidence levels lead to kept vs modified content?
            # -----------------------------------------------------------------
            decisions = db.query(DBAIDecision).filter(
                DBAIDecision.created_at >= one_week_ago
            ).all()

            confidence_outcomes = defaultdict(lambda: {"kept": 0, "modified": 0})

            for decision in decisions:
                # Bucket by confidence
                bucket = round(decision.confidence_score, 1)

                # Check if there was feedback (modification)
                feedback = db.query(DBUserFeedback).filter(
                    DBUserFeedback.document_id == decision.document_id,
                    DBUserFeedback.created_at >= decision.created_at
                ).first()

                if feedback:
                    confidence_outcomes[bucket]["modified"] += 1
                else:
                    confidence_outcomes[bucket]["kept"] += 1

            if confidence_outcomes:
                observations.append({
                    "type": "confidence_calibration",
                    "buckets": dict(confidence_outcomes)
                })

                # Calculate optimal threshold
                for bucket, outcomes in sorted(confidence_outcomes.items()):
                    total = outcomes["kept"] + outcomes["modified"]
                    if total >= 5:
                        keep_rate = outcomes["kept"] / total
                        if keep_rate >= 0.8:
                            agent.record_observation("optimal_threshold", {
                                "threshold": bucket,
                                "keep_rate": keep_rate,
                                "sample_size": total
                            })
                            break

            # -----------------------------------------------------------------
            # OBSERVATION 4: Concept co-occurrence patterns
            # Which concepts appear together in successful docs?
            # -----------------------------------------------------------------
            cooccurrence = defaultdict(int)

            for doc in successful_docs:
                concepts = db.query(DBConcept).filter_by(document_id=doc.id).all()
                concept_names = [c.name.lower() for c in concepts]

                for i, c1 in enumerate(concept_names):
                    for c2 in concept_names[i+1:]:
                        pair = tuple(sorted([c1, c2]))
                        cooccurrence[pair] += 1

            # Find strong co-occurrence patterns
            strong_pairs = [(pair, count) for pair, count in cooccurrence.items() if count >= 3]

            if strong_pairs:
                observations.append({
                    "type": "concept_cooccurrence",
                    "strong_pairs": len(strong_pairs),
                    "examples": strong_pairs[:5]
                })

            logger.info(f"👁️ Observations complete: {len(observations)} patterns detected")

            return {
                "status": "success",
                "observations": observations,
                "timestamp": datetime.utcnow().isoformat()
            }

    except Exception as e:
        agent.status = "error"
        logger.error(f"👁️ Observation failed: {e}", exc_info=True)
        raise


# =============================================================================
# AUTONOMOUS DECISION MAKING: Act on observations
# =============================================================================

@celery_app.task(name="backend.learning_agent.make_autonomous_decisions")
def make_autonomous_decisions():
    """
    AUTONOMOUS DECISION MAKING - The agent takes action.

    Based on observations, the agent INDEPENDENTLY decides to:
    1. Create new rules when patterns are clear
    2. Adjust confidence thresholds based on outcomes
    3. Deactivate rules that aren't working
    4. Update vocabulary based on successful extractions

    NO HUMAN APPROVAL NEEDED - the agent acts on its own judgment.
    """
    agent.status = "running"
    agent.mode = "acting"

    logger.info("🎯 Autonomous Agent: Making decisions...")

    actions_taken = []

    try:
        with get_db_context() as db:
            # Get all users to process
            users = db.query(DBDocument.owner_username).distinct().all()
            users = [u[0] for u in users if u[0]]

            for username in users:
                # ---------------------------------------------------------
                # DECISION 1: Create rejection rules for consistently bad concepts
                # ---------------------------------------------------------
                bad_concepts = _identify_bad_concepts(db, username)

                for concept_name, evidence in bad_concepts.items():
                    if evidence["score"] >= 0.7:  # High confidence it's bad
                        # CREATE RULE AUTONOMOUSLY
                        existing = db.query(DBLearnedRule).filter_by(
                            username=username,
                            rule_type="concept_reject",
                            active=True
                        ).filter(
                            DBLearnedRule.condition.contains({"concept_matches": concept_name})
                        ).first()

                        if not existing:
                            rule = DBLearnedRule(
                                username=username,
                                rule_type="concept_reject",
                                condition={"concept_matches": concept_name},
                                action={"reject": True},
                                confidence=evidence["score"],
                                source_feedback_ids=[],  # No feedback - autonomous
                            )
                            db.add(rule)
                            agent.autonomous_rules_created += 1
                            agent._save_to_db()  # Persist counter update

                            actions_taken.append({
                                "type": "rule_created",
                                "username": username,
                                "rule": f"REJECT '{concept_name}'",
                                "confidence": evidence["score"],
                                "reason": evidence["reason"],
                                "autonomous": True
                            })

                            logger.info(
                                f"🎯 AUTONOMOUS DECISION: Created REJECT rule for "
                                f"'{concept_name}' (user: {username}, confidence: {evidence['score']:.2f})"
                            )

                # ---------------------------------------------------------
                # DECISION 2: Adjust confidence thresholds based on outcomes
                # ---------------------------------------------------------
                profile = db.query(DBUserLearningProfile).filter_by(
                    username=username
                ).first()

                if not profile:
                    profile = DBUserLearningProfile(username=username)
                    db.add(profile)

                optimal_threshold = _calculate_optimal_threshold(db, username)

                if optimal_threshold and abs(optimal_threshold - profile.concept_confidence_threshold) > 0.05:
                    old_threshold = profile.concept_confidence_threshold
                    profile.concept_confidence_threshold = optimal_threshold

                    actions_taken.append({
                        "type": "threshold_adjusted",
                        "username": username,
                        "old": old_threshold,
                        "new": optimal_threshold,
                        "autonomous": True
                    })

                    logger.info(
                        f"🎯 AUTONOMOUS DECISION: Adjusted threshold for {username}: "
                        f"{old_threshold:.2f} → {optimal_threshold:.2f}"
                    )

                # ---------------------------------------------------------
                # DECISION 3: Learn vocabulary from successful extractions
                # ---------------------------------------------------------
                vocab_patterns = _identify_vocabulary_patterns(db, username)

                for canonical, variants in vocab_patterns.items():
                    if len(variants) >= 2:  # Multiple variants = normalization opportunity
                        existing = db.query(DBConceptVocabulary).filter_by(
                            username=username,
                            canonical_name=canonical
                        ).first()

                        if not existing:
                            vocab = DBConceptVocabulary(
                                username=username,
                                canonical_name=canonical,
                                variants=list(variants),
                                always_include=False,
                                never_include=False
                            )
                            db.add(vocab)

                            actions_taken.append({
                                "type": "vocabulary_learned",
                                "username": username,
                                "canonical": canonical,
                                "variants": list(variants),
                                "autonomous": True
                            })

                # ---------------------------------------------------------
                # DECISION 4: Deactivate underperforming rules
                # ---------------------------------------------------------
                rules = db.query(DBLearnedRule).filter_by(
                    username=username,
                    active=True
                ).filter(
                    DBLearnedRule.times_applied >= 5  # Need enough data
                ).all()

                for rule in rules:
                    total = rule.times_applied + rule.times_overridden
                    if total > 0:
                        accuracy = 1 - (rule.times_overridden / total)
                        if accuracy < 0.4:  # Very poor performance
                            rule.active = False

                            actions_taken.append({
                                "type": "rule_deactivated",
                                "username": username,
                                "rule_id": rule.id,
                                "accuracy": accuracy,
                                "reason": "Autonomous deactivation due to poor performance",
                                "autonomous": True
                            })

                            logger.info(
                                f"🎯 AUTONOMOUS DECISION: Deactivated rule #{rule.id} "
                                f"(accuracy: {accuracy:.1%})"
                            )

            db.commit()

            # Record actions taken
            for action in actions_taken:
                agent.record_action(action["type"], action)

            logger.info(f"🎯 Autonomous decisions complete: {len(actions_taken)} actions taken")

            # Send notifications for significant actions
            if actions_taken:
                _notify_autonomous_actions(actions_taken)

            return {
                "status": "success",
                "actions_taken": len(actions_taken),
                "actions": actions_taken
            }

    except Exception as e:
        agent.status = "error"
        logger.error(f"🎯 Decision making failed: {e}", exc_info=True)
        raise


# =============================================================================
# SELF-EVALUATION: Measure and improve
# =============================================================================

@celery_app.task(name="backend.learning_agent.self_evaluate")
def self_evaluate():
    """
    SELF-EVALUATION - The agent measures its own performance.

    Autonomously:
    1. Calculates accuracy metrics
    2. Detects performance trends
    3. Adjusts strategy based on results
    4. Reports on its own effectiveness
    """
    agent.status = "running"
    agent.mode = "evaluating"

    logger.info("📊 Autonomous Agent: Self-evaluating...")

    try:
        with get_db_context() as db:
            # Calculate overall accuracy
            rules = db.query(DBLearnedRule).filter_by(active=True).all()

            total_applied = sum(r.times_applied for r in rules)
            total_overridden = sum(r.times_overridden for r in rules)

            if total_applied + total_overridden > 0:
                overall_accuracy = 1 - (total_overridden / (total_applied + total_overridden))
            else:
                overall_accuracy = 0.5  # No data = unknown

            agent.record_accuracy(overall_accuracy, total_applied + total_overridden)

            # Adjust strategy based on accuracy trend
            trend = agent.get_accuracy_trend()

            strategy_change = None
            if trend == "declining" and agent.current_strategy != "conservative":
                agent.current_strategy = "conservative"
                strategy_change = "Switched to conservative strategy due to declining accuracy"
                agent._save_to_db()  # Persist strategy change
            elif trend == "improving" and overall_accuracy > 0.8:
                if agent.current_strategy == "conservative":
                    agent.current_strategy = "balanced"
                    strategy_change = "Upgraded to balanced strategy due to high accuracy"
                    agent._save_to_db()  # Persist strategy change
                elif agent.current_strategy == "balanced" and overall_accuracy > 0.9:
                    agent.current_strategy = "aggressive"
                    strategy_change = "Upgraded to aggressive strategy due to excellent accuracy"
                    agent._save_to_db()  # Persist strategy change

            # Calculate per-user accuracy
            user_accuracy = {}
            for username in db.query(DBLearnedRule.username).distinct():
                username = username[0]
                user_rules = [r for r in rules if r.username == username]
                user_applied = sum(r.times_applied for r in user_rules)
                user_overridden = sum(r.times_overridden for r in user_rules)
                if user_applied + user_overridden > 0:
                    user_accuracy[username] = 1 - (user_overridden / (user_applied + user_overridden))

            evaluation = {
                "overall_accuracy": overall_accuracy,
                "trend": trend,
                "strategy": agent.current_strategy,
                "strategy_change": strategy_change,
                "rules_active": len(rules),
                "total_applications": total_applied,
                "total_overrides": total_overridden,
                "user_accuracy": user_accuracy,
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info(
                f"📊 Self-evaluation: accuracy={overall_accuracy:.1%}, "
                f"trend={trend}, strategy={agent.current_strategy}"
            )

            if strategy_change:
                logger.info(f"📊 Strategy changed: {strategy_change}")

            return evaluation

    except Exception as e:
        logger.error(f"📊 Self-evaluation failed: {e}", exc_info=True)
        raise


# =============================================================================
# EXPERIMENTATION: Try new approaches
# =============================================================================

@celery_app.task(name="backend.learning_agent.run_experiments")
def run_experiments():
    """
    EXPERIMENTATION - The agent tests hypotheses.

    Autonomously runs A/B tests:
    1. Try different confidence thresholds
    2. Test different rule creation criteria
    3. Compare outcomes and adopt winners
    """
    agent.status = "running"
    agent.mode = "experimenting"

    logger.info("🧪 Autonomous Agent: Running experiments...")

    try:
        with get_db_context() as db:
            experiments = []

            # -----------------------------------------------------------------
            # EXPERIMENT: What minimum pattern count creates good rules?
            # -----------------------------------------------------------------
            experiment_id = f"min_pattern_{datetime.utcnow().strftime('%Y%m%d%H')}"

            if experiment_id not in agent.experiments_active:
                # Start new experiment
                rules_by_threshold = defaultdict(lambda: {"created": 0, "successful": 0})

                rules = db.query(DBLearnedRule).filter_by(active=True).all()

                for rule in rules:
                    # Infer what threshold created this rule based on confidence
                    if rule.confidence < 0.6:
                        threshold = 2
                    elif rule.confidence < 0.75:
                        threshold = 3
                    else:
                        threshold = 5

                    rules_by_threshold[threshold]["created"] += 1

                    # Check if rule is successful
                    if rule.times_applied > 0:
                        accuracy = 1 - (rule.times_overridden / (rule.times_applied + rule.times_overridden))
                        if accuracy >= 0.7:
                            rules_by_threshold[threshold]["successful"] += 1

                # Analyze results
                best_threshold = 2
                best_success_rate = 0

                for threshold, stats in rules_by_threshold.items():
                    if stats["created"] > 0:
                        success_rate = stats["successful"] / stats["created"]
                        if success_rate > best_success_rate:
                            best_success_rate = success_rate
                            best_threshold = threshold

                experiments.append({
                    "id": experiment_id,
                    "type": "min_pattern_threshold",
                    "results": dict(rules_by_threshold),
                    "recommendation": f"Use min_occurrences={best_threshold} (success rate: {best_success_rate:.1%})"
                })

                agent.experiments_active[experiment_id] = {
                    "started": datetime.utcnow().isoformat(),
                    "result": experiments[-1]
                }

            logger.info(f"🧪 Experiments complete: {len(experiments)} experiments run")

            return {
                "status": "success",
                "experiments": experiments
            }

    except Exception as e:
        logger.error(f"🧪 Experimentation failed: {e}", exc_info=True)
        raise


# =============================================================================
# Helper Functions for Autonomous Decision Making
# =============================================================================

def _identify_bad_concepts(db, username: str) -> Dict[str, Dict]:
    """
    Identify concepts that should be rejected based on outcomes.

    Looks at:
    - Concepts in deleted documents
    - Concepts that were frequently removed
    - Concepts with low confidence that weren't useful
    """
    bad_concepts = {}

    # Get AI decisions for this user
    decisions = db.query(DBAIDecision).filter(
        DBAIDecision.username == username,
        DBAIDecision.decision_type == "concept_extraction"
    ).order_by(DBAIDecision.created_at.desc()).limit(100).all()

    concept_stats = defaultdict(lambda: {"extracted": 0, "kept": 0, "feedback_removed": 0})

    for decision in decisions:
        extracted = decision.output_data.get("concepts", [])

        # Check what concepts survived
        if decision.document_id:
            doc = db.query(DBDocument).filter_by(doc_id=decision.document_id).first()
            if doc:
                current = db.query(DBConcept).filter_by(document_id=doc.id).all()
                current_names = {c.name.lower() for c in current}

                for c in extracted:
                    name = c.get("name", c) if isinstance(c, dict) else c
                    name = name.lower()
                    concept_stats[name]["extracted"] += 1
                    if name in current_names:
                        concept_stats[name]["kept"] += 1
            else:
                # Document was deleted - all concepts are "bad"
                for c in extracted:
                    name = c.get("name", c) if isinstance(c, dict) else c
                    name = name.lower()
                    concept_stats[name]["extracted"] += 1

    # Check feedback for explicit removals
    feedback = db.query(DBUserFeedback).filter(
        DBUserFeedback.username == username,
        DBUserFeedback.feedback_type == "concept_edit"
    ).order_by(DBUserFeedback.created_at.desc()).limit(50).all()

    for fb in feedback:
        old = set(
            c.get("name", c).lower() if isinstance(c, dict) else c.lower()
            for c in (fb.original_value or {}).get("concepts", [])
        )
        new = set(
            c.get("name", c).lower() if isinstance(c, dict) else c.lower()
            for c in (fb.new_value or {}).get("concepts", [])
        )
        for removed in old - new:
            concept_stats[removed]["feedback_removed"] += 1

    # Calculate "badness" score
    for name, stats in concept_stats.items():
        if stats["extracted"] >= 3:  # Need enough data
            removal_rate = 1 - (stats["kept"] / stats["extracted"])
            feedback_penalty = min(0.3, stats["feedback_removed"] * 0.1)

            score = removal_rate + feedback_penalty

            if score >= 0.6:  # Threshold for "bad" concept
                bad_concepts[name] = {
                    "score": min(1.0, score),
                    "extracted": stats["extracted"],
                    "kept": stats["kept"],
                    "feedback_removed": stats["feedback_removed"],
                    "reason": f"Removed {removal_rate:.0%} of the time, {stats['feedback_removed']} explicit removals"
                }

    return bad_concepts


def _calculate_optimal_threshold(db, username: str) -> Optional[float]:
    """
    Calculate optimal confidence threshold from actual outcomes.
    """
    decisions = db.query(DBAIDecision).filter(
        DBAIDecision.username == username,
        DBAIDecision.decision_type == "concept_extraction"
    ).order_by(DBAIDecision.created_at.desc()).limit(200).all()

    if len(decisions) < 10:
        return None

    # Bucket by confidence, track success rate
    buckets = defaultdict(lambda: {"total": 0, "successful": 0})

    for decision in decisions:
        bucket = round(decision.confidence_score, 1)

        # Check if extraction was "successful" (no modifications)
        feedback = db.query(DBUserFeedback).filter(
            DBUserFeedback.document_id == decision.document_id,
            DBUserFeedback.created_at >= decision.created_at
        ).first()

        buckets[bucket]["total"] += 1
        if not feedback:  # No feedback = extraction was accepted
            buckets[bucket]["successful"] += 1

    # Find lowest threshold with 80%+ success rate
    for threshold in [0.5, 0.6, 0.7, 0.8, 0.9]:
        if buckets[threshold]["total"] >= 5:
            success_rate = buckets[threshold]["successful"] / buckets[threshold]["total"]
            if success_rate >= 0.8:
                return threshold

    return 0.7  # Default


def _identify_vocabulary_patterns(db, username: str) -> Dict[str, set]:
    """
    Identify vocabulary normalization opportunities from successful extractions.
    """
    patterns = defaultdict(set)

    # Get concepts from user's documents
    docs = db.query(DBDocument).filter_by(owner_username=username).all()

    concept_variations = defaultdict(list)

    for doc in docs:
        concepts = db.query(DBConcept).filter_by(document_id=doc.id).all()
        for c in concepts:
            # Simple normalization: lowercase, remove extra spaces
            normalized = " ".join(c.name.lower().split())
            words = set(normalized.split())

            # Group by word overlap
            for existing in concept_variations:
                existing_words = set(existing.split())
                # If >50% word overlap and similar length, likely same concept
                overlap = len(words & existing_words) / max(len(words), len(existing_words))
                if overlap >= 0.5:
                    concept_variations[existing].append(normalized)
                    break
            else:
                concept_variations[normalized] = [normalized]

    # Find concepts with multiple variations
    for canonical, variations in concept_variations.items():
        unique_variations = set(variations)
        if len(unique_variations) > 1:
            patterns[canonical] = unique_variations

    return patterns


def _notify_autonomous_actions(actions: List[Dict]):
    """
    Notify users about autonomous actions the agent took.
    """
    import asyncio

    try:
        from .websocket_manager import manager, WebSocketEvent, EventType

        # Group actions by user
        by_user = defaultdict(list)
        for action in actions:
            username = action.get("username")
            if username:
                by_user[username].append(action)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        for username, user_actions in by_user.items():
            event = WebSocketEvent(
                event_type=EventType.NOTIFICATION,
                data={
                    "title": "🤖 AI Made Autonomous Decisions",
                    "message": f"The learning agent independently made {len(user_actions)} improvements to your extraction rules.",
                    "type": "autonomous_learning",
                    "details": {
                        "actions": user_actions[:5],  # First 5
                        "total": len(user_actions)
                    }
                }
            )

            try:
                loop.run_until_complete(manager.send_personal(username, event))
            except Exception:
                pass  # WebSocket may not be connected

        loop.close()

    except Exception as e:
        logger.warning(f"Failed to send autonomous action notifications: {e}")


# =============================================================================
# Public API for Agent Status
# =============================================================================

def get_agent_status() -> Dict[str, Any]:
    """Get comprehensive autonomous agent status."""
    return {
        "agent": agent.to_dict(),
        "is_autonomous": True,
        "requires_human_trigger": False,
        "scheduled_tasks": {
            "observe_outcomes": "every 5 minutes",
            "make_autonomous_decisions": "every 10 minutes",
            "self_evaluate": "every hour",
            "run_experiments": "every 6 hours"
        }
    }


# =============================================================================
# Celery Beat Schedule
# =============================================================================

LEARNING_AGENT_SCHEDULE = {
    # Observe outcomes - runs every 5 minutes
    "observe-outcomes": {
        "task": "backend.learning_agent.observe_outcomes",
        "schedule": crontab(minute="*/5"),
        "options": {"queue": "learning"}
    },

    # Make autonomous decisions - runs every 10 minutes
    "make-autonomous-decisions": {
        "task": "backend.learning_agent.make_autonomous_decisions",
        "schedule": crontab(minute="*/10"),
        "options": {"queue": "learning"}
    },

    # Self-evaluation - runs every hour
    "self-evaluate": {
        "task": "backend.learning_agent.self_evaluate",
        "schedule": crontab(minute=0),
        "options": {"queue": "learning"}
    },

    # Experiments - runs every 6 hours
    "run-experiments": {
        "task": "backend.learning_agent.run_experiments",
        "schedule": crontab(hour="*/6", minute=30),
        "options": {"queue": "learning"}
    }
}
