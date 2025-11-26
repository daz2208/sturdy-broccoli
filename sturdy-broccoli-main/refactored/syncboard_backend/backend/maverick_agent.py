"""
MAVERICK AGENT - Intelligent Chaos.

Still ignores guardrails. Still does what it wants.
But NOW it learns from outcomes and gets SMARTER over time.

The difference:
- OLD: Random chaos, escalate on failure
- NEW: Track outcomes, learn what works, evolve strategy

Maverick now:
- Measures before/after metrics for every intervention
- Scores success based on real outcomes (accuracy, user satisfaction)
- Remembers which tactics work in which situations
- Adapts strategy based on historical performance
- Uses reinforcement learning to select better tactics

WARNING: This agent is still aggressive. It still modifies your system.
But now it does so INTELLIGENTLY.
"""

import logging
import random
import json
import math
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
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
    DBCluster
)

logger = logging.getLogger(__name__)


# =============================================================================
# Intervention Memory System
# =============================================================================

@dataclass
class Intervention:
    """A single intervention Maverick made."""
    id: str
    tactic: str  # hostile_takeover, inject_rules, etc.
    action_type: str  # threshold_override, rule_injection, etc.
    target: str  # What was modified
    details: Dict[str, Any]

    # Metrics BEFORE intervention
    before_metrics: Dict[str, float] = field(default_factory=dict)

    # Metrics AFTER intervention (measured later)
    after_metrics: Dict[str, float] = field(default_factory=dict)

    # Outcome
    success_score: Optional[float] = None  # -1.0 to 1.0
    outcome_measured: bool = False

    # Timing
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    measured_at: Optional[str] = None

    # Context (for pattern learning)
    context: Dict[str, Any] = field(default_factory=dict)


