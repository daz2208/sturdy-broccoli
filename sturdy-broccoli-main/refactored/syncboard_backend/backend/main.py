"""
FastAPI backend for SyncBoard 3.0 Knowledge Bank.

Knowledge-first architecture with auto-clustering and build suggestions.
Boards removed - all content organized by AI-discovered concepts.

This main file handles app initialization and router mounting.
All endpoints are organized in the routers/ directory.
"""

import os
import uuid
import logging
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load environment variables
env_paths = [
    Path(__file__).parent.parent / '.env',
    Path(__file__).parent / '.env',
]
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        break

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Import routers
from .routers import (
    auth, uploads, search, clusters, documents, build_suggestions,
    analytics, ai_generation, duplicates, tags, saved_searches, relationships, jobs,
    integrations, knowledge_bases, admin, knowledge_graph,
    # Phase 10: SyncBoard 3.0 Enhancement routers
    project_goals, project_tracking, n8n_workflows, generated_code,
    # Knowledge tools (gap analysis, flashcards, etc.)
    knowledge_tools,
    # Real-time WebSocket support
    websocket,
    # Team collaboration
    teams,
    # Usage & billing
    usage,
    # Multi-industry content generation
    content_generation,
    # Agentic learning system
    feedback,
    learning,
)

# Import dependencies and shared state
from . import dependencies
from .database import init_db, check_database_health
from .db_storage_adapter import load_storage_from_db, save_storage_to_db
from .storage import load_storage
from .auth import hash_password
from .security_middleware import SecurityHeadersMiddleware, HTTPSRedirectMiddleware
from .redis_client import redis_client
from .config import settings
import threading

# =============================================================================
# Configuration
# =============================================================================

# Configuration now loaded from centralized settings
STORAGE_PATH = settings.storage_path
ALLOWED_ORIGINS = settings.allowed_origins
TESTING = settings.testing

# Logging setup (configurable via environment variable)
LOG_LEVEL = settings.log_level
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)

# =============================================================================
# Cache Reload Subscriber (Redis Pub/Sub)
# =============================================================================

def reload_cache_from_database():
    """Reload in-memory cache from database."""
    try:
        logger.info("Reloading cache from database...")

        # Clear vector store first
        dependencies.vector_store.docs.clear()
        dependencies.vector_store.doc_ids.clear()
        dependencies.vector_store.vectorizer = None
        dependencies.vector_store.doc_matrix = None

        # Load from database
        docs, meta, clusts, usrs = load_storage_from_db(dependencies.vector_store)

        # FIX: Reset _next_id to prevent doc_id collisions
        # Find the max doc_id across all KBs and set _next_id to max + 1
        all_doc_ids = []
        for kb_docs in docs.values():
            all_doc_ids.extend(kb_docs.keys())

        if all_doc_ids:
            max_doc_id = max(all_doc_ids)
            dependencies.vector_store._next_id = max_doc_id + 1
        else:
            dependencies.vector_store._next_id = 0

        # Update global state
        dependencies.documents.clear()
        dependencies.documents.update(docs)
        dependencies.metadata.clear()
        dependencies.metadata.update(meta)
        dependencies.clusters.clear()
        dependencies.clusters.update(clusts)
        dependencies.users.clear()
        dependencies.users.update(usrs)

        total_docs = sum(len(d) for d in docs.values())
        total_clusters = sum(len(c) for c in clusts.values())
        logger.info(f"Cache reloaded: {total_docs} documents in {len(docs)} KBs, {total_clusters} clusters, {len(usrs)} users, next_id={dependencies.vector_store._next_id}")
    except Exception as e:
        logger.error(f"Failed to reload cache: {e}")


def listen_for_data_changes():
    """Background thread that listens for data change notifications via Redis pub/sub."""
    if not redis_client:
        logger.warning("Redis not available, cache auto-reload disabled")
        return

    try:
        pubsub = redis_client.pubsub()
        pubsub.subscribe("syncboard:data_changed")
        logger.info("✅ Subscribed to data change notifications")

        for message in pubsub.listen():
            if message['type'] == 'message':
                logger.debug("Received data_changed notification, reloading cache...")
                reload_cache_from_database()
    except Exception as e:
        logger.error(f"Data change listener error: {e}")


