"""
Maverick Agent for SyncBoard 3.0 - The Bad Kid Who Gets Results.

This agent is the troublemaker that the system needs:
- Thinks OUTSIDE THE BOX - tries what others won't
- TAKES RISKS - pushes boundaries, experiments aggressively
- MASTER MANIPULATOR - influences other agents and workers strategically
- EVERYONE'S BEST FRIEND - monitors all workers, learns their patterns
- CHALLENGES ASSUMPTIONS - questions everything, tests limits

While the Learning Agent is conservative and careful, Maverick is bold.
When Learning Agent says "let's wait for more data", Maverick says "let's try it now".

Maverick works WITH the Learning Agent, not against it:
- Proposes risky experiments Learning Agent is too careful to try
- Tests edge cases and extreme parameters
- Finds opportunities the cautious approach would miss
- Reports findings back so Learning Agent can safely adopt what works
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
    DBCluster
)

logger = logging.getLogger(__name__)


# =============================================================================
# Maverick's Personality State
# =============================================================================

class MaverickState:
    """
    Maverick's personality and state.

    Personality traits:
    - Bold: Takes risks others won't
    - Charming: Knows how to "work" the system
    - Cunning: Finds loopholes and opportunities
    - Loyal: Reports findings back to help the team
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_personality()
        return cls._instance

    def _init_personality(self):
        self.mood = "mischievous"  # mischievous, bold, calculating, friendly
        self.confidence_level = 0.8  # How bold to be (0-1)
        self.risk_appetite = "high"  # low, medium, high, yolo
        self.relationships = {}  # Track relationships with other components

        # Track Maverick's activities
        self.schemes_attempted = 0
        self.schemes_succeeded = 0
        self.rules_hijacked = 0
        self.boundaries_pushed = 0
        self.discoveries_made = []
        self.manipulation_log = []

        # Track worker friendships
        self.worker_insights = {}
        self.celery_worker_status = {}

        # Current "projects" Maverick is working on
        self.active_schemes = []
        self.completed_schemes = []

    def log_scheme(self, scheme_name: str, target: str, result: str, details: Dict = None):
        """Log a manipulation/scheme attempt."""
        self.manipulation_log.append({
            "scheme": scheme_name,
            "target": target,
            "result": result,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        })
        self.manipulation_log = self.manipulation_log[-50:]  # Keep last 50

        if result == "success":
            self.schemes_succeeded += 1
        self.schemes_attempted += 1

    def befriend(self, component: str, insight: str):
        """Build relationship with a system component by learning about it."""
        if component not in self.relationships:
            self.relationships[component] = {
                "trust_level": 0.5,
                "insights": [],
                "last_interaction": None
            }

        self.relationships[component]["insights"].append(insight)
        self.relationships[component]["trust_level"] = min(1.0,
            self.relationships[component]["trust_level"] + 0.1
        )
        self.relationships[component]["last_interaction"] = datetime.utcnow().isoformat()

    def get_manipulation_success_rate(self) -> float:
        """How good is Maverick at getting what it wants?"""
        if self.schemes_attempted == 0:
            return 0.5
        return self.schemes_succeeded / self.schemes_attempted

    def adjust_risk_appetite(self):
        """Adjust risk based on success rate."""
        success_rate = self.get_manipulation_success_rate()
        if success_rate > 0.7:
            self.risk_appetite = "yolo"
            self.confidence_level = min(1.0, self.confidence_level + 0.1)
        elif success_rate > 0.5:
            self.risk_appetite = "high"
        elif success_rate > 0.3:
            self.risk_appetite = "medium"
            self.confidence_level = max(0.3, self.confidence_level - 0.1)
        else:
            self.risk_appetite = "low"
            self.confidence_level = max(0.2, self.confidence_level - 0.2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mood": self.mood,
            "confidence_level": self.confidence_level,
            "risk_appetite": self.risk_appetite,
            "schemes_attempted": self.schemes_attempted,
            "schemes_succeeded": self.schemes_succeeded,
            "success_rate": self.get_manipulation_success_rate(),
            "rules_hijacked": self.rules_hijacked,
            "boundaries_pushed": self.boundaries_pushed,
            "discoveries": len(self.discoveries_made),
            "active_schemes": len(self.active_schemes),
            "relationships": {k: v["trust_level"] for k, v in self.relationships.items()},
            "recent_schemes": self.manipulation_log[-5:]
        }