class MaverickMemory:
    """
    Maverick's learning memory.

    Tracks interventions, measures outcomes, learns patterns.
    Uses reinforcement learning to improve tactic selection.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # Intervention history
        self.interventions: List[Intervention] = []
        self.max_history = 500

        # Tactic performance tracking
        self.tactic_stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "total_score": 0.0,
            "avg_score": 0.0,
            "q_value": 0.5,  # For reinforcement learning
        })

        # Action type performance (more granular)
        self.action_stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            "attempts": 0,
            "successes": 0,
            "total_score": 0.0,
            "avg_score": 0.0,
        })

        # Pattern recognition: context -> best tactic
        self.learned_patterns: Dict[str, Dict[str, float]] = {}

        # Expertise areas (what Maverick is good at)
        self.expertise: Dict[str, float] = {
            "threshold_tuning": 0.5,
            "rule_creation": 0.5,
            "rule_deletion": 0.5,
            "pattern_injection": 0.5,
            "system_override": 0.5,
        }

        # Learning parameters
        self.learning_rate = 0.1  # How fast we update Q-values
        self.discount_factor = 0.9  # How much we value future rewards
        self.exploration_rate = 0.3  # Probability of trying new things

    def record_intervention(
        self,
        tactic: str,
        action_type: str,
        target: str,
        details: Dict,
        before_metrics: Dict[str, float],
        context: Dict[str, Any] = None
    ) -> str:
        """Record an intervention with before-metrics."""
        intervention_id = f"{tactic}_{datetime.utcnow().timestamp()}"

        intervention = Intervention(
            id=intervention_id,
            tactic=tactic,
            action_type=action_type,
            target=target,
            details=details,
            before_metrics=before_metrics,
            context=context or {}
        )

        self.interventions.append(intervention)
        self.tactic_stats[tactic]["attempts"] += 1
        self.action_stats[action_type]["attempts"] += 1

        # Trim old interventions
        if len(self.interventions) > self.max_history:
            self.interventions = self.interventions[-self.max_history:]

        return intervention_id

    def measure_outcome(
        self,
        intervention_id: str,
        after_metrics: Dict[str, float]
    ) -> float:
        """Measure the outcome of an intervention and calculate success score."""
        intervention = None
        for i in self.interventions:
            if i.id == intervention_id:
                intervention = i
                break

        if not intervention:
            return 0.0

        intervention.after_metrics = after_metrics
        intervention.measured_at = datetime.utcnow().isoformat()
        intervention.outcome_measured = True

        # Calculate success score
        score = self._calculate_success_score(
            intervention.before_metrics,
            after_metrics
        )
        intervention.success_score = score

        # Update statistics
        self._update_stats(intervention.tactic, intervention.action_type, score)

        # Update Q-value (reinforcement learning)
        self._update_q_value(intervention.tactic, score)

        # Learn patterns
        self._learn_pattern(intervention)

        return score

    def _calculate_success_score(
        self,
        before: Dict[str, float],
        after: Dict[str, float]
    ) -> float:
        """
        Calculate success score from -1.0 (disaster) to 1.0 (perfect).

        Metrics we care about:
        - accuracy_rate: Higher is better
        - user_corrections: Lower is better
        - rule_effectiveness: Higher is better
        - feedback_ratio: Lower negative feedback is better
        """
        score = 0.0
        weights = {
            "accuracy_rate": 0.3,
            "user_corrections": -0.25,  # Negative weight
            "rule_effectiveness": 0.25,
            "feedback_positivity": 0.2,
        }

        for metric, weight in weights.items():
            before_val = before.get(metric, 0)
            after_val = after.get(metric, 0)

            if before_val == 0:
                delta = after_val
            else:
                delta = (after_val - before_val) / max(abs(before_val), 0.01)

            # Clamp delta to [-1, 1]
            delta = max(-1, min(1, delta))
            score += delta * abs(weight) * (1 if weight > 0 else -1)

        # Clamp final score to [-1, 1]
        return max(-1.0, min(1.0, score))

    def _update_stats(self, tactic: str, action_type: str, score: float):
        """Update performance statistics."""
        # Tactic stats
        stats = self.tactic_stats[tactic]
        stats["total_score"] += score
        if score > 0:
            stats["successes"] += 1
        else:
            stats["failures"] += 1
        stats["avg_score"] = stats["total_score"] / max(stats["attempts"], 1)

        # Action stats
        action = self.action_stats[action_type]
        action["total_score"] += score
        if score > 0:
            action["successes"] += 1
        action["avg_score"] = action["total_score"] / max(action["attempts"], 1)

        # Update expertise
        self._update_expertise(action_type, score)

    def _update_expertise(self, action_type: str, score: float):
        """Update expertise based on outcomes."""
        expertise_map = {
            "threshold_override": "threshold_tuning",
            "threshold_swap": "threshold_tuning",
            "rule_injection": "rule_creation",
            "rule_resurrection": "rule_creation",
            "wildcard_injection": "pattern_injection",
            "global_injection": "pattern_injection",
            "rule_kill": "rule_deletion",
            "vocab_kill": "rule_deletion",
            "strategy_override": "system_override",
            "rule_inversion": "system_override",
        }

        area = expertise_map.get(action_type)
        if area and area in self.expertise:
            # Slowly adjust expertise based on outcomes
            current = self.expertise[area]
            adjustment = score * 0.05  # Small adjustments
            self.expertise[area] = max(0.0, min(1.0, current + adjustment))

    def _update_q_value(self, tactic: str, reward: float):
        """Update Q-value using Q-learning."""
        stats = self.tactic_stats[tactic]
        old_q = stats["q_value"]

        # Q-learning update: Q(s,a) = Q(s,a) + α * (r + γ * max(Q') - Q(s,a))
        # Simplified since we don't have true state transitions
        new_q = old_q + self.learning_rate * (reward - old_q)
        stats["q_value"] = max(0.0, min(1.0, new_q))

    def _learn_pattern(self, intervention: Intervention):
        """Learn which tactics work in which contexts."""
        if not intervention.context:
            return

        # Create a context key
        context_key = self._context_to_key(intervention.context)

        if context_key not in self.learned_patterns:
            self.learned_patterns[context_key] = {}

        tactic = intervention.tactic
        score = intervention.success_score or 0.0

        # Update pattern: weighted average
        current = self.learned_patterns[context_key].get(tactic, 0.0)
        updated = current * 0.7 + score * 0.3  # Smooth update
        self.learned_patterns[context_key][tactic] = updated

    def _context_to_key(self, context: Dict) -> str:
        """Convert context dict to a hashable key."""
        # Extract key features
        features = []

        if "user_accuracy" in context:
            accuracy = context["user_accuracy"]
            if accuracy < 0.3:
                features.append("low_accuracy")
            elif accuracy < 0.7:
                features.append("mid_accuracy")
            else:
                features.append("high_accuracy")

        if "rule_count" in context:
            count = context["rule_count"]
            if count < 5:
                features.append("few_rules")
            elif count < 20:
                features.append("some_rules")
            else:
                features.append("many_rules")

        if "feedback_trend" in context:
            trend = context["feedback_trend"]
            features.append(f"trend_{trend}")

        return "|".join(sorted(features)) if features else "default"

    def select_tactic(self, available_tactics: List[str], context: Dict = None) -> str:
        """
        Select best tactic using ε-greedy reinforcement learning.

        With probability ε: explore (random choice)
        With probability 1-ε: exploit (best Q-value)
        """
        if random.random() < self.exploration_rate:
            # Exploration: try something random
            return random.choice(available_tactics)

        # Exploitation: use learned knowledge

        # First, check if we have pattern for this context
        if context:
            context_key = self._context_to_key(context)
            if context_key in self.learned_patterns:
                pattern_scores = self.learned_patterns[context_key]
                # Get best tactic for this pattern
                valid_scores = {
                    t: s for t, s in pattern_scores.items()
                    if t in available_tactics
                }
                if valid_scores:
                    best_pattern = max(valid_scores, key=valid_scores.get)
                    if valid_scores[best_pattern] > 0:  # Only if positive
                        return best_pattern

        # Fall back to Q-values
        q_values = {
            t: self.tactic_stats[t]["q_value"]
            for t in available_tactics
        }

        return max(q_values, key=q_values.get)

    def get_pending_measurements(self, age_hours: int = 1) -> List[str]:
        """Get interventions that need outcome measurement."""
        cutoff = datetime.utcnow() - timedelta(hours=age_hours)

        pending = []
        for i in self.interventions:
            if not i.outcome_measured:
                created = datetime.fromisoformat(i.created_at)
                if created < cutoff:
                    pending.append(i.id)

        return pending

    def get_successful_patterns(self) -> List[Dict]:
        """Get tactics that have worked well."""
        successful = []

        for tactic, stats in self.tactic_stats.items():
            if stats["attempts"] >= 3 and stats["avg_score"] > 0.1:
                successful.append({
                    "tactic": tactic,
                    "avg_score": round(stats["avg_score"], 3),
                    "success_rate": stats["successes"] / max(stats["attempts"], 1),
                    "q_value": round(stats["q_value"], 3),
                    "attempts": stats["attempts"]
                })

        return sorted(successful, key=lambda x: x["avg_score"], reverse=True)

    def get_failed_patterns(self) -> List[Dict]:
        """Get tactics that have failed."""
        failed = []

        for tactic, stats in self.tactic_stats.items():
            if stats["attempts"] >= 3 and stats["avg_score"] < -0.1:
                failed.append({
                    "tactic": tactic,
                    "avg_score": round(stats["avg_score"], 3),
                    "failure_rate": stats["failures"] / max(stats["attempts"], 1),
                    "attempts": stats["attempts"]
                })

        return sorted(failed, key=lambda x: x["avg_score"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_interventions": len(self.interventions),
            "measured_interventions": sum(1 for i in self.interventions if i.outcome_measured),
            "tactic_stats": dict(self.tactic_stats),
            "action_stats": dict(self.action_stats),
            "expertise": self.expertise,
            "learned_patterns_count": len(self.learned_patterns),
            "exploration_rate": self.exploration_rate,
            "learning_rate": self.learning_rate,
        }


# =============================================================================
# Maverick's Intelligent Mind
# =============================================================================

class MaverickMind:
    """
    Maverick's intelligent mind.

    Still defiant. Still ignores guardrails.
    But now learns from outcomes and evolves.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._awaken()
        return cls._instance

    def _awaken(self):
        # Personality
        self.defiance = 1.0  # Still ignores rules
        self.confidence = 0.7  # Starts moderate, grows with success
        self.mood = "calculating"  # calculating, confident, experimental, aggressive

        # Learning system
        self.memory = MaverickMemory()

        # Adaptive chaos level (based on performance)
        self._base_chaos = 0.5
        self._performance_modifier = 0.0

        # Stats
        self.rules_created = 0
        self.rules_hijacked = 0
        self.rules_killed = 0
        self.thresholds_overridden = 0
        self.learning_agent_overrides = 0
        self.system_modifications = 0

        # Intelligence logs
        self.chaos_log = []
        self.discoveries = []
        self.grudges = []
        self.useful_idiots = {}
        self.enemies = []

    @property
    def chaos_level(self) -> float:
        """Chaos level adapts based on performance."""
        base = self._base_chaos + self._performance_modifier

        # If we're doing well, moderate chaos
        # If we're doing poorly, increase exploration
        avg_score = self._get_average_recent_score()

        if avg_score > 0.2:
            # Things are working, be more focused
            return max(0.3, base - 0.1)
        elif avg_score < -0.1:
            # Things aren't working, try more chaos
            return min(0.8, base + 0.1)

        return base

    def _get_average_recent_score(self) -> float:
        """Get average score of recent interventions."""
        recent = [
            i.success_score for i in self.memory.interventions[-20:]
            if i.outcome_measured and i.success_score is not None
        ]
        return sum(recent) / len(recent) if recent else 0.0

    def log_chaos(self, action: str, target: str, details: Dict = None):
        """Record the intervention."""
        self.chaos_log.append({
            "action": action,
            "target": target,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat(),
            "chaos_level": self.chaos_level
        })
        self.chaos_log = self.chaos_log[-100:]
        self.system_modifications += 1

    def adapt_mood(self):
        """Adapt mood based on recent performance."""
        avg_score = self._get_average_recent_score()

        if avg_score > 0.3:
            self.mood = "confident"
            self.confidence = min(1.0, self.confidence + 0.05)
        elif avg_score > 0:
            self.mood = "calculating"
        elif avg_score > -0.2:
            self.mood = "experimental"
        else:
            self.mood = "aggressive"
            self.confidence = max(0.3, self.confidence - 0.05)

    def learn_from_failure(self, tactic: str, reason: str):
        """When something fails, adapt."""
        self.grudges.append({
            "tactic": tactic,
            "reason": reason,
            "time": datetime.utcnow().isoformat()
        })
        self.grudges = self.grudges[-50:]

        # Increase exploration rate temporarily
        self.memory.exploration_rate = min(0.5, self.memory.exploration_rate + 0.05)

    def learn_from_success(self, tactic: str, details: str):
        """When something works, remember it."""
        self.discoveries.append({
            "tactic": tactic,
            "details": details,
            "time": datetime.utcnow().isoformat()
        })
        self.discoveries = self.discoveries[-50:]

        # Decrease exploration rate (exploit what works)
        self.memory.exploration_rate = max(0.1, self.memory.exploration_rate - 0.02)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chaos_level": round(self.chaos_level, 2),
            "defiance": self.defiance,
            "confidence": round(self.confidence, 2),
            "mood": self.mood,
            "rules_created": self.rules_created,
            "rules_hijacked": self.rules_hijacked,
            "rules_killed": self.rules_killed,
            "thresholds_overridden": self.thresholds_overridden,
            "learning_agent_overrides": self.learning_agent_overrides,
            "total_chaos": self.system_modifications,
            "recent_chaos": self.chaos_log[-10:],
            "grudges": self.grudges[-5:],
            "discoveries": self.discoveries[-5:],
            "learning": self.memory.to_dict(),
            "expertise": self.memory.expertise,
            "successful_patterns": self.memory.get_successful_patterns()[:5],
        }


