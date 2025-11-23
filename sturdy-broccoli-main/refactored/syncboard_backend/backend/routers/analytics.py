"""
Analytics Router for SyncBoard 3.0 Knowledge Bank.

Endpoints:
- GET /analytics - Get comprehensive analytics for user's knowledge bank
"""

import logging
from fastapi import APIRouter, HTTPException, Depends

from ..models import User
from ..dependencies import get_current_user
from ..analytics_service import AnalyticsService
from ..database import get_db_context
from ..redis_client import get_cached_analytics, cache_analytics

# Initialize logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="",
    tags=["analytics"],
    responses={401: {"description": "Unauthorized"}},
)

# =============================================================================
# Analytics Endpoint
# =============================================================================

@router.get("/analytics")
async def get_analytics(
    time_period: int = 30,
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive analytics for the user's knowledge bank.

    Args:
        time_period: Number of days for time-series data (default: 30)
        current_user: Authenticated user

    Returns:
        Complete analytics including:
        - Overview statistics (total docs, clusters, concepts)
        - Time-series data (document growth over time)
        - Distribution metrics (clusters, skill levels, source types)
        - Top concepts
        - Recent activity

    Raises:
        HTTPException 500: If analytics generation fails
    """
    try:
        # Check cache first (5-10x faster for cached results)
        cached_data = get_cached_analytics(
            user_id=current_user.username,
            time_period=str(time_period)
        )

        if cached_data:
            logger.info(f"Cache HIT: Analytics for {current_user.username} (period={time_period})")
            return cached_data

        # Cache miss - compute analytics
        logger.info(f"Cache MISS: Computing analytics for {current_user.username} (period={time_period})")
        with get_db_context() as db:
            analytics = AnalyticsService(db)
            data = analytics.get_complete_analytics(
                username=current_user.username,
                time_period_days=time_period
            )

            # Cache the result for 10 minutes (600 seconds)
            cache_analytics(
                user_id=current_user.username,
                analytics_data=data,
                time_period=str(time_period),
                ttl=600
            )

            return data
    except Exception as e:
        logger.error(f"Analytics failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate analytics: {str(e)}"
        )