# =============================================================================
# Lifespan Event Handler
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup: Initialize database and load data
    try:
        init_db()
        logger.info("✅ Database initialized")

        # Load from database
        docs, meta, clusts, usrs = load_storage_from_db(dependencies.vector_store)

        # Update global state
        dependencies.documents.update(docs)
        dependencies.metadata.update(meta)
        dependencies.clusters.update(clusts)
        dependencies.users.update(usrs)

        # Count actual documents (nested structure: {kb_id: {doc_id: content}})
        total_docs = sum(len(kb_docs) for kb_docs in docs.values())
        total_clusts = sum(len(kb_clusts) for kb_clusts in clusts.values())
        logger.info(f"Loaded from database: {total_docs} documents in {len(docs)} KBs, {total_clusts} clusters, {len(usrs)} users")
    except Exception as e:
        logger.warning(f"Database load failed: {e}. Falling back to file storage.")
        # Fallback to file storage
        docs, meta, clusts, usrs = load_storage(STORAGE_PATH, dependencies.vector_store)

        # Update global state
        dependencies.documents.update(docs)
        dependencies.metadata.update(meta)
        dependencies.clusters.update(clusts)
        dependencies.users.update(usrs)

        # Count actual documents (nested structure: {kb_id: {doc_id: content}})
        total_docs = sum(len(kb_docs) for kb_docs in docs.values())
        total_clusts = sum(len(kb_clusts) for kb_clusts in clusts.values())
        logger.info(f"Loaded from file: {total_docs} documents in {len(docs)} KBs, {total_clusts} clusters, {len(usrs)} users")

    # Create default test user if none exist
    if not dependencies.users:
        dependencies.users['test'] = hash_password('test123')
        try:
            save_storage_to_db(
                dependencies.documents,
                dependencies.metadata,
                dependencies.clusters,
                dependencies.users
            )
            logger.info("Created default test user in database")
        except Exception as e:
            logger.warning(f"Database save failed: {e}")

    # Start background listener for data changes
    listener_thread = threading.Thread(target=listen_for_data_changes, daemon=True)
    listener_thread.start()
    logger.info("Started data change listener thread")

    yield  # Application runs here

    # Shutdown: cleanup code goes here (if needed)
    logger.info("Application shutting down")

# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="SyncBoard Knowledge Bank",
    description="AI-powered knowledge management with auto-clustering",
    version="3.0.0",
    lifespan=lifespan
)