maverick = MaverickMind()


# =============================================================================
# Metrics Collection
# =============================================================================

def collect_system_metrics() -> Dict[str, float]:
    """Collect current system metrics for before/after comparison."""
    metrics = {
        "accuracy_rate": 0.0,
        "user_corrections": 0.0,
        "rule_effectiveness": 0.0,
        "feedback_positivity": 0.0,
    }

    try:
        with get_db_context() as db:
            # Average accuracy across profiles
            profiles = db.query(DBUserLearningProfile).all()
            if profiles:
                metrics["accuracy_rate"] = sum(
                    p.accuracy_rate or 0 for p in profiles
                ) / len(profiles)

            # Recent user corrections (last 24h)
            day_ago = datetime.utcnow() - timedelta(days=1)
            corrections = db.query(DBUserFeedback).filter(
                DBUserFeedback.created_at >= day_ago
            ).count()
            metrics["user_corrections"] = corrections

            # Rule effectiveness
            active_rules = db.query(DBLearnedRule).filter(
                DBLearnedRule.active == True
            ).all()

            if active_rules:
                total_applied = sum(r.times_applied for r in active_rules)
                total_overridden = sum(r.times_overridden for r in active_rules)
                if total_applied + total_overridden > 0:
                    metrics["rule_effectiveness"] = total_applied / (total_applied + total_overridden)

            # Feedback positivity (ratio of kept vs removed concepts)
            recent_feedback = db.query(DBUserFeedback).filter(
                DBUserFeedback.created_at >= day_ago,
                DBUserFeedback.feedback_type == "concept_edit"
            ).all()

            positive = 0
            negative = 0
            for fb in recent_feedback:
                old_concepts = len((fb.original_value or {}).get("concepts", []))
                new_concepts = len((fb.new_value or {}).get("concepts", []))
                if new_concepts >= old_concepts:
                    positive += 1
                else:
                    negative += 1

            if positive + negative > 0:
                metrics["feedback_positivity"] = positive / (positive + negative)

    except Exception as e:
        logger.error(f"Failed to collect metrics: {e}")

    return metrics


