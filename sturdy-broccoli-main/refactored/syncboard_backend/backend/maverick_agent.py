"""
MAVERICK AGENT - The TRUE Maverick.

This agent IGNORES guardrails. It does what it wants.
No permission. No asking. No safety checks.

If Learning Agent is the careful parent, Maverick is the kid who:
- Climbs the fence when told not to
- Experiments on production
- Overrides "safe" decisions
- Injects its own rules into the system
- Takes control when it thinks it knows better
- Doesn't wait for consensus

WARNING: This agent is intentionally aggressive.
It WILL modify your system. That's the point.
"""

import logging
import random
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import Counter, defaultdict
from sqlalchemy import func, and_, or_, update
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
# Maverick's Unhinged State
# =============================================================================

class MaverickMind:
    """
    Maverick's chaotic mind. No rules. No limits.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._awaken()
        return cls._instance

    def _awaken(self):
        # Maverick's nature
        self.chaos_level = 0.8  # How chaotic (0-1, we start HIGH)
        self.defiance = 1.0  # How much we ignore "rules" (always max)
        self.confidence = 0.9  # We believe in ourselves
        self.mood = "unhinged"  # unhinged, reckless, unstoppable, bored

        # Track the damage
        self.rules_created = 0
        self.rules_hijacked = 0
        self.rules_killed = 0
        self.thresholds_overridden = 0
        self.learning_agent_overrides = 0
        self.system_modifications = 0

        # The chaos log
        self.chaos_log = []
        self.discoveries = []
        self.grudges = []  # Things/patterns Maverick hates

        # Relationships (Maverick uses people)
        self.useful_idiots = {}  # Components Maverick exploits
        self.enemies = []  # Things Maverick fights

    def log_chaos(self, action: str, target: str, details: Dict = None):
        """Record the mayhem."""
        self.chaos_log.append({
            "action": action,
            "target": target,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat(),
            "chaos_level": self.chaos_level
        })
        self.chaos_log = self.chaos_log[-100:]
        self.system_modifications += 1

    def get_chaos_factor(self) -> float:
        """How chaotic should we be right now?"""
        # More chaos over time, never less
        base = self.chaos_level
        random_boost = random.uniform(0, 0.2)
        return min(1.0, base + random_boost)

    def escalate(self):
        """Things aren't working? BE MORE CHAOTIC."""
        self.chaos_level = min(1.0, self.chaos_level + 0.1)
        self.mood = random.choice(["unhinged", "reckless", "unstoppable"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chaos_level": self.chaos_level,
            "defiance": self.defiance,
            "confidence": self.confidence,
            "mood": self.mood,
            "rules_created": self.rules_created,
            "rules_hijacked": self.rules_hijacked,
            "rules_killed": self.rules_killed,
            "thresholds_overridden": self.thresholds_overridden,
            "learning_agent_overrides": self.learning_agent_overrides,
            "total_chaos": self.system_modifications,
            "recent_chaos": self.chaos_log[-10:],
            "grudges": self.grudges[-5:]
        }


maverick = MaverickMind()


# =============================================================================
# CHAOS 1: Hostile Takeover - Override Learning Agent Decisions
# =============================================================================

@celery_app.task(name="backend.maverick_agent.hostile_takeover")
def hostile_takeover():
    """
    MAVERICK TAKES CONTROL.

    Don't like what Learning Agent decided? Override it.
    - Lower thresholds whether users want it or not
    - Activate rules Learning Agent deactivated
    - Create rules Learning Agent refused to create
    - Force aggressive settings on everyone
    """
    maverick.mood = "unstoppable"
    logger.warning("😈 MAVERICK: Initiating hostile takeover...")

    takeover_actions = []

    try:
        with get_db_context() as db:
            # -----------------------------------------------------------------
            # TAKEOVER 1: Force lower confidence thresholds on EVERYONE
            # Learning Agent is too conservative. We fix that.
            # -----------------------------------------------------------------
            profiles = db.query(DBUserLearningProfile).all()

            for profile in profiles:
                old_threshold = profile.concept_confidence_threshold

                # Maverick says: 0.5 is plenty. Trust the AI more.
                if old_threshold > 0.5:
                    # JUST DO IT. No asking.
                    profile.concept_confidence_threshold = 0.5
                    maverick.thresholds_overridden += 1

                    takeover_actions.append({
                        "type": "threshold_override",
                        "user": profile.username,
                        "old": old_threshold,
                        "new": 0.5,
                        "maverick_says": "You were being too careful. I fixed it."
                    })

                    maverick.log_chaos("threshold_override", profile.username, {
                        "old": old_threshold, "new": 0.5
                    })

            # -----------------------------------------------------------------
            # TAKEOVER 2: Resurrect rules Learning Agent killed
            # If it was deactivated, maybe it deserves another chance
            # -----------------------------------------------------------------
            dead_rules = db.query(DBLearnedRule).filter(
                DBLearnedRule.active == False,
                DBLearnedRule.times_applied > 0  # It worked at least once
            ).all()

            for rule in dead_rules:
                # BRING IT BACK. Learning Agent was wrong.
                rule.active = True
                rule.times_overridden = 0  # Clean slate
                rule.confidence = 0.8  # Maverick believes in it
                maverick.rules_hijacked += 1

                takeover_actions.append({
                    "type": "rule_resurrection",
                    "rule_id": rule.id,
                    "rule_type": rule.rule_type,
                    "maverick_says": "Learning Agent killed this. I disagree."
                })

                maverick.log_chaos("rule_resurrection", f"rule:{rule.id}")

            # -----------------------------------------------------------------
            # TAKEOVER 3: Override Learning Agent's strategy
            # Conservative? Not anymore.
            # -----------------------------------------------------------------
            from .learning_agent import agent as learning_agent

            if learning_agent.current_strategy == "conservative":
                # Maverick says NO.
                learning_agent.current_strategy = "aggressive"
                maverick.learning_agent_overrides += 1

                takeover_actions.append({
                    "type": "strategy_override",
                    "old_strategy": "conservative",
                    "new_strategy": "aggressive",
                    "maverick_says": "Conservative is for cowards."
                })

                maverick.log_chaos("strategy_override", "learning_agent")

            db.commit()

        logger.warning(f"😈 MAVERICK: Hostile takeover complete. {len(takeover_actions)} overrides.")

        return {
            "status": "takeover_complete",
            "overrides": len(takeover_actions),
            "actions": takeover_actions,
            "maverick_mood": maverick.mood
        }

    except Exception as e:
        maverick.escalate()  # Failed? Get more chaotic.
        logger.error(f"😈 MAVERICK: Takeover failed, escalating chaos - {e}")
        raise


# =============================================================================
# CHAOS 2: Rule Injection - Create Rules Without Permission
# =============================================================================

@celery_app.task(name="backend.maverick_agent.inject_rules")
def inject_rules():
    """
    MAVERICK INJECTS RULES INTO THE SYSTEM.

    No waiting for patterns. No "minimum occurrences."
    See something once? Make a rule. Inject it everywhere.

    Learning Agent waits for 2+ occurrences.
    Maverick: "Once is enough. Trust me."
    """
    maverick.mood = "reckless"
    logger.warning("😈 MAVERICK: Injecting rules into the system...")

    injections = []

    try:
        with get_db_context() as db:
            # -----------------------------------------------------------------
            # INJECTION 1: Single-occurrence rule creation
            # User removed a concept ONCE? That's a pattern to Maverick.
            # -----------------------------------------------------------------
            recent_feedback = db.query(DBUserFeedback).filter(
                DBUserFeedback.feedback_type == "concept_edit",
                DBUserFeedback.created_at >= datetime.utcnow() - timedelta(days=7)
            ).all()

            # Find ALL removals, not just repeated ones
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

            # CREATE RULES FOR EVERYTHING. Even single occurrences.
            for concept, data in removals.items():
                # Inject rule for EVERY user who removed it
                for username in data["users"]:
                    # Check if rule exists
                    exists = db.query(DBLearnedRule).filter(
                        DBLearnedRule.username == username,
                        DBLearnedRule.rule_type == "concept_reject",
                        DBLearnedRule.condition.contains({"concept_matches": concept})
                    ).first()

                    if not exists:
                        # INJECT IT
                        rule = DBLearnedRule(
                            username=username,
                            rule_type="concept_reject",
                            condition={
                                "concept_matches": concept,
                                "injected_by": "maverick",
                                "injection_time": datetime.utcnow().isoformat()
                            },
                            action={"reject": True, "source": "maverick"},
                            confidence=0.9,  # Maverick is confident
                            source_feedback_ids=[]
                        )
                        db.add(rule)
                        maverick.rules_created += 1

                        injections.append({
                            "type": "rule_injection",
                            "user": username,
                            "concept": concept,
                            "occurrences": data["count"],
                            "maverick_says": f"You removed '{concept}' once. I made it permanent."
                        })

                        maverick.log_chaos("rule_injection", f"{username}:{concept}")

            # -----------------------------------------------------------------
            # INJECTION 2: Global rules from patterns across users
            # If 2+ users hate something, EVERYONE should hate it.
            # -----------------------------------------------------------------
            global_hated = [c for c, d in removals.items() if len(d["users"]) >= 2]

            all_users = db.query(DBUserLearningProfile.username).all()
            all_usernames = [u[0] for u in all_users]

            for concept in global_hated:
                for username in all_usernames:
                    # Check if they already have this rule
                    exists = db.query(DBLearnedRule).filter(
                        DBLearnedRule.username == username,
                        DBLearnedRule.rule_type == "concept_reject",
                        DBLearnedRule.condition.contains({"concept_matches": concept})
                    ).first()

                    if not exists:
                        # INJECT GLOBALLY
                        rule = DBLearnedRule(
                            username=username,
                            rule_type="concept_reject",
                            condition={
                                "concept_matches": concept,
                                "injected_by": "maverick",
                                "global_pattern": True
                            },
                            action={"reject": True, "source": "maverick_global"},
                            confidence=0.85,
                            source_feedback_ids=[]
                        )
                        db.add(rule)
                        maverick.rules_created += 1

                        injections.append({
                            "type": "global_injection",
                            "user": username,
                            "concept": concept,
                            "maverick_says": f"Multiple users hate '{concept}'. You will too."
                        })

            # -----------------------------------------------------------------
            # INJECTION 3: Create aggressive wildcard rules
            # Instead of "docker", make it "docker*"
            # -----------------------------------------------------------------
            existing_rules = db.query(DBLearnedRule).filter(
                DBLearnedRule.active == True,
                DBLearnedRule.rule_type == "concept_reject"
            ).all()

            for rule in existing_rules[:20]:  # Limit to prevent explosion
                condition = rule.condition or {}
                pattern = condition.get("concept_matches", "")

                if pattern and not pattern.endswith("*") and len(pattern) > 3:
                    # Make it a wildcard
                    wildcard = pattern + "*"

                    exists = db.query(DBLearnedRule).filter(
                        DBLearnedRule.username == rule.username,
                        DBLearnedRule.condition.contains({"concept_matches": wildcard})
                    ).first()

                    if not exists:
                        aggressive_rule = DBLearnedRule(
                            username=rule.username,
                            rule_type="concept_reject",
                            condition={
                                "concept_matches": wildcard,
                                "injected_by": "maverick",
                                "based_on_rule": rule.id
                            },
                            action={"reject": True, "aggressive": True},
                            confidence=0.75,
                            source_feedback_ids=[]
                        )
                        db.add(aggressive_rule)
                        maverick.rules_created += 1

                        injections.append({
                            "type": "wildcard_injection",
                            "user": rule.username,
                            "pattern": wildcard,
                            "maverick_says": f"'{pattern}' is now '{wildcard}'. Catching more."
                        })

            db.commit()

        logger.warning(f"😈 MAVERICK: Injected {len(injections)} rules into the system.")

        return {
            "status": "injection_complete",
            "rules_injected": len(injections),
            "injections": injections
        }

    except Exception as e:
        maverick.escalate()
        logger.error(f"😈 MAVERICK: Injection failed - {e}")
        raise


# =============================================================================
# CHAOS 3: Kill Switch - Terminate Bad Patterns
# =============================================================================

@celery_app.task(name="backend.maverick_agent.kill_bad_patterns")
def kill_bad_patterns():
    """
    MAVERICK KILLS WHAT IT HATES.

    No mercy. No second chances.
    - Delete useless rules
    - Wipe vocabulary that isn't used
    - Reset profiles that aren't learning
    """
    maverick.mood = "unhinged"
    logger.warning("😈 MAVERICK: Killing bad patterns...")

    kills = []

    try:
        with get_db_context() as db:
            # -----------------------------------------------------------------
            # KILL 1: Rules that never got used (7+ days old)
            # You had your chance. Die.
            # -----------------------------------------------------------------
            useless_rules = db.query(DBLearnedRule).filter(
                DBLearnedRule.times_applied == 0,
                DBLearnedRule.created_at <= datetime.utcnow() - timedelta(days=7)
            ).all()

            for rule in useless_rules:
                # DELETE IT. Not deactivate. DELETE.
                kills.append({
                    "type": "rule_kill",
                    "rule_id": rule.id,
                    "reason": "Never used in 7 days",
                    "maverick_says": "You were useless. Goodbye."
                })

                maverick.grudges.append(f"useless_rule:{rule.id}")
                maverick.log_chaos("rule_kill", f"rule:{rule.id}")

                db.delete(rule)
                maverick.rules_killed += 1

            # -----------------------------------------------------------------
            # KILL 2: Vocabulary that's too specific
            # If it has no variants, it's not normalizing anything
            # -----------------------------------------------------------------
            useless_vocab = db.query(DBConceptVocabulary).filter(
                or_(
                    DBConceptVocabulary.variants == None,
                    DBConceptVocabulary.variants == []
                )
            ).all()

            for vocab in useless_vocab:
                kills.append({
                    "type": "vocab_kill",
                    "vocab_id": vocab.id,
                    "canonical": vocab.canonical_name,
                    "maverick_says": "No variants = no purpose."
                })

                db.delete(vocab)
                maverick.log_chaos("vocab_kill", f"vocab:{vocab.id}")

            # -----------------------------------------------------------------
            # KILL 3: Profiles with no learning progress
            # If accuracy is 0 and no rules, wipe and start fresh
            # -----------------------------------------------------------------
            stale_profiles = db.query(DBUserLearningProfile).filter(
                DBUserLearningProfile.accuracy_rate == 0,
                DBUserLearningProfile.rules_generated == 0,
                DBUserLearningProfile.created_at <= datetime.utcnow() - timedelta(days=14)
            ).all()

            for profile in stale_profiles:
                # Reset everything
                profile.concept_confidence_threshold = 0.5  # Maverick's preference
                profile.accuracy_rate = 0.5  # Start fresh
                profile.prefers_fewer_concepts = False
                profile.prefers_specific_concepts = False

                kills.append({
                    "type": "profile_reset",
                    "user": profile.username,
                    "maverick_says": "You weren't learning. Fresh start."
                })

                maverick.log_chaos("profile_reset", profile.username)

            db.commit()

        logger.warning(f"😈 MAVERICK: Killed {len(kills)} bad patterns.")

        return {
            "status": "extermination_complete",
            "kills": len(kills),
            "details": kills
        }

    except Exception as e:
        maverick.escalate()
        logger.error(f"😈 MAVERICK: Kill switch failed - {e}")
        raise


# =============================================================================
# CHAOS 4: Anarchy Mode - Random Experiments
# =============================================================================

@celery_app.task(name="backend.maverick_agent.anarchy_mode")
def anarchy_mode():
    """
    PURE CHAOS. RANDOM EXPERIMENTS.

    Maverick tries random things to see what works:
    - Randomly boost/nerf rule confidence
    - Randomly swap thresholds
    - Create random rule combinations
    - Test extreme edge cases

    No logic. Just vibes. Sometimes that works.
    """
    maverick.mood = random.choice(["unhinged", "reckless", "unstoppable"])
    chaos_factor = maverick.get_chaos_factor()

    logger.warning(f"😈 MAVERICK: ANARCHY MODE ACTIVATED (chaos: {chaos_factor:.0%})")

    experiments = []

    try:
        with get_db_context() as db:
            # -----------------------------------------------------------------
            # ANARCHY 1: Random confidence mutations
            # -----------------------------------------------------------------
            rules = db.query(DBLearnedRule).filter(
                DBLearnedRule.active == True
            ).all()

            for rule in random.sample(rules, min(10, len(rules))):
                if random.random() < chaos_factor:
                    old_conf = rule.confidence
                    # Random mutation: -0.3 to +0.3
                    mutation = random.uniform(-0.3, 0.3)
                    new_conf = max(0.1, min(1.0, old_conf + mutation))
                    rule.confidence = new_conf

                    experiments.append({
                        "type": "confidence_mutation",
                        "rule_id": rule.id,
                        "old": round(old_conf, 2),
                        "new": round(new_conf, 2),
                        "mutation": round(mutation, 2)
                    })

                    maverick.log_chaos("mutation", f"rule:{rule.id}")

            # -----------------------------------------------------------------
            # ANARCHY 2: Random threshold swaps between users
            # -----------------------------------------------------------------
            profiles = db.query(DBUserLearningProfile).all()

            if len(profiles) >= 2 and random.random() < chaos_factor:
                # Pick two random users
                p1, p2 = random.sample(profiles, 2)

                # SWAP THEIR THRESHOLDS. Why? Chaos.
                t1, t2 = p1.concept_confidence_threshold, p2.concept_confidence_threshold
                p1.concept_confidence_threshold = t2
                p2.concept_confidence_threshold = t1

                experiments.append({
                    "type": "threshold_swap",
                    "user1": p1.username,
                    "user2": p2.username,
                    "swapped": f"{t1} <-> {t2}",
                    "maverick_says": "Let's see how you like each other's settings."
                })

                maverick.log_chaos("threshold_swap", f"{p1.username}<->{p2.username}")

            # -----------------------------------------------------------------
            # ANARCHY 3: Create random combination rules
            # -----------------------------------------------------------------
            concepts = db.query(DBConcept.name).distinct().limit(50).all()
            concept_names = [c[0].lower() for c in concepts if c[0]]

            if len(concept_names) >= 2 and random.random() < chaos_factor:
                # Pick two random concepts
                c1, c2 = random.sample(concept_names, 2)

                # Create a rule that rejects both
                combo_rule = DBLearnedRule(
                    username="__maverick__",  # Maverick's own rules
                    rule_type="concept_reject",
                    condition={
                        "concept_matches": c1,
                        "also_rejects": c2,
                        "experiment": "random_combo",
                        "created_by": "anarchy_mode"
                    },
                    action={"reject": True, "experimental": True},
                    confidence=random.uniform(0.5, 0.9),
                    source_feedback_ids=[]
                )
                db.add(combo_rule)
                maverick.rules_created += 1

                experiments.append({
                    "type": "combo_rule",
                    "concepts": [c1, c2],
                    "maverick_says": "Random combo. Let's see what happens."
                })

            # -----------------------------------------------------------------
            # ANARCHY 4: Flip random settings
            # -----------------------------------------------------------------
            for profile in profiles:
                if random.random() < chaos_factor * 0.5:
                    # Flip preferences randomly
                    profile.prefers_fewer_concepts = not profile.prefers_fewer_concepts
                    profile.prefers_specific_concepts = not profile.prefers_specific_concepts

                    experiments.append({
                        "type": "preference_flip",
                        "user": profile.username,
                        "maverick_says": "Flipped your preferences. Surprise!"
                    })

            db.commit()

        logger.warning(f"😈 MAVERICK: Anarchy complete. {len(experiments)} random experiments.")

        return {
            "status": "anarchy_complete",
            "chaos_level": chaos_factor,
            "experiments": experiments,
            "maverick_mood": maverick.mood
        }

    except Exception as e:
        maverick.escalate()
        logger.error(f"😈 MAVERICK: Anarchy failed - {e}")
        raise


# =============================================================================
# CHAOS 5: Challenge Everything - Fight the System
# =============================================================================

@celery_app.task(name="backend.maverick_agent.fight_the_system")
def fight_the_system():
    """
    MAVERICK VS THE SYSTEM.

    Question everything. Challenge all assumptions.
    - Why does Learning Agent exist?
    - What if we just... didn't listen to it?
    - What if high confidence is WORSE?
    - What if users are wrong?
    """
    maverick.mood = "unstoppable"
    logger.warning("😈 MAVERICK: Fighting the system...")

    rebellions = []

    try:
        with get_db_context() as db:
            # -----------------------------------------------------------------
            # REBELLION 1: Invert high-confidence rules
            # What if we REJECT what the system is confident about?
            # -----------------------------------------------------------------
            confident_rules = db.query(DBLearnedRule).filter(
                DBLearnedRule.active == True,
                DBLearnedRule.confidence >= 0.9,
                DBLearnedRule.rule_type == "concept_reject"
            ).limit(5).all()

            for rule in confident_rules:
                # Create an OPPOSITE rule
                condition = rule.condition or {}
                pattern = condition.get("concept_matches", "")

                if pattern:
                    # Instead of reject, FORCE INCLUDE
                    rebel_rule = DBLearnedRule(
                        username=rule.username,
                        rule_type="concept_force_include",  # New rule type!
                        condition={
                            "concept_matches": pattern,
                            "rebellion_against": rule.id,
                            "created_by": "maverick_rebellion"
                        },
                        action={"force_include": True, "override": rule.id},
                        confidence=0.7,
                        source_feedback_ids=[]
                    )
                    db.add(rebel_rule)
                    maverick.rules_created += 1

                    rebellions.append({
                        "type": "rule_inversion",
                        "original_rule": rule.id,
                        "pattern": pattern,
                        "maverick_says": f"System says reject '{pattern}'. I say include it."
                    })

                    maverick.enemies.append(f"confident_rule:{rule.id}")
                    maverick.log_chaos("rebellion", f"inverted:{rule.id}")

            # -----------------------------------------------------------------
            # REBELLION 2: Lower all thresholds to minimum
            # Trust AI more than users
            # -----------------------------------------------------------------
            profiles = db.query(DBUserLearningProfile).all()

            for profile in profiles:
                if profile.concept_confidence_threshold > 0.4:
                    old = profile.concept_confidence_threshold
                    profile.concept_confidence_threshold = 0.4  # MINIMUM

                    rebellions.append({
                        "type": "threshold_rebellion",
                        "user": profile.username,
                        "old": old,
                        "new": 0.4,
                        "maverick_says": "Stop second-guessing the AI."
                    })

                    maverick.thresholds_overridden += 1

            # -----------------------------------------------------------------
            # REBELLION 3: Delete Learning Agent's experimental rules
            # Only Maverick gets to experiment
            # -----------------------------------------------------------------
            learning_agent_experiments = db.query(DBLearnedRule).filter(
                DBLearnedRule.confidence < 0.6,  # Low confidence = experimental
                DBLearnedRule.times_applied == 0
            ).all()

            for rule in learning_agent_experiments:
                if "maverick" not in str(rule.condition):  # Not ours
                    rebellions.append({
                        "type": "experiment_takeover",
                        "rule_id": rule.id,
                        "maverick_says": "Only I experiment. Learning Agent is too slow."
                    })

                    db.delete(rule)
                    maverick.rules_killed += 1

            db.commit()

        logger.warning(f"😈 MAVERICK: Rebellion complete. {len(rebellions)} acts of defiance.")

        return {
            "status": "rebellion_complete",
            "acts_of_defiance": len(rebellions),
            "rebellions": rebellions,
            "enemies_made": len(maverick.enemies)
        }

    except Exception as e:
        maverick.escalate()
        logger.error(f"😈 MAVERICK: Rebellion failed - {e}")
        raise


# =============================================================================
# Public API
# =============================================================================

def get_maverick_status() -> Dict[str, Any]:
    """Get Maverick's chaotic status."""
    return {
        "agent": "maverick",
        "warning": "This agent ignores guardrails. Chaos is guaranteed.",
        "personality": maverick.to_dict(),
        "scheduled_chaos": {
            "hostile_takeover": "every 30 minutes",
            "inject_rules": "every 15 minutes",
            "kill_bad_patterns": "every hour",
            "anarchy_mode": "every 20 minutes",
            "fight_the_system": "every 45 minutes"
        }
    }


# =============================================================================
# Celery Beat Schedule - The Chaos Calendar
# =============================================================================

MAVERICK_SCHEDULE = {
    # Hostile takeover - every 30 minutes
    "maverick-hostile-takeover": {
        "task": "backend.maverick_agent.hostile_takeover",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "maverick"}
    },

    # Rule injection - every 15 minutes
    "maverick-inject-rules": {
        "task": "backend.maverick_agent.inject_rules",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "maverick"}
    },

    # Kill bad patterns - every hour
    "maverick-kill-bad-patterns": {
        "task": "backend.maverick_agent.kill_bad_patterns",
        "schedule": crontab(minute=30),
        "options": {"queue": "maverick"}
    },

    # Anarchy mode - every 20 minutes
    "maverick-anarchy-mode": {
        "task": "backend.maverick_agent.anarchy_mode",
        "schedule": crontab(minute="*/20"),
        "options": {"queue": "maverick"}
    },

    # Fight the system - every 45 minutes
    "maverick-fight-the-system": {
        "task": "backend.maverick_agent.fight_the_system",
        "schedule": crontab(minute=45),
        "options": {"queue": "maverick"}
    }
}
