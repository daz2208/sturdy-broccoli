"""
Usage & Billing Router for SyncBoard 3.0 Monetization.

Endpoints:
- GET /usage - Get current usage for authenticated user
- GET /usage/history - Get usage history
- GET /subscription - Get subscription details
- POST /subscription/upgrade - Upgrade subscription plan
- GET /plans - List available plans with limits

Admin endpoints:
- GET /admin/usage/{username} - Get user's usage (admin)
- PUT /admin/subscription/{username} - Modify user subscription (admin)
- POST /admin/rate-limit-override - Create rate limit override
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..models import User
from ..dependencies import get_current_user
from ..database import get_db
from ..db_models import DBUserSubscription, DBUsageRecord, DBRateLimitOverride, DBUser

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(
    prefix="/usage",
    tags=["usage"],
    responses={401: {"description": "Unauthorized"}},
)


# =============================================================================
# Plan Definitions
# =============================================================================

PLAN_LIMITS: Dict[str, Dict[str, Any]] = {
    "free": {
        "name": "Free",
        "price_monthly": 0,
        "api_calls_per_minute": 10,
        "api_calls_per_day": 100,
        "documents_per_month": 50,
        "ai_requests_per_day": 10,
        "storage_mb": 100,
        "knowledge_bases": 1,
        "team_members": 0,
        "features": ["Basic search", "Document upload", "Concept extraction"]
    },
    "starter": {
        "name": "Starter",
        "price_monthly": 9,
        "api_calls_per_minute": 30,
        "api_calls_per_day": 1000,
        "documents_per_month": 500,
        "ai_requests_per_day": 50,
        "storage_mb": 1000,
        "knowledge_bases": 5,
        "team_members": 0,
        "features": ["Everything in Free", "Priority processing", "Export features", "Advanced analytics"]
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 29,
        "api_calls_per_minute": 100,
        "api_calls_per_day": 10000,
        "documents_per_month": 5000,
        "ai_requests_per_day": 200,
        "storage_mb": 10000,
        "knowledge_bases": 20,
        "team_members": 5,
        "features": ["Everything in Starter", "Team collaboration", "API access", "Custom integrations", "Priority support"]
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": 99,
        "api_calls_per_minute": 500,
        "api_calls_per_day": 100000,
        "documents_per_month": -1,  # Unlimited
        "ai_requests_per_day": 1000,
        "storage_mb": 100000,
        "knowledge_bases": -1,  # Unlimited
        "team_members": -1,  # Unlimited
        "features": ["Everything in Pro", "Unlimited documents", "Dedicated support", "Custom SLA", "SSO/SAML", "On-premise option"]
    }
}


# =============================================================================
# Request/Response Models
# =============================================================================

class SubscriptionResponse(BaseModel):
    plan: str
    status: str
    started_at: datetime
    expires_at: Optional[datetime]
    trial_ends_at: Optional[datetime]
    limits: Dict[str, Any]

    class Config:
        from_attributes = True


class UsageResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    api_calls: int
    documents_uploaded: int
    ai_requests: int
    storage_bytes: int
    search_queries: int
    build_suggestions: int
    limits: Dict[str, Any]
    usage_percentage: Dict[str, float]


class PlanResponse(BaseModel):
    id: str
    name: str
    price_monthly: int
    limits: Dict[str, Any]
    features: List[str]


class UpgradeRequest(BaseModel):
    plan: str = Field(..., pattern="^(starter|pro|enterprise)$")


# =============================================================================
# Helper Functions
# =============================================================================

def get_or_create_subscription(db: Session, username: str) -> DBUserSubscription:
    """Get or create a subscription for a user."""
    subscription = db.query(DBUserSubscription).filter(
        DBUserSubscription.username == username
    ).first()

    if not subscription:
        subscription = DBUserSubscription(
            username=username,
            plan="free",
            status="active"
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)

    return subscription


def get_current_usage(db: Session, subscription_id: int, username: str) -> DBUsageRecord:
    """Get or create current month's usage record."""
    now = datetime.utcnow()
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    period_end = (period_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)

    usage = db.query(DBUsageRecord).filter(
        DBUsageRecord.subscription_id == subscription_id,
        DBUsageRecord.period_start == period_start
    ).first()

    if not usage:
        usage = DBUsageRecord(
            subscription_id=subscription_id,
            username=username,
            period_start=period_start,
            period_end=period_end
        )
        db.add(usage)
        db.commit()
        db.refresh(usage)

    return usage