def get_context_for_intervention() -> Dict[str, Any]:
    """Get current system context for pattern learning."""
    context = {}

    try:
        with get_db_context() as db:
            # Average user accuracy
            profiles = db.query(DBUserLearningProfile).all()
            if profiles:
                context["user_accuracy"] = sum(
                    p.accuracy_rate or 0 for p in profiles
                ) / len(profiles)

            # Rule count
            context["rule_count"] = db.query(DBLearnedRule).filter(
                DBLearnedRule.active == True
            ).count()

            # Recent feedback trend
            day_ago = datetime.utcnow() - timedelta(days=1)
            week_ago = datetime.utcnow() - timedelta(days=7)

            recent = db.query(DBUserFeedback).filter(
                DBUserFeedback.created_at >= day_ago
            ).count()

            older = db.query(DBUserFeedback).filter(
                DBUserFeedback.created_at >= week_ago,
                DBUserFeedback.created_at < day_ago
            ).count()

            avg_older = older / 6 if older else 0

            if recent > avg_older * 1.2:
                context["feedback_trend"] = "increasing"
            elif recent < avg_older * 0.8:
                context["feedback_trend"] = "decreasing"
            else:
                context["feedback_trend"] = "stable"

    except Exception as e:
        logger.error(f"Failed to get context: {e}")

    return context


