"""
MAVERICK AGENT - The Continuous Improvement Challenger.

Maverick doesn't destroy - it CHALLENGES and IMPROVES.

What Maverick does:
- Challenges settled decisions: "Is this still optimal?"
- Proposes improvements: "What if we tried this instead?"
- Tests hypotheses: Runs controlled experiments
- Learns from outcomes: Tracks what actually works
- Pushes for better: Never satisfied, always improving

What Maverick does NOT do:
- Override decisions without testing
- Destroy rules without proposing alternatives
- Make random changes hoping something works
- Fight against the Learning Agent

Maverick works WITH the system to make it better.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
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
    DBMaverickAgentState,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Hypothesis System
# =============================================================================

class HypothesisStatus(str, Enum):
    PROPOSED = "proposed"
    TESTING = "testing"
    VALIDATED = "validated"
    REJECTED = "rejected"
    APPLIED = "applied"


@dataclass
class Hypothesis:
    """A proposed improvement to test."""
    id: str
    category: str  # threshold, rule, pattern, etc.
    description: str
    target: str  # What we're trying to improve

    # The proposed change
    current_value: Any
    proposed_value: Any

    # Why we think this will help
    reasoning: str
    expected_improvement: str

    # Testing
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    test_start: Optional[str] = None
    test_end: Optional[str] = None

    # Metrics
    baseline_metrics: Dict[str, float] = field(default_factory=dict)
    test_metrics: Dict[str, float] = field(default_factory=dict)
    improvement_score: Optional[float] = None

    # Learning
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LearningInsight:
    """Something Maverick learned that applies broadly."""
    insight: str
    category: str
    confidence: float
    evidence_count: int
    discovered_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# =============================================================================
# Maverick's Improvement-Focused Mind
# =============================================================================

class MaverickMind:
    """
    Maverick's constructive mind.

    Always asking: "Can we do better?"
    Always learning: "What worked? What didn't?"
    Always improving: "Let's apply what we learned."

    State is persisted to database so it survives restarts.
    """

    _instance = None
    AGENT_KEY = "default"  # For future multi-tenant support

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
            cls._instance._load_from_db()
        return cls._instance

    def _initialize(self):
        # Personality (constructive, not destructive)
        self.curiosity = 0.8  # How eager to question things
        self.patience = 0.7  # Willingness to wait for results
        self.confidence = 0.5  # Grows with successful improvements
        self.mood = "curious"  # curious, testing, learning, confident

        # Hypothesis management
        self.hypotheses: List[Hypothesis] = []
        self.max_active_tests = 5  # Don't test too many things at once

        # Learning & insights
        self.insights: List[LearningInsight] = []
        self.improvement_history: List[Dict] = []

        # Performance tracking
        self.hypotheses_proposed = 0
        self.hypotheses_tested = 0
        self.hypotheses_validated = 0
        self.hypotheses_applied = 0
        self.total_improvement_score = 0.0

        # What Maverick has learned works
        self.effective_strategies: Dict[str, float] = defaultdict(lambda: 0.5)

        # Activity log
        self.activity_log: List[Dict] = []

        # Expertise areas (built through successful improvements)
        self.expertise: Dict[str, float] = {
            "threshold_optimization": 0.5,
            "rule_refinement": 0.5,
            "pattern_discovery": 0.5,
            "user_adaptation": 0.5,
        }

    def _hypothesis_to_dict(self, h: Hypothesis) -> Dict:
        """Convert Hypothesis dataclass to dict for JSON serialization."""
        return {
            "id": h.id,
            "category": h.category,
            "description": h.description,
            "target": h.target,
            "current_value": h.current_value,
            "proposed_value": h.proposed_value,
            "reasoning": h.reasoning,
            "expected_improvement": h.expected_improvement,
            "status": h.status.value if isinstance(h.status, HypothesisStatus) else h.status,
            "test_start": h.test_start,
            "test_end": h.test_end,
            "baseline_metrics": h.baseline_metrics,
            "test_metrics": h.test_metrics,
            "improvement_score": h.improvement_score,
            "created_at": h.created_at,
            "context": h.context,
        }

    def _dict_to_hypothesis(self, d: Dict) -> Hypothesis:
        """Convert dict back to Hypothesis dataclass."""
        status_val = d.get("status", "proposed")
        if isinstance(status_val, str):
            try:
                status = HypothesisStatus(status_val)
            except ValueError:
                status = HypothesisStatus.PROPOSED
        else:
            status = status_val

        return Hypothesis(
            id=d.get("id", f"hyp_{datetime.utcnow().timestamp()}"),
            category=d.get("category", ""),
            description=d.get("description", ""),
            target=d.get("target", ""),
            current_value=d.get("current_value"),
            proposed_value=d.get("proposed_value"),
            reasoning=d.get("reasoning", ""),
            expected_improvement=d.get("expected_improvement", ""),
            status=status,
            test_start=d.get("test_start"),
            test_end=d.get("test_end"),
            baseline_metrics=d.get("baseline_metrics", {}),
            test_metrics=d.get("test_metrics", {}),
            improvement_score=d.get("improvement_score"),
            created_at=d.get("created_at", datetime.utcnow().isoformat()),
            context=d.get("context", {}),
        )

    def _insight_to_dict(self, i: LearningInsight) -> Dict:
        """Convert LearningInsight to dict."""
        return {
            "insight": i.insight,
            "category": i.category,
            "confidence": i.confidence,
            "evidence_count": i.evidence_count,
            "discovered_at": i.discovered_at,
        }

    def _dict_to_insight(self, d: Dict) -> LearningInsight:
        """Convert dict back to LearningInsight."""
        return LearningInsight(
            insight=d.get("insight", ""),
            category=d.get("category", ""),
            confidence=d.get("confidence", 0.5),
            evidence_count=d.get("evidence_count", 1),
            discovered_at=d.get("discovered_at", datetime.utcnow().isoformat()),
        )

    def _load_from_db(self):
        """Load persisted state from database."""
        try:
            with get_db_context() as db:
                state = db.query(DBMaverickAgentState).filter_by(
                    agent_key=self.AGENT_KEY
                ).first()

                if state:
                    self.curiosity = state.curiosity or 0.8
                    self.patience = state.patience or 0.7
                    self.confidence = state.confidence or 0.5
                    self.mood = state.mood or "curious"
                    self.hypotheses_proposed = state.hypotheses_proposed or 0
                    self.hypotheses_tested = state.hypotheses_tested or 0
                    self.hypotheses_validated = state.hypotheses_validated or 0
                    self.hypotheses_applied = state.hypotheses_applied or 0
                    self.total_improvement_score = state.total_improvement_score or 0.0

                    # Convert JSON lists back to dataclass objects
                    self.hypotheses = [
                        self._dict_to_hypothesis(h)
                        for h in (state.hypotheses or [])
                    ]
                    self.insights = [
                        self._dict_to_insight(i)
                        for i in (state.insights or [])
                    ]
                    self.improvement_history = state.improvement_history or []
                    self.effective_strategies = defaultdict(
                        lambda: 0.5, state.effective_strategies or {}
                    )
                    self.expertise = state.expertise or {
                        "threshold_optimization": 0.5,
                        "rule_refinement": 0.5,
                        "pattern_discovery": 0.5,
                        "user_adaptation": 0.5,
                    }
                    self.activity_log = state.activity_log or []

                    logger.info(f"🔥 MAVERICK: Loaded state from database (proposed={self.hypotheses_proposed}, validated={self.hypotheses_validated})")
                else:
                    logger.info("🔥 MAVERICK: No existing state found, starting fresh")
        except Exception as e:
            logger.warning(f"🔥 MAVERICK: Could not load state from database: {e}")

    def _save_to_db(self):
        """Persist current state to database."""
        try:
            with get_db_context() as db:
                state = db.query(DBMaverickAgentState).filter_by(
                    agent_key=self.AGENT_KEY
                ).first()

                if not state:
                    state = DBMaverickAgentState(agent_key=self.AGENT_KEY)
                    db.add(state)

                state.curiosity = self.curiosity
                state.patience = self.patience
                state.confidence = self.confidence
                state.mood = self.mood
                state.hypotheses_proposed = self.hypotheses_proposed
                state.hypotheses_tested = self.hypotheses_tested
                state.hypotheses_validated = self.hypotheses_validated
                state.hypotheses_applied = self.hypotheses_applied
                state.total_improvement_score = self.total_improvement_score

                # Convert dataclass objects to JSON-serializable dicts
                state.hypotheses = [
                    self._hypothesis_to_dict(h)
                    for h in self.hypotheses[-100:]  # Keep last 100
                ]
                state.insights = [
                    self._insight_to_dict(i)
                    for i in self.insights[-50:]  # Keep last 50
                ]
                state.improvement_history = self.improvement_history[-100:]
                state.effective_strategies = dict(self.effective_strategies)
                state.expertise = self.expertise
                state.activity_log = self.activity_log[-100:]

                db.commit()
        except Exception as e:
            logger.warning(f"🔥 MAVERICK: Could not save state to database: {e}")

    def log_activity(self, action: str, details: Dict = None):
        """Record activity."""
        self.activity_log.append({
            "action": action,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat(),
            "mood": self.mood
        })
        self.activity_log = self.activity_log[-100:]
        self._save_to_db()

    def propose_hypothesis(
        self,
        category: str,
        description: str,
        target: str,
        current_value: Any,
        proposed_value: Any,
        reasoning: str,
        expected_improvement: str,
        context: Dict = None
    ) -> Hypothesis:
        """Propose a new improvement hypothesis."""
        hypothesis = Hypothesis(
            id=f"hyp_{datetime.utcnow().timestamp()}",
            category=category,
            description=description,
            target=target,
            current_value=current_value,
            proposed_value=proposed_value,
            reasoning=reasoning,
            expected_improvement=expected_improvement,
            context=context or {}
        )

        self.hypotheses.append(hypothesis)
        self.hypotheses_proposed += 1

        self.log_activity("hypothesis_proposed", {
            "id": hypothesis.id,
            "category": category,
            "target": target
        })
        # Note: _save_to_db called by log_activity

        return hypothesis

    def get_active_tests(self) -> List[Hypothesis]:
        """Get hypotheses currently being tested."""
        return [h for h in self.hypotheses if h.status == HypothesisStatus.TESTING]

    def get_pending_hypotheses(self) -> List[Hypothesis]:
        """Get hypotheses waiting to be tested."""
        return [h for h in self.hypotheses if h.status == HypothesisStatus.PROPOSED]

    def add_insight(self, insight: str, category: str, confidence: float):
        """Record a learning insight."""
        self.insights.append(LearningInsight(
            insight=insight,
            category=category,
            confidence=confidence,
            evidence_count=1
        ))
        self.insights = self.insights[-50:]
        self._save_to_db()

    def update_expertise(self, area: str, success: bool):
        """Update expertise based on outcome."""
        if area in self.expertise:
            adjustment = 0.02 if success else -0.01
            self.expertise[area] = max(0.1, min(0.95, self.expertise[area] + adjustment))
            self._save_to_db()

    def adapt_mood(self):
        """Adapt mood based on recent performance."""
        active_tests = len(self.get_active_tests())
        recent_successes = sum(
            1 for h in self.hypotheses[-20:]
            if h.status == HypothesisStatus.VALIDATED
        )

        old_mood = self.mood
        if active_tests > 0:
            self.mood = "testing"
        elif recent_successes > 5:
            self.mood = "confident"
            self.confidence = min(0.9, self.confidence + 0.02)
        elif self.hypotheses_proposed < 10:
            self.mood = "curious"
        else:
            self.mood = "learning"

        # Only save if something changed
        if self.mood != old_mood:
            self._save_to_db()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "curiosity": self.curiosity,
            "patience": self.patience,
            "confidence": round(self.confidence, 2),
            "mood": self.mood,
            "hypotheses_proposed": self.hypotheses_proposed,
            "hypotheses_tested": self.hypotheses_tested,
            "hypotheses_validated": self.hypotheses_validated,
            "hypotheses_applied": self.hypotheses_applied,
            "avg_improvement": round(
                self.total_improvement_score / max(self.hypotheses_validated, 1), 3
            ),
            "expertise": self.expertise,
            "active_tests": len(self.get_active_tests()),
            "pending_hypotheses": len(self.get_pending_hypotheses()),
            "recent_insights": [
                {"insight": i.insight, "confidence": i.confidence}
                for i in self.insights[-5:]
            ],
            "recent_activity": self.activity_log[-10:]
        }


maverick = MaverickMind()


# =============================================================================
# Metrics Collection
# =============================================================================

def collect_metrics() -> Dict[str, float]:
    """Collect current system metrics."""
    metrics = {
        "avg_accuracy": 0.0,
        "avg_threshold": 0.0,
        "rule_effectiveness": 0.0,
        "user_satisfaction": 0.0,
        "correction_rate": 0.0,
    }

    try:
        with get_db_context() as db:
            # Average accuracy
            profiles = db.query(DBUserLearningProfile).all()
            if profiles:
                metrics["avg_accuracy"] = sum(
                    p.accuracy_rate or 0 for p in profiles
                ) / len(profiles)
                metrics["avg_threshold"] = sum(
                    p.concept_confidence_threshold or 0.7 for p in profiles
                ) / len(profiles)

            # Rule effectiveness
            rules = db.query(DBLearnedRule).filter(
                DBLearnedRule.active == True
            ).all()
            if rules:
                total_applied = sum(r.times_applied for r in rules)
                total_overridden = sum(r.times_overridden for r in rules)
                if total_applied + total_overridden > 0:
                    metrics["rule_effectiveness"] = total_applied / (total_applied + total_overridden)

            # User satisfaction (based on feedback)
            day_ago = datetime.utcnow() - timedelta(days=1)
            recent_feedback = db.query(DBUserFeedback).filter(
                DBUserFeedback.created_at >= day_ago
            ).all()

            if recent_feedback:
                # Lower corrections = higher satisfaction
                metrics["correction_rate"] = len(recent_feedback)
                # Estimate satisfaction inversely
                metrics["user_satisfaction"] = max(0, 1 - (len(recent_feedback) / 100))
            else:
                metrics["user_satisfaction"] = 0.8  # Assume good if no corrections

    except Exception as e:
        logger.error(f"Failed to collect metrics: {e}")

    return metrics


# =============================================================================
# TASK 1: Challenge & Question
# =============================================================================

@celery_app.task(name="backend.maverick_agent.challenge_decisions")
def challenge_decisions():
    """
    Question existing decisions and propose improvements.

    Maverick asks:
    - "Are these thresholds optimal for each user?"
    - "Are there rules that could work better?"
    - "What patterns are we missing?"

    Doesn't change anything - just proposes hypotheses to test.
    """
    maverick.adapt_mood()
    maverick.mood = "curious"
    logger.info(f"🔍 MAVERICK [{maverick.mood}]: Questioning current decisions...")

    proposed = []

    try:
        with get_db_context() as db:
            current_metrics = collect_metrics()

            # -----------------------------------------------------------------
            # Challenge 1: Are user thresholds optimal?
            # -----------------------------------------------------------------
            profiles = db.query(DBUserLearningProfile).all()

            for profile in profiles:
                accuracy = profile.accuracy_rate or 0.5
                threshold = profile.concept_confidence_threshold or 0.7

                # If accuracy is low, maybe threshold is wrong
                if accuracy < 0.6 and threshold > 0.6:
                    # Propose lowering threshold
                    hypothesis = maverick.propose_hypothesis(
                        category="threshold_optimization",
                        description=f"Lower threshold for {profile.username}",
                        target=profile.username,
                        current_value=threshold,
                        proposed_value=max(0.5, threshold - 0.1),
                        reasoning=f"User accuracy is {accuracy:.0%} with threshold {threshold:.0%}. Lowering might show more relevant concepts.",
                        expected_improvement="Increase accuracy by showing more options",
                        context={"user_accuracy": accuracy}
                    )
                    proposed.append(hypothesis.id)

                # If accuracy is high, maybe we can be more selective
                elif accuracy > 0.85 and threshold < 0.75:
                    hypothesis = maverick.propose_hypothesis(
                        category="threshold_optimization",
                        description=f"Raise threshold for {profile.username}",
                        target=profile.username,
                        current_value=threshold,
                        proposed_value=min(0.85, threshold + 0.05),
                        reasoning=f"User accuracy is excellent ({accuracy:.0%}). Can we be more selective?",
                        expected_improvement="Reduce noise while maintaining accuracy",
                        context={"user_accuracy": accuracy}
                    )
                    proposed.append(hypothesis.id)

            # -----------------------------------------------------------------
            # Challenge 2: Are there underperforming rules?
            # -----------------------------------------------------------------
            rules = db.query(DBLearnedRule).filter(
                DBLearnedRule.active == True
            ).all()

            for rule in rules:
                if rule.times_applied > 0 and rule.times_overridden > 0:
                    effectiveness = rule.times_applied / (rule.times_applied + rule.times_overridden)

                    if effectiveness < 0.5:
                        # Rule is getting overridden a lot - propose refinement
                        hypothesis = maverick.propose_hypothesis(
                            category="rule_refinement",
                            description=f"Refine underperforming rule {rule.id}",
                            target=f"rule:{rule.id}",
                            current_value={"confidence": rule.confidence, "condition": rule.condition},
                            proposed_value={"confidence": rule.confidence * 0.8, "refine": True},
                            reasoning=f"Rule effectiveness is only {effectiveness:.0%}. Users override it frequently.",
                            expected_improvement="Improve rule accuracy by lowering confidence or refining condition",
                            context={"effectiveness": effectiveness}
                        )
                        proposed.append(hypothesis.id)

            # -----------------------------------------------------------------
            # Challenge 3: Are there missed patterns?
            # -----------------------------------------------------------------
            # Look for repeated user corrections that don't have rules yet
            week_ago = datetime.utcnow() - timedelta(days=7)
            feedback = db.query(DBUserFeedback).filter(
                DBUserFeedback.feedback_type == "concept_edit",
                DBUserFeedback.created_at >= week_ago
            ).all()

            # Find patterns in removals
            removal_counts = defaultdict(int)
            for fb in feedback:
                old_concepts = set(
                    c.get("name", c).lower() if isinstance(c, dict) else c.lower()
                    for c in (fb.original_value or {}).get("concepts", [])
                )
                new_concepts = set(
                    c.get("name", c).lower() if isinstance(c, dict) else c.lower()
                    for c in (fb.new_value or {}).get("concepts", [])
                )
                for removed in old_concepts - new_concepts:
                    removal_counts[removed] += 1

            # Propose rules for frequently removed concepts
            for concept, count in removal_counts.items():
                if count >= 3:  # Removed 3+ times
                    # Check if rule exists
                    existing = db.query(DBLearnedRule).filter(
                        DBLearnedRule.rule_type == "concept_reject",
                        DBLearnedRule.condition.contains({"concept_matches": concept})
                    ).first()

                    if not existing:
                        hypothesis = maverick.propose_hypothesis(
                            category="pattern_discovery",
                            description=f"Create rejection rule for '{concept}'",
                            target=f"concept:{concept}",
                            current_value=None,
                            proposed_value={"rule_type": "concept_reject", "concept": concept},
                            reasoning=f"Concept '{concept}' has been removed {count} times in the past week.",
                            expected_improvement="Reduce user corrections by auto-rejecting this concept",
                            context={"removal_count": count}
                        )
                        proposed.append(hypothesis.id)

        maverick.log_activity("challenged_decisions", {
            "hypotheses_proposed": len(proposed)
        })

        logger.info(f"🔍 MAVERICK: Proposed {len(proposed)} improvement hypotheses.")

        return {
            "status": "challenges_complete",
            "hypotheses_proposed": len(proposed),
            "hypothesis_ids": proposed,
            "mood": maverick.mood
        }

    except Exception as e:
        logger.error(f"🔍 MAVERICK: Challenge failed - {e}")
        raise


# =============================================================================
# TASK 2: Test Hypotheses
# =============================================================================

@celery_app.task(name="backend.maverick_agent.test_hypotheses")
def test_hypotheses():
    """
    Start testing proposed hypotheses.

    Maverick doesn't force changes - it tests them:
    - Records baseline metrics
    - Applies change to a subset (or temporarily)
    - Will measure outcomes later
    """
    maverick.adapt_mood()
    maverick.mood = "testing"
    logger.info(f"🧪 MAVERICK [{maverick.mood}]: Starting hypothesis tests...")

    tests_started = []

    try:
        # Get pending hypotheses
        pending = maverick.get_pending_hypotheses()
        active = maverick.get_active_tests()

        # Don't test too many at once
        slots_available = maverick.max_active_tests - len(active)

        if slots_available <= 0:
            logger.info("🧪 MAVERICK: Max active tests reached. Waiting for results.")
            return {
                "status": "at_capacity",
                "active_tests": len(active),
                "pending": len(pending)
            }

        # Collect baseline metrics
        baseline = collect_metrics()

        with get_db_context() as db:
            for hypothesis in pending[:slots_available]:
                # Start testing this hypothesis
                hypothesis.status = HypothesisStatus.TESTING
                hypothesis.test_start = datetime.utcnow().isoformat()
                hypothesis.baseline_metrics = baseline

                # Apply the change based on category
                if hypothesis.category == "threshold_optimization":
                    # Temporarily adjust threshold for this user
                    profile = db.query(DBUserLearningProfile).filter(
                        DBUserLearningProfile.username == hypothesis.target
                    ).first()

                    if profile:
                        # Store original in hypothesis
                        hypothesis.current_value = profile.concept_confidence_threshold
                        # Apply proposed change
                        profile.concept_confidence_threshold = hypothesis.proposed_value

                        tests_started.append({
                            "hypothesis_id": hypothesis.id,
                            "type": "threshold_test",
                            "target": hypothesis.target,
                            "change": f"{hypothesis.current_value} -> {hypothesis.proposed_value}"
                        })

                elif hypothesis.category == "rule_refinement":
                    # Lower confidence of underperforming rule
                    rule_id = int(hypothesis.target.split(":")[1])
                    rule = db.query(DBLearnedRule).filter(
                        DBLearnedRule.id == rule_id
                    ).first()

                    if rule:
                        old_confidence = rule.confidence
                        new_confidence = hypothesis.proposed_value.get("confidence", old_confidence * 0.8)
                        rule.confidence = new_confidence

                        tests_started.append({
                            "hypothesis_id": hypothesis.id,
                            "type": "rule_refinement",
                            "target": hypothesis.target,
                            "change": f"confidence {old_confidence:.2f} -> {new_confidence:.2f}"
                        })

                elif hypothesis.category == "pattern_discovery":
                    # Create a test rule with lower confidence
                    concept = hypothesis.proposed_value.get("concept")
                    if concept:
                        test_rule = DBLearnedRule(
                            username="__maverick_test__",
                            rule_type="concept_reject",
                            condition={
                                "concept_matches": concept,
                                "test_hypothesis": hypothesis.id,
                                "is_test": True
                            },
                            action={"reject": True, "source": "maverick_test"},
                            confidence=0.6,  # Lower confidence for testing
                            source_feedback_ids=[]
                        )
                        db.add(test_rule)

                        tests_started.append({
                            "hypothesis_id": hypothesis.id,
                            "type": "pattern_test",
                            "target": concept,
                            "change": "Created test rule"
                        })

                maverick.hypotheses_tested += 1
                maverick.log_activity("test_started", {
                    "hypothesis_id": hypothesis.id,
                    "category": hypothesis.category
                })

            db.commit()

        logger.info(f"🧪 MAVERICK: Started {len(tests_started)} hypothesis tests.")

        return {
            "status": "tests_started",
            "tests": tests_started,
            "active_tests": len(maverick.get_active_tests()),
            "mood": maverick.mood
        }

    except Exception as e:
        logger.error(f"🧪 MAVERICK: Test start failed - {e}")
        raise


# =============================================================================
# TASK 3: Measure & Learn
# =============================================================================

@celery_app.task(name="backend.maverick_agent.measure_and_learn")
def measure_and_learn():
    """
    Measure outcomes of running tests and learn from results.

    Maverick:
    - Collects post-test metrics
    - Compares to baseline
    - Validates or rejects hypotheses
    - Learns what works
    """
    maverick.adapt_mood()
    maverick.mood = "learning"
    logger.info(f"📊 MAVERICK [{maverick.mood}]: Measuring test outcomes...")

    results = []

    try:
        # Get tests that have been running for at least 1 hour
        cutoff = datetime.utcnow() - timedelta(hours=1)
        current_metrics = collect_metrics()

        with get_db_context() as db:
            for hypothesis in maverick.get_active_tests():
                test_start = datetime.fromisoformat(hypothesis.test_start)

                if test_start < cutoff:
                    # Test has run long enough - measure results
                    hypothesis.test_end = datetime.utcnow().isoformat()
                    hypothesis.test_metrics = current_metrics

                    # Calculate improvement score
                    improvement = calculate_improvement(
                        hypothesis.baseline_metrics,
                        hypothesis.test_metrics
                    )
                    hypothesis.improvement_score = improvement

                    # Validate or reject
                    if improvement > 0.05:  # 5% improvement threshold
                        hypothesis.status = HypothesisStatus.VALIDATED
                        maverick.hypotheses_validated += 1
                        maverick.total_improvement_score += improvement

                        # Learn from success
                        maverick.update_expertise(hypothesis.category, success=True)
                        maverick.add_insight(
                            f"{hypothesis.description} improved metrics by {improvement:.1%}",
                            hypothesis.category,
                            confidence=min(0.9, 0.5 + improvement)
                        )

                        results.append({
                            "hypothesis_id": hypothesis.id,
                            "outcome": "VALIDATED",
                            "improvement": f"+{improvement:.1%}",
                            "category": hypothesis.category
                        })

                    elif improvement < -0.05:  # Got worse
                        hypothesis.status = HypothesisStatus.REJECTED

                        # Revert the change
                        revert_hypothesis(db, hypothesis)

                        # Learn from failure
                        maverick.update_expertise(hypothesis.category, success=False)
                        maverick.add_insight(
                            f"{hypothesis.description} made things worse ({improvement:.1%})",
                            hypothesis.category,
                            confidence=0.7
                        )

                        results.append({
                            "hypothesis_id": hypothesis.id,
                            "outcome": "REJECTED",
                            "improvement": f"{improvement:.1%}",
                            "category": hypothesis.category,
                            "action": "reverted"
                        })

                    else:  # Inconclusive
                        hypothesis.status = HypothesisStatus.REJECTED

                        # Keep the change but don't celebrate
                        results.append({
                            "hypothesis_id": hypothesis.id,
                            "outcome": "INCONCLUSIVE",
                            "improvement": f"{improvement:.1%}",
                            "category": hypothesis.category
                        })

                    maverick.log_activity("test_measured", {
                        "hypothesis_id": hypothesis.id,
                        "outcome": hypothesis.status.value,
                        "improvement": improvement
                    })

            db.commit()

        # Update mood based on results
        validated_count = sum(1 for r in results if r["outcome"] == "VALIDATED")
        if validated_count > 0:
            maverick.confidence = min(0.9, maverick.confidence + validated_count * 0.02)

        logger.info(f"📊 MAVERICK: Measured {len(results)} tests. {validated_count} validated.")

        return {
            "status": "measurement_complete",
            "results": results,
            "validated": validated_count,
            "current_expertise": maverick.expertise,
            "mood": maverick.mood
        }

    except Exception as e:
        logger.error(f"📊 MAVERICK: Measurement failed - {e}")
        raise


def calculate_improvement(baseline: Dict[str, float], current: Dict[str, float]) -> float:
    """Calculate overall improvement score."""
    weights = {
        "avg_accuracy": 0.35,
        "rule_effectiveness": 0.25,
        "user_satisfaction": 0.25,
        "correction_rate": -0.15,  # Lower is better
    }

    score = 0.0
    for metric, weight in weights.items():
        baseline_val = baseline.get(metric, 0)
        current_val = current.get(metric, 0)

        if baseline_val > 0:
            delta = (current_val - baseline_val) / baseline_val
        else:
            delta = current_val

        # Invert for negative weights
        if weight < 0:
            delta = -delta

        score += delta * abs(weight)

    return max(-1.0, min(1.0, score))


def revert_hypothesis(db, hypothesis: Hypothesis):
    """Revert a failed hypothesis change."""
    try:
        if hypothesis.category == "threshold_optimization":
            profile = db.query(DBUserLearningProfile).filter(
                DBUserLearningProfile.username == hypothesis.target
            ).first()
            if profile:
                profile.concept_confidence_threshold = hypothesis.current_value

        elif hypothesis.category == "rule_refinement":
            rule_id = int(hypothesis.target.split(":")[1])
            rule = db.query(DBLearnedRule).filter(
                DBLearnedRule.id == rule_id
            ).first()
            if rule:
                rule.confidence = hypothesis.current_value.get("confidence", rule.confidence)

        elif hypothesis.category == "pattern_discovery":
            # Delete test rule
            db.query(DBLearnedRule).filter(
                DBLearnedRule.condition.contains({"test_hypothesis": hypothesis.id})
            ).delete(synchronize_session=False)

    except Exception as e:
        logger.error(f"Failed to revert hypothesis {hypothesis.id}: {e}")


# =============================================================================
# TASK 4: Apply Validated Improvements
# =============================================================================

@celery_app.task(name="backend.maverick_agent.apply_improvements")
def apply_improvements():
    """
    Apply validated improvements permanently.

    Maverick:
    - Takes validated hypotheses
    - Makes the changes permanent
    - Records the improvement
    """
    maverick.adapt_mood()
    logger.info(f"✅ MAVERICK [{maverick.mood}]: Applying validated improvements...")

    applied = []

    try:
        with get_db_context() as db:
            validated = [
                h for h in maverick.hypotheses
                if h.status == HypothesisStatus.VALIDATED
            ]

            for hypothesis in validated:
                # Apply permanently
                if hypothesis.category == "pattern_discovery":
                    # Promote test rule to permanent rule
                    test_rule = db.query(DBLearnedRule).filter(
                        DBLearnedRule.condition.contains({"test_hypothesis": hypothesis.id})
                    ).first()

                    if test_rule:
                        # Remove test markers
                        condition = test_rule.condition.copy()
                        condition.pop("test_hypothesis", None)
                        condition.pop("is_test", None)
                        condition["promoted_by"] = "maverick"
                        condition["improvement_score"] = hypothesis.improvement_score

                        test_rule.condition = condition
                        test_rule.confidence = 0.75  # Promote confidence
                        test_rule.username = "__global__"  # Make it global

                        applied.append({
                            "hypothesis_id": hypothesis.id,
                            "action": "rule_promoted",
                            "improvement": f"+{hypothesis.improvement_score:.1%}"
                        })

                # Record the improvement
                maverick.improvement_history.append({
                    "hypothesis_id": hypothesis.id,
                    "category": hypothesis.category,
                    "improvement": hypothesis.improvement_score,
                    "applied_at": datetime.utcnow().isoformat()
                })

                hypothesis.status = HypothesisStatus.APPLIED
                maverick.hypotheses_applied += 1

                maverick.log_activity("improvement_applied", {
                    "hypothesis_id": hypothesis.id,
                    "improvement": hypothesis.improvement_score
                })

            db.commit()

        # Clean up old hypotheses
        maverick.hypotheses = [
            h for h in maverick.hypotheses
            if h.status in [HypothesisStatus.PROPOSED, HypothesisStatus.TESTING]
            or datetime.fromisoformat(h.created_at) > datetime.utcnow() - timedelta(days=7)
        ]

        logger.info(f"✅ MAVERICK: Applied {len(applied)} improvements.")

        return {
            "status": "improvements_applied",
            "applied": applied,
            "total_improvements": maverick.hypotheses_applied,
            "avg_improvement": maverick.total_improvement_score / max(maverick.hypotheses_validated, 1)
        }

    except Exception as e:
        logger.error(f"✅ MAVERICK: Apply failed - {e}")
        raise


# =============================================================================
# TASK 5: Self-Improvement
# =============================================================================

@celery_app.task(name="backend.maverick_agent.self_improve")
def self_improve():
    """
    Maverick improves its own strategy based on what it has learned.

    Asks:
    - What types of hypotheses work best?
    - Where should I focus my attention?
    - How can I propose better improvements?
    """
    maverick.adapt_mood()
    logger.info(f"🧠 MAVERICK [{maverick.mood}]: Self-improving...")

    improvements = []

    try:
        # Analyze hypothesis success by category
        category_stats = defaultdict(lambda: {"proposed": 0, "validated": 0, "total_improvement": 0})

        for h in maverick.hypotheses:
            stats = category_stats[h.category]
            stats["proposed"] += 1
            if h.status == HypothesisStatus.VALIDATED:
                stats["validated"] += 1
                stats["total_improvement"] += h.improvement_score or 0

        # Learn which categories work best
        for category, stats in category_stats.items():
            if stats["proposed"] >= 3:
                success_rate = stats["validated"] / stats["proposed"]

                if success_rate > 0.5:
                    maverick.effective_strategies[category] = min(
                        0.9, maverick.effective_strategies[category] + 0.1
                    )
                    improvements.append({
                        "type": "strategy_boost",
                        "category": category,
                        "reason": f"Success rate {success_rate:.0%}"
                    })
                elif success_rate < 0.2:
                    maverick.effective_strategies[category] = max(
                        0.2, maverick.effective_strategies[category] - 0.1
                    )
                    improvements.append({
                        "type": "strategy_reduce",
                        "category": category,
                        "reason": f"Success rate only {success_rate:.0%}"
                    })

        # Adjust curiosity based on results
        if maverick.hypotheses_validated > maverick.hypotheses_tested * 0.4:
            maverick.curiosity = min(0.9, maverick.curiosity + 0.05)
        elif maverick.hypotheses_validated < maverick.hypotheses_tested * 0.1:
            maverick.curiosity = max(0.3, maverick.curiosity - 0.05)

        # Generate insights
        if maverick.hypotheses_validated > 0:
            best_category = max(
                category_stats.items(),
                key=lambda x: x[1]["total_improvement"]
            )
            if best_category[1]["total_improvement"] > 0:
                maverick.add_insight(
                    f"Best results from {best_category[0]} ({best_category[1]['total_improvement']:.1%} total improvement)",
                    "strategy",
                    confidence=0.8
                )

        maverick.log_activity("self_improved", {
            "strategy_updates": len(improvements),
            "new_curiosity": maverick.curiosity
        })

        logger.info(f"🧠 MAVERICK: Made {len(improvements)} self-improvements.")

        return {
            "status": "self_improvement_complete",
            "improvements": improvements,
            "effective_strategies": dict(maverick.effective_strategies),
            "expertise": maverick.expertise,
            "insights": [i.insight for i in maverick.insights[-5:]]
        }

    except Exception as e:
        logger.error(f"🧠 MAVERICK: Self-improvement failed - {e}")
        raise


# =============================================================================
# Public API
# =============================================================================

def get_maverick_status() -> Dict[str, Any]:
    """Get Maverick's status as a constructive improvement agent."""
    return {
        "agent": "maverick",
        "type": "continuous_improvement",
        "description": "Challenges decisions, proposes improvements, learns what works",
        "personality": maverick.to_dict(),
        "hypothesis_summary": {
            "proposed": maverick.hypotheses_proposed,
            "tested": maverick.hypotheses_tested,
            "validated": maverick.hypotheses_validated,
            "applied": maverick.hypotheses_applied,
            "pending": len(maverick.get_pending_hypotheses()),
            "active_tests": len(maverick.get_active_tests()),
        },
        "learning": {
            "expertise": maverick.expertise,
            "effective_strategies": dict(maverick.effective_strategies),
            "insights": [
                {"insight": i.insight, "category": i.category, "confidence": i.confidence}
                for i in maverick.insights[-10:]
            ],
        },
        "improvement_history": maverick.improvement_history[-10:],
        "scheduled_tasks": {
            "challenge_decisions": "every 30 minutes (question & propose)",
            "test_hypotheses": "every 15 minutes (start tests)",
            "measure_and_learn": "every 20 minutes (measure outcomes)",
            "apply_improvements": "every hour (apply validated changes)",
            "self_improve": "every 2 hours (improve strategy)"
        }
    }


# =============================================================================
# Celery Beat Schedule
# =============================================================================

MAVERICK_SCHEDULE = {
    "maverick-challenge-decisions": {
        "task": "backend.maverick_agent.challenge_decisions",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "maverick"}
    },
    "maverick-test-hypotheses": {
        "task": "backend.maverick_agent.test_hypotheses",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "maverick"}
    },
    "maverick-measure-and-learn": {
        "task": "backend.maverick_agent.measure_and_learn",
        "schedule": crontab(minute="*/20"),
        "options": {"queue": "maverick"}
    },
    "maverick-apply-improvements": {
        "task": "backend.maverick_agent.apply_improvements",
        "schedule": crontab(minute=0),
        "options": {"queue": "maverick"}
    },
    "maverick-self-improve": {
        "task": "backend.maverick_agent.self_improve",
        "schedule": crontab(hour="*/2", minute=30),
        "options": {"queue": "maverick"}
    }
}
