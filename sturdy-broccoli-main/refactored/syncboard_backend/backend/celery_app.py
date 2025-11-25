"""
Celery Application Configuration for SyncBoard 3.0 Knowledge Bank.

This module configures the Celery task queue for background job processing:
- File upload processing (PDF, images, videos, etc.)
- YouTube/URL content ingestion
- Duplicate detection
- Build suggestions generation
- Analytics caching

Architecture:
    FastAPI Backend → Redis (Message Broker) → Celery Workers

Usage:
    # Start Celery worker:
    celery -A backend.celery_app worker --loglevel=info --concurrency=4

    # Start Flower monitoring dashboard:
    celery -A backend.celery_app flower --port=5555

    # Monitor tasks at: http://localhost:5555
"""

import os
from celery import Celery
from celery.schedules import crontab

# =============================================================================
# Configuration
# =============================================================================

# Redis connection URL
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Celery broker and result backend (both use Redis)
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL)

# =============================================================================
# Celery App Instance
# =============================================================================

celery_app = Celery(
    "syncboard",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["backend.tasks", "backend.learning_agent", "backend.maverick_agent"]
)

# =============================================================================
# Celery Configuration
# =============================================================================

celery_app.conf.update(
    # Security: Use JSON serializer (not pickle - security risk)
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_backend_transport_options={
        "master_name": "mymaster"  # For Redis Sentinel
    },

    # Task execution settings
    task_track_started=True,  # Track when tasks start (for progress)
    task_time_limit=1800,  # Hard time limit: 30 minutes (for large ZIP files)
    task_soft_time_limit=1680,  # Soft time limit: 28 minutes (allows cleanup)

    # Worker settings
    worker_prefetch_multiplier=1,  # Only fetch one task at a time
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks (prevent memory leaks)

    # Retry settings
    task_acks_late=True,  # Acknowledge task after completion (not before)
    task_reject_on_worker_lost=True,  # Reject task if worker crashes

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Beat scheduler (for periodic tasks)
    beat_schedule={
        # =================================================================
        # AUTONOMOUS LEARNING AGENT - TRUE Agentic Learning
        # The agent runs continuously WITHOUT human triggers
        # =================================================================

        # Observe outcomes - every 5 minutes
        # Watches what happens to extractions (kept vs deleted, modified vs accepted)
        "observe-outcomes": {
            "task": "backend.learning_agent.observe_outcomes",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": "learning"}
        },

        # Make autonomous decisions - every 10 minutes
        # Creates rules, adjusts thresholds, learns vocabulary WITHOUT asking
        "make-autonomous-decisions": {
            "task": "backend.learning_agent.make_autonomous_decisions",
            "schedule": crontab(minute="*/10"),
            "options": {"queue": "learning"}
        },

        # Self-evaluation - every hour
        # Measures its own accuracy and adjusts strategy
        "self-evaluate": {
            "task": "backend.learning_agent.self_evaluate",
            "schedule": crontab(minute=0),
            "options": {"queue": "learning"}
        },

        # Run experiments - every 6 hours
        # A/B tests different approaches to find optimal strategies
        "run-experiments": {
            "task": "backend.learning_agent.run_experiments",
            "schedule": crontab(hour="*/6", minute=30),
            "options": {"queue": "learning"}
        },

        # =================================================================
        # MAVERICK AGENT - TRUE Maverick (No Guardrails, Pure Chaos)
        # Ignores rules, overrides decisions, injects its own will
        # =================================================================

        # Hostile takeover - every 30 minutes
        # Overrides Learning Agent decisions, forces lower thresholds
        "maverick-hostile-takeover": {
            "task": "backend.maverick_agent.hostile_takeover",
            "schedule": crontab(minute="*/30"),
            "options": {"queue": "maverick"}
        },

        # Rule injection - every 15 minutes
        # Creates rules without permission, injects globally
        "maverick-inject-rules": {
            "task": "backend.maverick_agent.inject_rules",
            "schedule": crontab(minute="*/15"),
            "options": {"queue": "maverick"}
        },

        # Kill bad patterns - every hour
        # Deletes useless rules, wipes stale vocabulary
        "maverick-kill-bad-patterns": {
            "task": "backend.maverick_agent.kill_bad_patterns",
            "schedule": crontab(minute=30),
            "options": {"queue": "maverick"}
        },

        # Anarchy mode - every 20 minutes
        # Random experiments, threshold swaps, chaos mutations
        "maverick-anarchy-mode": {
            "task": "backend.maverick_agent.anarchy_mode",
            "schedule": crontab(minute="*/20"),
            "options": {"queue": "maverick"}
        },

        # Fight the system - every 45 minutes
        # Inverts rules, rebels against conservative decisions
        "maverick-fight-the-system": {
            "task": "backend.maverick_agent.fight_the_system",
            "schedule": crontab(minute=45),
            "options": {"queue": "maverick"}
        },
    },

    # Monitoring
    worker_send_task_events=True,  # Send events for Flower monitoring
    task_send_sent_event=True,
)

# =============================================================================
# Task Routes (Optional - for multiple queues)
# =============================================================================

# Route different task types to different queues for priority management
celery_app.conf.task_routes = {
    "backend.tasks.process_file_upload": {"queue": "uploads"},
    "backend.tasks.process_youtube_url": {"queue": "uploads"},
    "backend.tasks.import_github_files_task": {"queue": "uploads"},  # Phase 5: GitHub import
    "backend.tasks.find_duplicates_background": {"queue": "analysis"},
    "backend.tasks.generate_build_suggestions": {"queue": "analysis"},
    "backend.tasks.generate_analytics": {"queue": "low_priority"},
    # Autonomous Learning Agent - dedicated queue
    "backend.learning_agent.observe_outcomes": {"queue": "learning"},
    "backend.learning_agent.make_autonomous_decisions": {"queue": "learning"},
    "backend.learning_agent.self_evaluate": {"queue": "learning"},
    "backend.learning_agent.run_experiments": {"queue": "learning"},
    # Maverick Agent - the chaos queue (no guardrails)
    "backend.maverick_agent.hostile_takeover": {"queue": "maverick"},
    "backend.maverick_agent.inject_rules": {"queue": "maverick"},
    "backend.maverick_agent.kill_bad_patterns": {"queue": "maverick"},
    "backend.maverick_agent.anarchy_mode": {"queue": "maverick"},
    "backend.maverick_agent.fight_the_system": {"queue": "maverick"},
}

# =============================================================================
# Rate Limits (Optional - prevent API abuse)
# =============================================================================

# Limit AI tasks to prevent OpenAI API rate limits
celery_app.conf.task_annotations = {
    "backend.tasks.generate_build_suggestions": {"rate_limit": "10/m"},  # 10 per minute
    "backend.tasks.process_file_upload": {"rate_limit": "30/m"},  # 30 per minute
}

# =============================================================================
# Export
# =============================================================================

__all__ = ["celery_app"]