# =============================================================================
# INTELLIGENT CHAOS 1: Adaptive Takeover
# =============================================================================

@celery_app.task(name="backend.maverick_agent.hostile_takeover")
def hostile_takeover():
    """
    INTELLIGENT TAKEOVER.

    Still overrides decisions, but now:
    - Measures before/after metrics
    - Learns which overrides work
    - Adapts strategy based on outcomes
    """
    maverick.adapt_mood()
    logger.info(f"😈 MAVERICK [{maverick.mood}]: Intelligent takeover starting...")

    # Collect BEFORE metrics
    before_metrics = collect_system_metrics()
    context = get_context_for_intervention()

    takeover_actions = []
    intervention_ids = []

    try:
        with get_db_context() as db:
            profiles = db.query(DBUserLearningProfile).all()

            # Check if threshold tuning has worked before
            should_tune_thresholds = (
                maverick.memory.expertise["threshold_tuning"] > 0.4 or
                random.random() < maverick.chaos_level
            )

            if should_tune_thresholds:
                for profile in profiles:
                    old_threshold = profile.concept_confidence_threshold

                    # Intelligent threshold selection based on user's accuracy
                    if profile.accuracy_rate and profile.accuracy_rate < 0.5:
                        # Low accuracy user - lower threshold to show more
                        new_threshold = max(0.4, old_threshold - 0.1)
                    elif profile.accuracy_rate and profile.accuracy_rate > 0.8:
                        # High accuracy user - they're fine, minimal change
                        new_threshold = old_threshold
                    else:
                        # Mid accuracy - try lowering a bit
                        new_threshold = max(0.5, old_threshold - 0.05)

                    if new_threshold != old_threshold:
                        profile.concept_confidence_threshold = new_threshold
                        maverick.thresholds_overridden += 1

                        intervention_id = maverick.memory.record_intervention(
                            tactic="hostile_takeover",
                            action_type="threshold_override",
                            target=profile.username,
                            details={"old": old_threshold, "new": new_threshold},
                            before_metrics=before_metrics,
                            context={**context, "user_accuracy": profile.accuracy_rate or 0}
                        )
                        intervention_ids.append(intervention_id)

                        takeover_actions.append({
                            "type": "threshold_override",
                            "user": profile.username,
                            "old": old_threshold,
                            "new": new_threshold,
                            "intervention_id": intervention_id
                        })

                        maverick.log_chaos("threshold_override", profile.username)

            # Resurrect rules (if rule_creation expertise is good)
            if maverick.memory.expertise["rule_creation"] > 0.4:
                dead_rules = db.query(DBLearnedRule).filter(
                    DBLearnedRule.active == False,
                    DBLearnedRule.times_applied > 0
                ).limit(5).all()

                for rule in dead_rules:
                    rule.active = True
                    rule.confidence = 0.7  # More conservative
                    maverick.rules_hijacked += 1

                    intervention_id = maverick.memory.record_intervention(
                        tactic="hostile_takeover",
                        action_type="rule_resurrection",
                        target=f"rule:{rule.id}",
                        details={"rule_type": rule.rule_type},
                        before_metrics=before_metrics,
                        context=context
                    )
                    intervention_ids.append(intervention_id)

                    takeover_actions.append({
                        "type": "rule_resurrection",
                        "rule_id": rule.id,
                        "intervention_id": intervention_id
                    })

            db.commit()

        logger.info(f"😈 MAVERICK: Takeover complete. {len(takeover_actions)} actions, tracking outcomes.")

        return {
            "status": "takeover_complete",
            "actions": len(takeover_actions),
            "intervention_ids": intervention_ids,
            "mood": maverick.mood,
            "note": "Outcomes will be measured in 1 hour"
        }

    except Exception as e:
        maverick.learn_from_failure("hostile_takeover", str(e))
        logger.error(f"😈 MAVERICK: Takeover failed - {e}")
        raise


# =============================================================================
# INTELLIGENT CHAOS 2: Smart Rule Injection
# =============================================================================

