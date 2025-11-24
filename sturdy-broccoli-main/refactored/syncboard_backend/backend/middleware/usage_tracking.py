"""
Usage Tracking Middleware for SyncBoard 3.0

Tracks API usage per user for:
- Request counting
- Cost monitoring
- Rate limiting enforcement
- Usage analytics
"""

from fastapi import Request, Response
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import Callable
import time

from backend.database import SessionLocal
from backend.db_models import DBUsageRecord, DBUserSubscription
from backend.auth import get_username_from_token


async def usage_tracking_middleware(request: Request, call_next: Callable) -> Response:
    """
    Track API usage for authenticated requests.

    Records:
    - API endpoint called
    - Request duration
    - Response status
    - User making the request
    """
    start_time = time.time()
    username = None

    # Get username from token if present
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
        try:
            username = get_username_from_token(token)
        except Exception:
            pass  # Invalid token, skip tracking

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000

    # Track usage if authenticated
    if username and not request.url.path.startswith("/docs") and not request.url.path.startswith("/openapi"):
        db = SessionLocal()
        try:
            # Get or create user subscription
            subscription = db.query(DBUserSubscription).filter_by(username=username).first()
            if not subscription:
                # Create default free subscription
                subscription = DBUserSubscription(
                    username=username,
                    plan="free",
                    status="active",
                    created_at=datetime.utcnow()
                )
                db.add(subscription)
                db.commit()
                db.refresh(subscription)

            # Get current period's usage record
            period_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_end = (period_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)

            usage_record = db.query(DBUsageRecord).filter(
                DBUsageRecord.username == username,
                DBUsageRecord.period_start == period_start
            ).first()

            if not usage_record:
                # Create new usage record for this period
                usage_record = DBUsageRecord(
                    subscription_id=subscription.id,
                    username=username,
                    period_start=period_start,
                    period_end=period_end,
                    api_calls=0,
                    documents_uploaded=0,
                    ai_requests=0,
                    storage_bytes=0,
                    search_queries=0,
                    build_suggestions=0,
                    created_at=datetime.utcnow()
                )
                db.add(usage_record)

            # Increment API calls counter
            usage_record.api_calls += 1

            # Track specific endpoint types
            if "/upload" in request.url.path or request.method == "POST" and "/documents" in request.url.path:
                usage_record.documents_uploaded += 1

            if "/knowledge/" in request.url.path or "/concepts" in request.url.path:
                usage_record.ai_requests += 1

            if "/search" in request.url.path:
                usage_record.search_queries += 1

            if "/build" in request.url.path or "/suggest" in request.url.path:
                usage_record.build_suggestions += 1

            db.commit()

        except Exception as e:
            print(f"Usage tracking error: {e}")
            db.rollback()
        finally:
            db.close()

    return response