# Custom rate limit handler with Retry-After header
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom handler for rate limit exceeded errors.
    Includes Retry-After header for better client handling.
    """
    from fastapi.responses import JSONResponse

    # Extract retry time from the exception message (format: "X per Y")
    retry_after = 60  # Default to 60 seconds
    if hasattr(exc, 'detail') and 'per' in str(exc.detail):
        try:
            # Parse "N per minute/hour/etc" format
            parts = str(exc.detail).split()
            if 'minute' in str(exc.detail).lower():
                retry_after = 60
            elif 'hour' in str(exc.detail).lower():
                retry_after = 3600
            elif 'second' in str(exc.detail).lower():
                retry_after = int(parts[0]) if parts[0].isdigit() else 1
        except (IndexError, ValueError):
            pass

    return JSONResponse(
        status_code=429,
        content={
            "detail": str(exc.detail),
            "error": "rate_limit_exceeded",
            "retry_after_seconds": retry_after,
            "message": f"Rate limit exceeded. Please wait {retry_after} seconds before retrying."
        },
        headers={"Retry-After": str(retry_after)}
    )

# Rate limiting (disabled in test mode)
if not TESTING:
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)
    logger.info("🚦 Rate limiting enabled")
else:
    # Create dummy limiter for tests
    limiter = Limiter(key_func=lambda: "test-client")
    app.state.limiter = limiter
    logger.info("🚦 Rate limiting disabled (test mode)")

# CORS
origins = ALLOWED_ORIGINS.split(',') if ALLOWED_ORIGINS != '*' else ['*']

# Warn if using wildcard CORS in production
if origins == ['*']:
    logger.warning(
        "⚠️  SECURITY WARNING: CORS is set to allow ALL origins (*). "
        "This is insecure for production. Set SYNCBOARD_ALLOWED_ORIGINS to specific domains."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers middleware (Phase 2)
environment = settings.environment
logger.info(f"🔒 Running in {environment} environment")

# Add security headers to all responses
app.add_middleware(SecurityHeadersMiddleware, environment=environment)

# Enforce HTTPS in production
if environment == "production":
    app.add_middleware(HTTPSRedirectMiddleware, environment=environment)
    logger.info("🔒 HTTPS enforcement enabled")
else:
    logger.info("ℹ️  HTTPS enforcement disabled (not production)")

# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """
    Add unique request ID to each request for tracing.
    Enables debugging by tracking requests through logs.
    """
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    # Process request
    response = await call_next(request)

    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id

    return response


# Usage tracking middleware (monitors API usage and costs)
from backend.middleware.usage_tracking import usage_tracking_middleware
app.middleware("http")(usage_tracking_middleware)
logger.info("📊 Usage tracking middleware enabled")

# =============================================================================
# Mount Routers
# =============================================================================

# Authentication endpoints
app.include_router(auth.router)

# Upload endpoints
app.include_router(uploads.router)

# Search endpoints
app.include_router(search.router)

# Cluster management endpoints
app.include_router(clusters.router)

# Document CRUD endpoints
app.include_router(documents.router)

# Build suggestion endpoints
app.include_router(build_suggestions.router)

# Analytics endpoints
app.include_router(analytics.router)

# AI generation endpoints
app.include_router(ai_generation.router)

# Phase 7.2: Duplicate detection endpoints
app.include_router(duplicates.router)

# Phase 7.3: Tags endpoints
app.include_router(tags.router)

# Phase 7.4: Saved searches endpoints
app.include_router(saved_searches.router)

# Phase 7.5: Document relationships endpoints
app.include_router(relationships.router)

# Phase 2 (Celery): Background job status endpoints
app.include_router(jobs.router)

# Phase 5: Cloud service integrations endpoints
app.include_router(integrations.router)

# Phase 8: Multi-knowledge base support
app.include_router(knowledge_bases.router)

# Phase 9: Admin/utility endpoints (chunking backfill, etc.)
app.include_router(admin.router)

# Phase 10: Knowledge graph endpoints
app.include_router(knowledge_graph.router)

# Phase 10: SyncBoard 3.0 Enhancement endpoints
app.include_router(project_goals.router)
app.include_router(project_tracking.router)
app.include_router(n8n_workflows.router)
app.include_router(generated_code.router)

# Knowledge Tools (gap analysis, flashcards, learning paths, etc.)
app.include_router(knowledge_tools.router)

# Real-time WebSocket support
app.include_router(websocket.router)

# Team collaboration
app.include_router(teams.router)

# Usage & billing
app.include_router(usage.router)

# Multi-industry content generation
app.include_router(content_generation.router)

# Agentic learning system
app.include_router(feedback.router)
app.include_router(learning.router)

# =============================================================================
# Health Check Endpoint
# =============================================================================

@app.get("/health", tags=["health"])
async def health_check():
    """
    Enhanced health check endpoint.

    Returns system status and dependency health for monitoring.
    Includes disk space, vector store size, and data integrity checks.
    """
    import shutil

    # Basic statistics
    # Note: documents and clusters are nested by knowledge base ID
    # so we need to sum across all KBs to get the actual counts
    total_documents = sum(len(kb_docs) for kb_docs in dependencies.documents.values())
    total_clusters = sum(len(kb_clusters) for kb_clusters in dependencies.clusters.values())

    health_data = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "statistics": {
            "documents": total_documents,
            "clusters": total_clusters,
            "users": len(dependencies.users),
            "knowledge_bases": len(dependencies.documents),  # Number of KBs
            "vector_store_size": len(dependencies.vector_store.docs) if hasattr(dependencies.vector_store, 'docs') else 0
        },
        "dependencies": {}
    }

    # Check disk space
    try:
        disk_usage = shutil.disk_usage("/")
        disk_free_gb = disk_usage.free / (1024 ** 3)
        health_data["dependencies"]["disk_space_gb"] = round(disk_free_gb, 2)
        health_data["dependencies"]["disk_healthy"] = disk_free_gb > 1.0  # At least 1GB free
    except Exception as e:
        health_data["dependencies"]["disk_space_gb"] = "error"
        health_data["dependencies"]["disk_healthy"] = False
        logger.error(f"Failed to check disk space: {e}")

    # Check storage file
    try:
        storage_path = Path(STORAGE_PATH)
        if storage_path.exists():
            file_size_mb = storage_path.stat().st_size / (1024 ** 2)
            health_data["dependencies"]["storage_file_mb"] = round(file_size_mb, 2)
            health_data["dependencies"]["storage_file_exists"] = True
        else:
            health_data["dependencies"]["storage_file_exists"] = False
    except Exception as e:
        health_data["dependencies"]["storage_file_exists"] = "error"
        logger.error(f"Failed to check storage file: {e}")

    # Check OpenAI API
    try:
        openai_key = settings.openai_api_key
        health_data["dependencies"]["openai_configured"] = bool(openai_key and openai_key.startswith('sk-'))
    except Exception:
        health_data["dependencies"]["openai_configured"] = False

    # Check database health
    try:
        db_health = check_database_health()
        health_data["dependencies"]["database"] = db_health
    except Exception as e:
        health_data["dependencies"]["database"] = {
            "database_connected": False,
            "error": str(e)
        }
        logger.error(f"Failed to check database health: {e}")

    # Overall health status
    all_healthy = all([
        health_data["dependencies"].get("disk_healthy", False),
        health_data["dependencies"].get("storage_file_exists", False) or health_data["dependencies"].get("database", {}).get("database_connected", False),
        health_data["dependencies"].get("openai_configured", False)
    ])

    if not all_healthy:
        health_data["status"] = "degraded"

    return health_data

# =============================================================================
# Mount Static Files
# =============================================================================

try:
    static_path = Path(__file__).parent / 'static'
    if static_path.exists():
        app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")