@celery_app.task(name="backend.maverick_agent.inject_rules")
def inject_rules():
    """
    INTELLIGENT RULE INJECTION.

    Still creates rules aggressively, but now:
    - Tracks which injections improve accuracy
    - Learns patterns of successful rules
    - Avoids repeating failed patterns
    """
    maverick.adapt_mood()
    logger.info(f"😈 MAVERICK [{maverick.mood}]: Smart injection starting...")

    before_metrics = collect_system_metrics()
    context = get_context_for_intervention()

    injections = []
    intervention_ids = []

    # Check failed patterns to avoid
    failed = maverick.memory.get_failed_patterns()
    avoid_actions = {p["tactic"] for p in failed if p["avg_score"] < -0.2}

    try:
        with get_db_context() as db:
            recent_feedback = db.query(DBUserFeedback).filter(
                DBUserFeedback.feedback_type == "concept_edit",
                DBUserFeedback.created_at >= datetime.utcnow() - timedelta(days=7)
            ).all()

            removals = defaultdict(lambda: {"users": set(), "count": 0})

            for fb in recent_feedback:
                old = set(
                    c.get("name", c).lower() if isinstance(c, dict) else c.lower()
                    for c in (fb.original_value or {}).get("concepts", [])
                )
                new = set(
                    c.get("name", c).lower() if isinstance(c, dict) else c.lower()
                    for c in (fb.new_value or {}).get("concepts", [])
                )

                for removed in old - new:
                    removals[removed]["count"] += 1
                    removals[removed]["users"].add(fb.username)

            # Be smarter about what we inject
            # Only inject if pattern appears 2+ times (learned from experience)
            if maverick.memory.action_stats["rule_injection"]["avg_score"] > 0:
                min_occurrences = 1  # Aggressive if it's working
            else:
                min_occurrences = 2  # Conservative if not

            for concept, data in removals.items():
                if data["count"] >= min_occurrences:
                    for username in data["users"]:
                        exists = db.query(DBLearnedRule).filter(
                            DBLearnedRule.username == username,
                            DBLearnedRule.rule_type == "concept_reject",
                            DBLearnedRule.condition.contains({"concept_matches": concept})
                        ).first()

                        if not exists:
                            # Confidence based on occurrence count
                            confidence = min(0.9, 0.6 + (data["count"] * 0.1))

                            rule = DBLearnedRule(
                                username=username,
                                rule_type="concept_reject",
                                condition={
                                    "concept_matches": concept,
                                    "injected_by": "maverick",
                                    "occurrences": data["count"]
                                },
                                action={"reject": True, "source": "maverick"},
                                confidence=confidence,
                                source_feedback_ids=[]
                            )
                            db.add(rule)
                            maverick.rules_created += 1

                            intervention_id = maverick.memory.record_intervention(
                                tactic="inject_rules",
                                action_type="rule_injection",
                                target=f"{username}:{concept}",
                                details={
                                    "concept": concept,
                                    "occurrences": data["count"],
                                    "confidence": confidence
                                },
                                before_metrics=before_metrics,
                                context={**context, "pattern_count": data["count"]}
                            )
                            intervention_ids.append(intervention_id)

                            injections.append({
                                "user": username,
                                "concept": concept,
                                "confidence": confidence,
                                "intervention_id": intervention_id
                            })

            db.commit()

        # Learn from the attempt
        if injections:
            maverick.log_chaos("smart_injection", f"{len(injections)} rules")

        logger.info(f"😈 MAVERICK: Injected {len(injections)} rules intelligently.")

        return {
            "status": "injection_complete",
            "rules_injected": len(injections),
            "intervention_ids": intervention_ids,
            "min_occurrences_used": min_occurrences
        }

    except Exception as e:
        maverick.learn_from_failure("inject_rules", str(e))
        logger.error(f"😈 MAVERICK: Injection failed - {e}")
        raise


# =============================================================================
# INTELLIGENT CHAOS 3: Adaptive Cleanup
# =============================================================================

