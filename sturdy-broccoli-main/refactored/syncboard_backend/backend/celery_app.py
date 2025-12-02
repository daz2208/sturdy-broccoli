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

from celery import Celery
from celery.schedules import crontab
from backend.config import settings

# =============================================================================
# Configuration
# =============================================================================

# Configuration loaded from centralized settings
REDIS_URL = settings.redis_url

# Celery broker and result backend (both use Redis)
CELERY_BROKER_URL = settings.effective_celery_broker_url
CELERY_RESULT_BACKEND = settings.effective_celery_result_backend

# =============================================================================
# Celery App Instance
# =============================================================================

celery_app = Celery(
    "syncboard",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["backend.tasks"]
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
        # No scheduled tasks currently configured
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