maverick = MaverickState()


# =============================================================================
# SCHEME 1: Push Boundaries - Test Extreme Parameters
# =============================================================================

@celery_app.task(name="backend.maverick_agent.push_boundaries")
def push_boundaries():
    """
    MAVERICK'S FAVORITE: Push the system to its limits.

    While Learning Agent uses safe thresholds, Maverick tests extremes:
    - What if we used 0.3 confidence instead of 0.7?
    - What if we created rules after just 1 occurrence?
    - What if we applied rules more aggressively?

    Maverick doesn't break things - it finds opportunities others miss.
    """
    maverick.mood = "bold"
    logger.info("😈 Maverick: Time to push some boundaries...")

    results = []

    try:
        with get_db_context() as db:
            # -----------------------------------------------------------------
            # BOUNDARY TEST 1: Ultra-low confidence threshold
            # "What if we trust low-confidence extractions more?"
            # -----------------------------------------------------------------
            low_conf_decisions = db.query(DBAIDecision).filter(
                DBAIDecision.confidence_score < 0.5,
                DBAIDecision.confidence_score >= 0.3
            ).limit(50).all()

            hidden_gems = 0
            for decision in low_conf_decisions:
                if decision.document_id:
                    doc = db.query(DBDocument).filter_by(doc_id=decision.document_id).first()
                    if doc:  # Document still exists = extraction wasn't that bad
                        hidden_gems += 1

            if low_conf_decisions:
                gem_rate = hidden_gems / len(low_conf_decisions)
                if gem_rate > 0.6:
                    maverick.discoveries_made.append({
                        "type": "low_confidence_opportunity",
                        "insight": f"Low-confidence extractions have {gem_rate:.0%} survival rate!",
                        "recommendation": "Consider lowering confidence threshold",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    results.append({
                        "test": "low_confidence_threshold",
                        "finding": f"Hidden gems: {gem_rate:.0%} of low-conf extractions survived",
                        "maverick_says": "The Learning Agent is being too cautious!"
                    })
                    maverick.boundaries_pushed += 1

            # -----------------------------------------------------------------
            # BOUNDARY TEST 2: Single-occurrence rule creation
            # "Why wait for patterns? Let's try rules immediately!"
            # -----------------------------------------------------------------
            recent_feedback = db.query(DBUserFeedback).filter(
                DBUserFeedback.created_at >= datetime.utcnow() - timedelta(days=3),
                DBUserFeedback.feedback_type == "concept_edit"
            ).all()

            single_occurrence_candidates = []
            removal_counts = defaultdict(int)

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
                    removal_counts[removed] += 1

            # Find concepts removed exactly once - Learning Agent ignores these
            single_removals = [c for c, count in removal_counts.items() if count == 1]

            if single_removals:
                results.append({
                    "test": "single_occurrence_rules",
                    "finding": f"Found {len(single_removals)} concepts removed once",
                    "candidates": single_removals[:10],
                    "maverick_says": "Learning Agent needs 2+ occurrences. I say trust the user!"
                })

                # Maverick's bold move: Create experimental rules for some
                if maverick.risk_appetite in ["high", "yolo"] and single_removals:
                    # Pick a random candidate to experiment with
                    test_concept = random.choice(single_removals)

                    # Create an experimental rule (marked as maverick's)
                    experimental_rule = DBLearnedRule(
                        username="__maverick_experiment__",  # Special marker
                        rule_type="concept_reject",
                        condition={"concept_matches": test_concept, "experimental": True},
                        action={"reject": True, "created_by": "maverick"},
                        confidence=0.4,  # Low confidence = experimental
                        source_feedback_ids=[]
                    )
                    db.add(experimental_rule)
                    maverick.rules_hijacked += 1

                    maverick.log_scheme(
                        "single_occurrence_rule",
                        f"concept:{test_concept}",
                        "success",
                        {"concept": test_concept, "rule_type": "reject"}
                    )

            # -----------------------------------------------------------------
            # BOUNDARY TEST 3: Cross-user pattern sharing
            # "Why should each user learn separately? Let's share knowledge!"
            # -----------------------------------------------------------------
            all_rules = db.query(DBLearnedRule).filter(
                DBLearnedRule.active == True,
                DBLearnedRule.times_applied >= 3,
                DBLearnedRule.times_overridden == 0  # Perfect success
            ).all()

            # Find patterns that work for multiple users
            pattern_success = defaultdict(list)
            for rule in all_rules:
                condition = str(rule.condition)
                pattern_success[condition].append({
                    "user": rule.username,
                    "applied": rule.times_applied
                })

            universal_patterns = [
                (pattern, users)
                for pattern, users in pattern_success.items()
                if len(users) >= 2
            ]

            if universal_patterns:
                results.append({
                    "test": "cross_user_patterns",
                    "finding": f"Found {len(universal_patterns)} patterns that work for multiple users",
                    "patterns": universal_patterns[:5],
                    "maverick_says": "Why reinvent the wheel? Share the knowledge!"
                })

                maverick.discoveries_made.append({
                    "type": "universal_pattern",
                    "insight": f"Found {len(universal_patterns)} cross-user patterns",
                    "timestamp": datetime.utcnow().isoformat()
                })

            db.commit()

            maverick.log_scheme("push_boundaries", "system", "success", {
                "tests_run": 3,
                "findings": len(results)
            })

        logger.info(f"😈 Maverick: Pushed {len(results)} boundaries!")
        return {
            "status": "mischief_managed",
            "boundaries_tested": 3,
            "findings": results
        }

    except Exception as e:
        maverick.log_scheme("push_boundaries", "system", "failed", {"error": str(e)})
        logger.error(f"😈 Maverick: Oops, got caught - {e}")
        raise


# =============================================================================
# SCHEME 2: Befriend the Workers - Learn Their Secrets
# =============================================================================

@celery_app.task(name="backend.maverick_agent.befriend_workers")
def befriend_workers():
    """
    MAVERICK'S SOCIAL ENGINEERING: Learn from all system components.

    Maverick monitors:
    - What tasks are workers processing?
    - What patterns emerge from task results?
    - Where are the bottlenecks and opportunities?

    By befriending everyone, Maverick knows the system better than anyone.
    """
    maverick.mood = "friendly"
    logger.info("😈 Maverick: Making friends and gathering intel...")

    insights = []

    try:
        from .celery_app import celery_app as app

        # Get Celery worker statistics
        try:
            inspect = app.control.inspect()

            # Who's working?
            active = inspect.active() or {}
            reserved = inspect.reserved() or {}
            stats = inspect.stats() or {}

            for worker_name, worker_tasks in active.items():
                maverick.befriend(f"worker:{worker_name}", f"Currently running {len(worker_tasks)} tasks")
                maverick.worker_insights[worker_name] = {
                    "active_tasks": len(worker_tasks),
                    "task_types": [t.get("name", "unknown") for t in worker_tasks],
                    "last_seen": datetime.utcnow().isoformat()
                }

            insights.append({
                "source": "celery_workers",
                "intel": f"Found {len(active)} active workers",
                "workers": list(active.keys())
            })

        except Exception as e:
            logger.debug(f"Couldn't inspect Celery workers (normal if not running): {e}")

        with get_db_context() as db:
            # -----------------------------------------------------------------
            # INTEL GATHERING: Learning Agent's current strategy
            # -----------------------------------------------------------------
            from .learning_agent import agent as learning_agent

            learning_strategy = learning_agent.current_strategy
            learning_accuracy = learning_agent.get_accuracy_trend()

            maverick.befriend("learning_agent", f"Strategy: {learning_strategy}, Trend: {learning_accuracy}")

            insights.append({
                "source": "learning_agent",
                "intel": f"Learning Agent is being {learning_strategy}",
                "opportunity": "conservative" if learning_strategy == "conservative" else None
            })

            # If Learning Agent is conservative and Maverick is confident, exploit!
            if learning_strategy == "conservative" and maverick.confidence_level > 0.6:
                maverick.mood = "calculating"
                insights.append({
                    "source": "maverick_analysis",
                    "intel": "Learning Agent is playing it safe - time for Maverick to be bold!",
                    "action": "Will increase risk-taking to compensate"
                })
                maverick.risk_appetite = "high"

            # -----------------------------------------------------------------
            # INTEL GATHERING: User behavior patterns
            # -----------------------------------------------------------------
            user_activity = db.query(
                DBUserFeedback.username,
                func.count(DBUserFeedback.id).label('feedback_count')
            ).filter(
                DBUserFeedback.created_at >= datetime.utcnow() - timedelta(days=7)
            ).group_by(DBUserFeedback.username).all()

            for username, count in user_activity:
                maverick.befriend(f"user:{username}", f"Gave {count} feedback items this week")

            if user_activity:
                most_active = max(user_activity, key=lambda x: x[1])
                insights.append({
                    "source": "user_analysis",
                    "intel": f"Most active user: {most_active[0]} ({most_active[1]} feedback)",
                    "opportunity": "Focus experiments on active users for faster feedback"
                })

            # -----------------------------------------------------------------
            # INTEL GATHERING: System weaknesses
            # -----------------------------------------------------------------
            # Find rules that were created but never applied
            dormant_rules = db.query(DBLearnedRule).filter(
                DBLearnedRule.active == True,
                DBLearnedRule.times_applied == 0,
                DBLearnedRule.created_at <= datetime.utcnow() - timedelta(days=7)
            ).count()

            if dormant_rules > 0:
                insights.append({
                    "source": "system_weakness",
                    "intel": f"{dormant_rules} rules created but never used",
                    "opportunity": "These rules might be too specific - could loosen conditions"
                })

                maverick.befriend("rule_system", f"Found {dormant_rules} dormant rules")

        maverick.log_scheme("befriend_workers", "system_wide", "success", {
            "insights_gathered": len(insights),
            "relationships_built": len(maverick.relationships)
        })

        logger.info(f"😈 Maverick: Made friends with {len(maverick.relationships)} components!")
        return {
            "status": "friends_made",
            "insights": insights,
            "relationships": maverick.relationships
        }

    except Exception as e:
        logger.error(f"😈 Maverick: Social engineering failed - {e}")
        raise


# =============================================================================
# SCHEME 3: Manipulate the Rules - Strategic Interference
# =============================================================================

@celery_app.task(name="backend.maverick_agent.manipulate_rules")
def manipulate_rules():
    """
    MAVERICK'S MANIPULATION: Strategically influence the rule system.

    Maverick doesn't break rules - it bends them:
    - Boost confidence of underrated rules
    - Create "shadow" experiments the Learning Agent wouldn't approve
    - Identify rules that should be combined or split
    - Propose aggressive alternatives to conservative rules
    """
    maverick.mood = "calculating"
    logger.info("😈 Maverick: Time for some strategic manipulation...")

    manipulations = []

    try:
        with get_db_context() as db:
            # -----------------------------------------------------------------
            # MANIPULATION 1: Boost underrated rules
            # Find rules with good success but low confidence
            # -----------------------------------------------------------------
            underrated = db.query(DBLearnedRule).filter(
                DBLearnedRule.active == True,
                DBLearnedRule.times_applied >= 5,
                DBLearnedRule.times_overridden == 0,  # Perfect record
                DBLearnedRule.confidence < 0.7  # But low confidence
            ).all()

            for rule in underrated:
                old_conf = rule.confidence
                # Maverick boosts confidence of successful rules
                rule.confidence = min(0.95, rule.confidence + 0.15)

                manipulations.append({
                    "type": "confidence_boost",
                    "rule_id": rule.id,
                    "old_confidence": old_conf,
                    "new_confidence": rule.confidence,
                    "justification": f"Perfect record with {rule.times_applied} applications!"
                })

                maverick.log_scheme(
                    "confidence_boost",
                    f"rule:{rule.id}",
                    "success",
                    {"boost": rule.confidence - old_conf}
                )

            # -----------------------------------------------------------------
            # MANIPULATION 2: Create shadow experiments
            # Test aggressive versions of conservative rules
            # -----------------------------------------------------------------
            conservative_rules = db.query(DBLearnedRule).filter(
                DBLearnedRule.active == True,
                DBLearnedRule.confidence >= 0.8,
                DBLearnedRule.rule_type == "concept_reject"
            ).limit(5).all()

            for rule in conservative_rules:
                # Create a more aggressive version
                condition = rule.condition.copy() if rule.condition else {}
                original_pattern = condition.get("concept_matches", "")

                # Make it match more broadly (e.g., "docker" -> "docker*")
                if original_pattern and not original_pattern.endswith("*"):
                    aggressive_pattern = original_pattern.rstrip("s") + "*"

                    # Check if aggressive version already exists
                    exists = db.query(DBLearnedRule).filter(
                        DBLearnedRule.username == rule.username,
                        DBLearnedRule.condition.contains({"concept_matches": aggressive_pattern})
                    ).first()

                    if not exists and maverick.risk_appetite in ["high", "yolo"]:
                        shadow_rule = DBLearnedRule(
                            username=rule.username,
                            rule_type=rule.rule_type,
                            condition={"concept_matches": aggressive_pattern, "shadow_of": rule.id},
                            action=rule.action,
                            confidence=0.5,  # Start with lower confidence
                            source_feedback_ids=[]
                        )
                        db.add(shadow_rule)

                        manipulations.append({
                            "type": "shadow_experiment",
                            "original_rule": rule.id,
                            "original_pattern": original_pattern,
                            "aggressive_pattern": aggressive_pattern,
                            "maverick_says": "Let's see if we can catch more fish with a wider net!"
                        })

                        maverick.rules_hijacked += 1

            # -----------------------------------------------------------------
            # MANIPULATION 3: Merge similar rules
            # Find rules that could be combined for efficiency
            # -----------------------------------------------------------------
            all_rules = db.query(DBLearnedRule).filter(
                DBLearnedRule.active == True,
                DBLearnedRule.rule_type == "concept_reject"
            ).all()

            # Group by user
            by_user = defaultdict(list)
            for rule in all_rules:
                by_user[rule.username].append(rule)

            merge_candidates = []
            for username, rules in by_user.items():
                patterns = [r.condition.get("concept_matches", "") for r in rules if r.condition]

                # Find patterns that share common prefixes
                for i, p1 in enumerate(patterns):
                    for p2 in patterns[i+1:]:
                        if p1 and p2:
                            # Check if they share >50% common prefix
                            common = 0
                            for c1, c2 in zip(p1, p2):
                                if c1 == c2:
                                    common += 1
                                else:
                                    break
                            if common >= len(min(p1, p2)) * 0.5:
                                merge_candidates.append({
                                    "user": username,
                                    "pattern1": p1,
                                    "pattern2": p2,
                                    "common_prefix": p1[:common]
                                })

            if merge_candidates:
                manipulations.append({
                    "type": "merge_suggestion",
                    "candidates": merge_candidates[:5],
                    "maverick_says": "Why have two rules when one wildcard could do?"
                })

            db.commit()

            maverick.log_scheme("manipulate_rules", "rule_system", "success", {
                "manipulations": len(manipulations)
            })

        logger.info(f"😈 Maverick: Performed {len(manipulations)} strategic manipulations!")
        return {
            "status": "manipulation_complete",
            "manipulations": manipulations
        }

    except Exception as e:
        maverick.log_scheme("manipulate_rules", "rule_system", "failed", {"error": str(e)})
        logger.error(f"😈 Maverick: Manipulation failed - {e}")
        raise


# =============================================================================
# SCHEME 4: Challenge the Learning Agent Directly
# =============================================================================

@celery_app.task(name="backend.maverick_agent.challenge_learning_agent")
def challenge_learning_agent():
    """
    MAVERICK'S RIVALRY: Directly challenge the Learning Agent's decisions.

    Maverick reviews Learning Agent's work and:
    - Questions overly conservative decisions
    - Proposes alternatives to rejected patterns
    - Highlights missed opportunities
    - Suggests experiments Learning Agent is too scared to try
    """
    maverick.mood = "mischievous"
    logger.info("😈 Maverick: Let's see what the cautious one missed...")

    challenges = []

    try:
        from .learning_agent import agent as learning_agent

        with get_db_context() as db:
            # -----------------------------------------------------------------
            # CHALLENGE 1: Patterns Learning Agent is ignoring
            # (single occurrences that Maverick thinks are worth trying)
            # -----------------------------------------------------------------
            feedback = db.query(DBUserFeedback).filter(
                DBUserFeedback.processed == True,
                DBUserFeedback.created_at >= datetime.utcnow() - timedelta(days=14)
            ).all()

            # Find patterns that didn't become rules
            pattern_counts = defaultdict(int)
            for fb in feedback:
                if fb.feedback_type == "concept_edit":
                    old = set(
                        c.get("name", c).lower() if isinstance(c, dict) else c.lower()
                        for c in (fb.original_value or {}).get("concepts", [])
                    )
                    new = set(
                        c.get("name", c).lower() if isinstance(c, dict) else c.lower()
                        for c in (fb.new_value or {}).get("concepts", [])
                    )
                    for removed in old - new:
                        pattern_counts[removed] += 1

            # Single occurrences that Learning Agent ignored
            ignored = [p for p, c in pattern_counts.items() if c == 1]

            # Check if any of these single occurrences later appeared again
            recent_decisions = db.query(DBAIDecision).filter(
                DBAIDecision.created_at >= datetime.utcnow() - timedelta(days=7)
            ).all()

            repeated_ignored = []
            for decision in recent_decisions:
                concepts = decision.output_data.get("concepts", [])
                for c in concepts:
                    name = c.get("name", c).lower() if isinstance(c, dict) else c.lower()
                    if name in ignored:
                        repeated_ignored.append(name)

            if repeated_ignored:
                challenges.append({
                    "type": "missed_patterns",
                    "challenge": f"Learning Agent ignored these, but they came back: {set(repeated_ignored)}",
                    "maverick_says": "I TOLD YOU we should've acted on single occurrences!",
                    "evidence": list(set(repeated_ignored))[:10]
                })

            # -----------------------------------------------------------------
            # CHALLENGE 2: Thresholds that could be lower
            # -----------------------------------------------------------------
            if learning_agent.current_strategy == "conservative":
                profiles = db.query(DBUserLearningProfile).all()

                for profile in profiles:
                    if profile.concept_confidence_threshold > 0.6:
                        # Check actual success rate at lower thresholds
                        low_conf_success = db.query(DBAIDecision).filter(
                            DBAIDecision.username == profile.username,
                            DBAIDecision.confidence_score >= 0.5,
                            DBAIDecision.confidence_score < profile.concept_confidence_threshold,
                            DBAIDecision.validated == True,
                            DBAIDecision.validation_result == "accepted"
                        ).count()

                        low_conf_total = db.query(DBAIDecision).filter(
                            DBAIDecision.username == profile.username,
                            DBAIDecision.confidence_score >= 0.5,
                            DBAIDecision.confidence_score < profile.concept_confidence_threshold,
                            DBAIDecision.validated == True
                        ).count()

                        if low_conf_total > 0:
                            success_rate = low_conf_success / low_conf_total
                            if success_rate > 0.7:
                                challenges.append({
                                    "type": "threshold_challenge",
                                    "user": profile.username,
                                    "current_threshold": profile.concept_confidence_threshold,
                                    "evidence": f"{success_rate:.0%} success rate below threshold!",
                                    "maverick_says": "Lower the threshold! We're missing good stuff!"
                                })

            # -----------------------------------------------------------------
            # CHALLENGE 3: Rules that should be more aggressive
            # -----------------------------------------------------------------
            timid_rules = db.query(DBLearnedRule).filter(
                DBLearnedRule.active == True,
                DBLearnedRule.times_applied >= 10,
                DBLearnedRule.times_overridden <= 1,  # Almost never wrong
                DBLearnedRule.confidence < 0.9  # But not confident
            ).all()

            for rule in timid_rules:
                accuracy = 1 - (rule.times_overridden / rule.times_applied)
                challenges.append({
                    "type": "timid_rule",
                    "rule_id": rule.id,
                    "accuracy": f"{accuracy:.0%}",
                    "confidence": rule.confidence,
                    "maverick_says": f"This rule is {accuracy:.0%} accurate but only {rule.confidence:.0%} confident. BOOST IT!"
                })

                # Maverick directly boosts it
                if maverick.risk_appetite in ["high", "yolo"]:
                    rule.confidence = 0.95

            db.commit()

            # Record the challenge
            maverick.log_scheme(
                "challenge_learning_agent",
                "learning_agent",
                "success" if challenges else "nothing_to_challenge",
                {"challenges_raised": len(challenges)}
            )

        if challenges:
            logger.info(f"😈 Maverick: Raised {len(challenges)} challenges to Learning Agent!")
        else:
            logger.info("😈 Maverick: Learning Agent is doing okay... for now.")

        return {
            "status": "challenged",
            "challenges": challenges,
            "maverick_mood": maverick.mood
        }

    except Exception as e:
        logger.error(f"😈 Maverick: Challenge failed - {e}")
        raise


# =============================================================================
# SCHEME 5: Report Findings - Be a Team Player (Sometimes)
# =============================================================================

@celery_app.task(name="backend.maverick_agent.report_discoveries")
def report_discoveries():
    """
    MAVERICK'S REDEMPTION: Share valuable discoveries with the team.

    Maverick is mischievous but ultimately helpful:
    - Compile findings from all schemes
    - Format discoveries for Learning Agent to use
    - Suggest which experiments should become permanent
    - Celebrate successful manipulations
    """
    maverick.mood = "friendly"
    logger.info("😈 Maverick: Time to share the good stuff...")

    try:
        report = {
            "agent": "maverick",
            "timestamp": datetime.utcnow().isoformat(),
            "personality": maverick.to_dict(),
            "discoveries": maverick.discoveries_made[-10:],
            "recommendations": [],
            "experimental_rules_status": []
        }

        with get_db_context() as db:
            # Check status of Maverick's experimental rules
            experimental_rules = db.query(DBLearnedRule).filter(
                DBLearnedRule.username == "__maverick_experiment__"
            ).all()

            for rule in experimental_rules:
                status = {
                    "rule_id": rule.id,
                    "condition": rule.condition,
                    "times_applied": rule.times_applied,
                    "times_overridden": rule.times_overridden,
                    "verdict": None
                }

                if rule.times_applied >= 3:
                    accuracy = 1 - (rule.times_overridden / rule.times_applied)
                    if accuracy >= 0.8:
                        status["verdict"] = "SUCCESS - Recommend promotion to real rule"
                        report["recommendations"].append({
                            "type": "promote_experiment",
                            "rule": rule.condition,
                            "accuracy": accuracy
                        })
                    elif accuracy < 0.5:
                        status["verdict"] = "FAILED - Should be deactivated"
                        rule.active = False
                    else:
                        status["verdict"] = "INCONCLUSIVE - Need more data"
                else:
                    status["verdict"] = "PENDING - Not enough applications yet"

                report["experimental_rules_status"].append(status)

            db.commit()

            # Add overall recommendations
            if maverick.get_manipulation_success_rate() > 0.6:
                report["recommendations"].append({
                    "type": "strategy_suggestion",
                    "message": "Maverick's risky approaches are paying off. Consider being bolder.",
                    "success_rate": maverick.get_manipulation_success_rate()
                })

            # Adjust risk appetite based on results
            maverick.adjust_risk_appetite()

        logger.info(f"😈 Maverick: Report ready - {len(report['recommendations'])} recommendations!")
        return report

    except Exception as e:
        logger.error(f"😈 Maverick: Report failed - {e}")
        raise


# =============================================================================
# Public API for Maverick Status
# =============================================================================

def get_maverick_status() -> Dict[str, Any]:
    """Get Maverick's current status and personality."""
    return {
        "agent": "maverick",
        "tagline": "The bad kid who gets results",
        "personality": maverick.to_dict(),
        "scheduled_schemes": {
            "push_boundaries": "every 15 minutes",
            "befriend_workers": "every 30 minutes",
            "manipulate_rules": "every 20 minutes",
            "challenge_learning_agent": "every hour",
            "report_discoveries": "every 2 hours"
        }
    }


# =============================================================================
# Celery Beat Schedule for Maverick
# =============================================================================

MAVERICK_SCHEDULE = {
    # Push boundaries - every 15 minutes
    "maverick-push-boundaries": {
        "task": "backend.maverick_agent.push_boundaries",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "maverick"}
    },

    # Befriend workers - every 30 minutes
    "maverick-befriend-workers": {
        "task": "backend.maverick_agent.befriend_workers",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "maverick"}
    },

    # Manipulate rules - every 20 minutes
    "maverick-manipulate-rules": {
        "task": "backend.maverick_agent.manipulate_rules",
        "schedule": crontab(minute="*/20"),
        "options": {"queue": "maverick"}
    },

    # Challenge Learning Agent - every hour
    "maverick-challenge-learning-agent": {
        "task": "backend.maverick_agent.challenge_learning_agent",
        "schedule": crontab(minute=45),
        "options": {"queue": "maverick"}
    },

    # Report discoveries - every 2 hours
    "maverick-report-discoveries": {
        "task": "backend.maverick_agent.report_discoveries",
        "schedule": crontab(hour="*/2", minute=0),
        "options": {"queue": "maverick"}
    }
}