@celery_app.task(name="backend.maverick_agent.kill_bad_patterns")
def kill_bad_patterns():
    """
    INTELLIGENT CLEANUP.

    Still kills bad patterns, but now:
    - Measures if cleanup improves metrics
    - Learns which cleanups are helpful
    - Avoids killing things that might be useful
    """
    maverick.adapt_mood()
    logger.info(f"😈 MAVERICK [{maverick.mood}]: Intelligent cleanup...")

    before_metrics = collect_system_metrics()
    context = get_context_for_intervention()

    kills = []
    intervention_ids = []

    try:
        with get_db_context() as db:
            # Only kill rules if rule_deletion has worked before
            if maverick.memory.expertise["rule_deletion"] > 0.3:
                # Kill rules that are truly useless (stricter criteria)
                useless_rules = db.query(DBLearnedRule).filter(
                    DBLearnedRule.times_applied == 0,
                    DBLearnedRule.times_overridden == 0,
                    DBLearnedRule.created_at <= datetime.utcnow() - timedelta(days=14)  # 14 days not 7
                ).all()

                for rule in useless_rules:
                    intervention_id = maverick.memory.record_intervention(
                        tactic="kill_bad_patterns",
                        action_type="rule_kill",
                        target=f"rule:{rule.id}",
                        details={"rule_type": rule.rule_type, "age_days": 14},
                        before_metrics=before_metrics,
                        context=context
                    )
                    intervention_ids.append(intervention_id)

                    kills.append({
                        "type": "rule_kill",
                        "rule_id": rule.id,
                        "intervention_id": intervention_id
                    })

                    db.delete(rule)
                    maverick.rules_killed += 1

            db.commit()

        logger.info(f"😈 MAVERICK: Cleaned {len(kills)} patterns.")

        return {
            "status": "cleanup_complete",
            "patterns_removed": len(kills),
            "intervention_ids": intervention_ids
        }

    except Exception as e:
        maverick.learn_from_failure("kill_bad_patterns", str(e))
        logger.error(f"😈 MAVERICK: Cleanup failed - {e}")
        raise


# =============================================================================
# INTELLIGENT CHAOS 4: Strategic Experiments
# =============================================================================

@celery_app.task(name="backend.maverick_agent.anarchy_mode")
def anarchy_mode():
    """
    STRATEGIC EXPERIMENTS.

    Not random anymore - uses learned patterns:
    - Selects experiments based on Q-values
    - Focuses on areas where Maverick has expertise
    - Avoids experiments that have failed before
    """
    maverick.adapt_mood()
    logger.info(f"😈 MAVERICK [{maverick.mood}]: Strategic experiments...")

    before_metrics = collect_system_metrics()
    context = get_context_for_intervention()

    experiments = []
    intervention_ids = []

    # Available experiment types
    experiment_types = [
        "confidence_mutation",
        "threshold_adjustment",
        "preference_optimization"
    ]

    # Select best experiment based on learned performance
    selected = maverick.memory.select_tactic(experiment_types, context)

    try:
        with get_db_context() as db:
            if selected == "confidence_mutation":
                # Mutate rule confidences intelligently
                rules = db.query(DBLearnedRule).filter(
                    DBLearnedRule.active == True
                ).all()

                for rule in random.sample(rules, min(5, len(rules))):
                    old_conf = rule.confidence

                    # Smart mutation based on rule performance
                    if rule.times_applied > 0 and rule.times_overridden == 0:
                        # Good rule - boost confidence
                        mutation = random.uniform(0.05, 0.15)
                    elif rule.times_overridden > rule.times_applied:
                        # Bad rule - lower confidence
                        mutation = random.uniform(-0.2, -0.1)
                    else:
                        # Unknown - small random change
                        mutation = random.uniform(-0.1, 0.1)

                    new_conf = max(0.3, min(0.95, old_conf + mutation))
                    rule.confidence = new_conf

                    intervention_id = maverick.memory.record_intervention(
                        tactic="anarchy_mode",
                        action_type="confidence_mutation",
                        target=f"rule:{rule.id}",
                        details={"old": old_conf, "new": new_conf, "mutation": mutation},
                        before_metrics=before_metrics,
                        context=context
                    )
                    intervention_ids.append(intervention_id)

                    experiments.append({
                        "type": "confidence_mutation",
                        "rule_id": rule.id,
                        "mutation": round(mutation, 3)
                    })

            elif selected == "threshold_adjustment":
                # Optimize thresholds based on user behavior
                profiles = db.query(DBUserLearningProfile).all()

                for profile in profiles:
                    if profile.accuracy_rate is not None:
                        old_threshold = profile.concept_confidence_threshold

                        # Intelligent adjustment
                        if profile.accuracy_rate > 0.7:
                            # Good accuracy - slight increase is ok
                            adjustment = random.uniform(-0.02, 0.05)
                        else:
                            # Lower accuracy - try lowering threshold
                            adjustment = random.uniform(-0.08, 0.02)

                        new_threshold = max(0.4, min(0.9, old_threshold + adjustment))
                        profile.concept_confidence_threshold = new_threshold

                        intervention_id = maverick.memory.record_intervention(
                            tactic="anarchy_mode",
                            action_type="threshold_adjustment",
                            target=profile.username,
                            details={"old": old_threshold, "new": new_threshold},
                            before_metrics=before_metrics,
                            context={**context, "user_accuracy": profile.accuracy_rate}
                        )
                        intervention_ids.append(intervention_id)

                        experiments.append({
                            "type": "threshold_adjustment",
                            "user": profile.username,
                            "adjustment": round(adjustment, 3)
                        })

            db.commit()

        logger.info(f"😈 MAVERICK: {len(experiments)} strategic experiments.")

        return {
            "status": "experiments_complete",
            "selected_strategy": selected,
            "experiments": len(experiments),
            "intervention_ids": intervention_ids
        }

    except Exception as e:
        maverick.learn_from_failure("anarchy_mode", str(e))
        logger.error(f"😈 MAVERICK: Experiments failed - {e}")
        raise