def get_user_limits(db: Session, username: str, plan: str) -> Dict[str, Any]:
    """Get effective limits for a user (plan limits + overrides)."""
    base_limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"]).copy()

    # Check for overrides
    override = db.query(DBRateLimitOverride).filter(
        DBRateLimitOverride.username == username
    ).first()

    if override and (not override.expires_at or override.expires_at > datetime.utcnow()):
        if override.max_api_calls_per_minute:
            base_limits["api_calls_per_minute"] = override.max_api_calls_per_minute
        if override.max_api_calls_per_day:
            base_limits["api_calls_per_day"] = override.max_api_calls_per_day
        if override.max_documents_per_month:
            base_limits["documents_per_month"] = override.max_documents_per_month
        if override.max_ai_requests_per_day:
            base_limits["ai_requests_per_day"] = override.max_ai_requests_per_day
        if override.max_storage_bytes:
            base_limits["storage_mb"] = override.max_storage_bytes // (1024 * 1024)

    return base_limits


def calculate_usage_percentage(usage: DBUsageRecord, limits: Dict[str, Any]) -> Dict[str, float]:
    """Calculate usage as percentage of limits."""
    def calc_pct(used: int, limit: int) -> float:
        if limit <= 0:  # Unlimited
            return 0.0
        return min(100.0, (used / limit) * 100)

    return {
        "api_calls": calc_pct(usage.api_calls, limits.get("api_calls_per_day", 100)),
        "documents": calc_pct(usage.documents_uploaded, limits.get("documents_per_month", 50)),
        "ai_requests": calc_pct(usage.ai_requests, limits.get("ai_requests_per_day", 10)),
        "storage": calc_pct(usage.storage_bytes, limits.get("storage_mb", 100) * 1024 * 1024),
        "search_queries": 0.0,  # Usually unlimited
        "build_suggestions": 0.0  # Usually unlimited
    }


async def check_quota(db: Session, username: str, resource: str, amount: int = 1) -> bool:
    """
    Check if user has quota for a resource. Returns True if allowed, False if exceeded.

    Usage:
        if not await check_quota(db, username, "documents"):
            raise HTTPException(429, "Document upload quota exceeded")
    """
    subscription = get_or_create_subscription(db, username)
    usage = get_current_usage(db, subscription.id, username)
    limits = get_user_limits(db, username, subscription.plan)

    resource_map = {
        "api_calls": ("api_calls", "api_calls_per_day"),
        "documents": ("documents_uploaded", "documents_per_month"),
        "ai_requests": ("ai_requests", "ai_requests_per_day"),
        "storage": ("storage_bytes", "storage_mb"),
    }

    if resource not in resource_map:
        return True

    usage_field, limit_field = resource_map[resource]
    current = getattr(usage, usage_field, 0)
    limit = limits.get(limit_field, 0)

    # -1 means unlimited
    if limit == -1:
        return True

    # Special handling for storage (convert MB to bytes)
    if resource == "storage":
        limit = limit * 1024 * 1024

    return current + amount <= limit


async def increment_usage(db: Session, username: str, resource: str, amount: int = 1):
    """Increment usage counter for a resource."""
    subscription = get_or_create_subscription(db, username)
    usage = get_current_usage(db, subscription.id, username)

    resource_map = {
        "api_calls": "api_calls",
        "documents": "documents_uploaded",
        "ai_requests": "ai_requests",
        "storage": "storage_bytes",
        "search_queries": "search_queries",
        "build_suggestions": "build_suggestions"
    }

    if resource in resource_map:
        field = resource_map[resource]
        setattr(usage, field, getattr(usage, field, 0) + amount)
        db.commit()


