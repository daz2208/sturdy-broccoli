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
        # MAVERICK AGENT - Continuous Improvement Challenger
        # Challenges decisions, proposes improvements, tests hypotheses
        # =================================================================

        # Challenge decisions - every 30 minutes
        # Questions existing decisions and proposes improvement hypotheses
        "maverick-challenge-decisions": {
            "task": "backend.maverick_agent.challenge_decisions",
            "schedule": crontab(minute="*/30"),
            "options": {"queue": "maverick"}
        },

        # Test hypotheses - every 15 minutes
        # Starts testing proposed improvements
        "maverick-test-hypotheses": {
            "task": "backend.maverick_agent.test_hypotheses",
            "schedule": crontab(minute="*/15"),
            "options": {"queue": "maverick"}
        },

        # Measure and learn - every 20 minutes
        # Measures outcomes of tests and learns what works
        "maverick-measure-and-learn": {
            "task": "backend.maverick_agent.measure_and_learn",
            "schedule": crontab(minute="*/20"),
            "options": {"queue": "maverick"}
        },

        # Apply improvements - every hour
        # Applies validated improvements permanently
        "maverick-apply-improvements": {
            "task": "backend.maverick_agent.apply_improvements",
            "schedule": crontab(minute=0),
            "options": {"queue": "maverick"}
        },

        # Self-improve - every 2 hours
        # Improves Maverick's own strategy based on what it learned
        "maverick-self-improve": {
            "task": "backend.maverick_agent.self_improve",
            "schedule": crontab(hour="*/2", minute=30),
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
    "backend.tasks.process_url_upload": {"queue": "uploads"},  # Handles YouTube, web articles, etc.
    "backend.tasks.process_image_upload": {"queue": "uploads"},  # Image/OCR processing
    "backend.tasks.import_github_files_task": {"queue": "uploads"},  # Phase 5: GitHub import
    "backend.tasks.find_duplicates_background": {"queue": "analysis"},
    "backend.tasks.generate_build_suggestions": {"queue": "analysis"},
    # Autonomous Learning Agent - dedicated queue
    "backend.learning_agent.observe_outcomes": {"queue": "learning"},
    "backend.learning_agent.make_autonomous_decisions": {"queue": "learning"},
    "backend.learning_agent.self_evaluate": {"queue": "learning"},
    "backend.learning_agent.run_experiments": {"queue": "learning"},
    # Maverick Agent - continuous improvement queue
    "backend.maverick_agent.challenge_decisions": {"queue": "maverick"},
    "backend.maverick_agent.test_hypotheses": {"queue": "maverick"},
    "backend.maverick_agent.measure_and_learn": {"queue": "maverick"},
    "backend.maverick_agent.apply_improvements": {"queue": "maverick"},
    "backend.maverick_agent.self_improve": {"queue": "maverick"},
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