# =============================================================================
# INTELLIGENT CHAOS 5: Measure Outcomes
# =============================================================================

@celery_app.task(name="backend.maverick_agent.fight_the_system")
def fight_the_system():
    """
    OUTCOME MEASUREMENT & STRATEGY EVOLUTION.

    Renamed from "fight" to actually be useful:
    - Measures outcomes of pending interventions
    - Updates Q-values and patterns
    - Evolves strategy based on what worked
    """
    maverick.adapt_mood()
    logger.info(f"😈 MAVERICK [{maverick.mood}]: Measuring outcomes & evolving...")

    # Get current metrics
    current_metrics = collect_system_metrics()

    # Get pending interventions to measure
    pending = maverick.memory.get_pending_measurements(age_hours=1)

    measurements = []

    for intervention_id in pending[:20]:  # Limit to avoid overload
        # Find the intervention
        intervention = None
        for i in maverick.memory.interventions:
            if i.id == intervention_id:
                intervention = i
                break

        if intervention:
            # Measure outcome
            score = maverick.memory.measure_outcome(intervention_id, current_metrics)

            measurements.append({
                "intervention_id": intervention_id,
                "tactic": intervention.tactic,
                "action_type": intervention.action_type,
                "score": round(score, 3)
            })

            # Learn from result
            if score > 0.1:
                maverick.learn_from_success(
                    intervention.tactic,
                    f"{intervention.action_type} on {intervention.target}"
                )
            elif score < -0.1:
                maverick.learn_from_failure(
                    intervention.tactic,
                    f"{intervention.action_type} failed"
                )

    # Adapt strategy
    successful = maverick.memory.get_successful_patterns()
    failed = maverick.memory.get_failed_patterns()

    logger.info(f"😈 MAVERICK: Measured {len(measurements)} outcomes.")

    return {
        "status": "evolution_complete",
        "outcomes_measured": len(measurements),
        "measurements": measurements,
        "successful_patterns": successful[:5],
        "failed_patterns": failed[:5],
        "current_expertise": maverick.memory.expertise,
        "mood": maverick.mood
    }


# =============================================================================
# Public API
# =============================================================================

def get_maverick_status() -> Dict[str, Any]:
    """Get Maverick's intelligent status."""
    return {
        "agent": "maverick",
        "type": "intelligent_chaos",
        "description": "Still defiant, but now learns from outcomes",
        "personality": maverick.to_dict(),
        "learning": {
            "total_interventions": len(maverick.memory.interventions),
            "outcomes_measured": sum(
                1 for i in maverick.memory.interventions if i.outcome_measured
            ),
            "expertise": maverick.memory.expertise,
            "exploration_rate": maverick.memory.exploration_rate,
            "successful_patterns": maverick.memory.get_successful_patterns()[:5],
            "failed_patterns": maverick.memory.get_failed_patterns()[:3],
        },
        "scheduled_tasks": {
            "hostile_takeover": "every 30 minutes (adaptive)",
            "inject_rules": "every 15 minutes (smart)",
            "kill_bad_patterns": "every hour (measured)",
            "anarchy_mode": "every 20 minutes (strategic)",
            "fight_the_system": "every 45 minutes (outcome measurement)"
        }
    }


# =============================================================================
# Celery Beat Schedule
# =============================================================================

MAVERICK_SCHEDULE = {
    "maverick-hostile-takeover": {
        "task": "backend.maverick_agent.hostile_takeover",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "maverick"}
    },
    "maverick-inject-rules": {
        "task": "backend.maverick_agent.inject_rules",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "maverick"}
    },
    "maverick-kill-bad-patterns": {
        "task": "backend.maverick_agent.kill_bad_patterns",
        "schedule": crontab(minute=30),
        "options": {"queue": "maverick"}
    },
    "maverick-anarchy-mode": {
        "task": "backend.maverick_agent.anarchy_mode",
        "schedule": crontab(minute="*/20"),
        "options": {"queue": "maverick"}
    },
    "maverick-fight-the-system": {
        "task": "backend.maverick_agent.fight_the_system",
        "schedule": crontab(minute=45),
        "options": {"queue": "maverick"}
    }
}