# =============================================================================
# User Endpoints
# =============================================================================

@router.get("", response_model=UsageResponse)
async def get_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current usage for authenticated user."""
    subscription = get_or_create_subscription(db, current_user.username)
    usage = get_current_usage(db, subscription.id, current_user.username)
    limits = get_user_limits(db, current_user.username, subscription.plan)

    return UsageResponse(
        period_start=usage.period_start,
        period_end=usage.period_end,
        api_calls=usage.api_calls,
        documents_uploaded=usage.documents_uploaded,
        ai_requests=usage.ai_requests,
        storage_bytes=usage.storage_bytes,
        search_queries=usage.search_queries,
        build_suggestions=usage.build_suggestions,
        limits=limits,
        usage_percentage=calculate_usage_percentage(usage, limits)
    )


@router.get("/history")
async def get_usage_history(
    months: int = Query(6, ge=1, le=24),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get usage history for past months."""
    subscription = get_or_create_subscription(db, current_user.username)

    cutoff = datetime.utcnow() - timedelta(days=months * 31)

    records = db.query(DBUsageRecord).filter(
        DBUsageRecord.subscription_id == subscription.id,
        DBUsageRecord.period_start >= cutoff
    ).order_by(DBUsageRecord.period_start.desc()).all()

    return [{
        "period": r.period_start.strftime("%Y-%m"),
        "api_calls": r.api_calls,
        "documents_uploaded": r.documents_uploaded,
        "ai_requests": r.ai_requests,
        "storage_bytes": r.storage_bytes,
        "search_queries": r.search_queries
    } for r in records]


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get subscription details for authenticated user."""
    subscription = get_or_create_subscription(db, current_user.username)
    limits = get_user_limits(db, current_user.username, subscription.plan)

    return SubscriptionResponse(
        plan=subscription.plan,
        status=subscription.status,
        started_at=subscription.started_at,
        expires_at=subscription.expires_at,
        trial_ends_at=subscription.trial_ends_at,
        limits=limits
    )


@router.post("/subscription/upgrade")
async def upgrade_subscription(
    req: UpgradeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upgrade subscription plan.

    Note: In production, this would integrate with Stripe/payment processor.
    This is a simplified version for demonstration.
    """
    subscription = get_or_create_subscription(db, current_user.username)

    if subscription.plan == req.plan:
        raise HTTPException(status_code=400, detail="Already on this plan")

    # In production: Create Stripe checkout session here
    # For now, just update the plan
    subscription.plan = req.plan
    subscription.updated_at = datetime.utcnow()
    db.commit()

    logger.info(f"User {current_user.username} upgraded to {req.plan}")

    return {
        "message": f"Upgraded to {req.plan} plan",
        "plan": req.plan,
        "limits": PLAN_LIMITS[req.plan]
    }


@router.get("/plans", response_model=List[PlanResponse])
async def list_plans():
    """List all available subscription plans."""
    return [
        PlanResponse(
            id=plan_id,
            name=plan["name"],
            price_monthly=plan["price_monthly"],
            limits={k: v for k, v in plan.items() if k not in ["name", "price_monthly", "features"]},
            features=plan["features"]
        )
        for plan_id, plan in PLAN_LIMITS.items()
    ]


# =============================================================================
# Quota Checking Middleware Helper
# =============================================================================

def require_quota(resource: str, amount: int = 1):
    """
    Dependency to check quota before allowing an endpoint.

    Usage:
        @router.post("/upload")
        async def upload(
            ...,
            _quota = Depends(require_quota("documents"))
        ):
    """
    async def check(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        has_quota = await check_quota(db, current_user.username, resource, amount)
        if not has_quota:
            raise HTTPException(
                status_code=429,
                detail=f"Quota exceeded for {resource}. Please upgrade your plan."
            )
        return True

    return check
