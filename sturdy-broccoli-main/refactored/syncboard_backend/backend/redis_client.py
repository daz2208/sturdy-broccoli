"""
Redis Cache Client for SyncBoard 3.0 Knowledge Bank.

Provides caching utilities for:
- Analytics results
- Build suggestions
- Duplicate detection results
- Rate limiting counters

Uses Redis for fast in-memory caching with TTL (time-to-live) expiration.
"""

import json
import logging
from typing import Optional, Any
import redis
from redis.exceptions import RedisError, ConnectionError

from .config import settings

# Initialize logger
logger = logging.getLogger(__name__)

# =============================================================================
# Redis Connection
# =============================================================================

# Redis connection URL from centralized configuration
REDIS_URL = settings.redis_url

# Initialize Redis client
try:
    redis_client = redis.from_url(
        REDIS_URL,
        decode_responses=True,  # Auto-decode bytes to strings
        socket_connect_timeout=5,
        socket_keepalive=True,
        health_check_interval=30
    )
    # Test connection
    redis_client.ping()
    logger.info(f"✅ Redis connected: {REDIS_URL}")
except (RedisError, ConnectionError) as e:
    logger.warning(f"⚠️  Redis connection failed: {e}. Caching disabled.")
    redis_client = None  # Graceful degradation if Redis unavailable


# =============================================================================
# Cache Functions
# =============================================================================

def get_cache(key: str) -> Optional[Any]:
    """
    Get value from cache.

    Args:
        key: Cache key

    Returns:
        Cached value (parsed from JSON) or None if not found
    """
    if not redis_client:
        return None

    try:
        value = redis_client.get(key)
        if value:
            return json.loads(value)
        return None
    except (RedisError, json.JSONDecodeError) as e:
        logger.warning(f"Cache get error for key '{key}': {e}")
        return None


def set_cache(key: str, value: Any, ttl: int = 300) -> bool:
    """
    Set value in cache with TTL.

    Args:
        key: Cache key
        value: Value to cache (will be JSON-serialized)
        ttl: Time-to-live in seconds (default: 5 minutes)

    Returns:
        True if successful, False otherwise
    """
    if not redis_client:
        return False

    try:
        serialized = json.dumps(value)
        redis_client.setex(key, ttl, serialized)
        return True
    except (RedisError, TypeError) as e:
        logger.warning(f"Cache set error for key '{key}': {e}")
        return False


def delete_cache(key: str) -> bool:
    """
    Delete value from cache.

    Args:
        key: Cache key

    Returns:
        True if successful, False otherwise
    """
    if not redis_client:
        return False

    try:
        redis_client.delete(key)
        return True
    except RedisError as e:
        logger.warning(f"Cache delete error for key '{key}': {e}")
        return False


def invalidate_pattern(pattern: str) -> int:
    """
    Invalidate all cache keys matching a pattern.

    Args:
        pattern: Redis key pattern (e.g., "user:123:*")

    Returns:
        Number of keys deleted
    """
    if not redis_client:
        return 0

    try:
        keys = redis_client.keys(pattern)
        if keys:
            return redis_client.delete(*keys)
        return 0
    except RedisError as e:
        logger.warning(f"Cache invalidate error for pattern '{pattern}': {e}")
        return 0


# =============================================================================
# Analytics Caching
# =============================================================================

def get_cached_analytics(user_id: str, time_period: Optional[str] = None) -> Optional[dict]:
    """
    Get cached analytics for a user.

    Args:
        user_id: Username
        time_period: Optional time period filter

    Returns:
        Cached analytics dict or None
    """
    cache_key = f"analytics:{user_id}"
    if time_period:
        cache_key += f":{time_period}"
    return get_cache(cache_key)


def cache_analytics(user_id: str, analytics_data: dict, time_period: Optional[str] = None, ttl: int = 300) -> bool:
    """
    Cache analytics results.

    Args:
        user_id: Username
        analytics_data: Analytics data to cache
        time_period: Optional time period filter
        ttl: Time-to-live in seconds (default: 5 minutes)

    Returns:
        True if successful
    """
    cache_key = f"analytics:{user_id}"
    if time_period:
        cache_key += f":{time_period}"
    return set_cache(cache_key, analytics_data, ttl)


def invalidate_analytics(user_id: str) -> int:
    """
    Invalidate all analytics cache for a user.

    Args:
        user_id: Username

    Returns:
        Number of keys deleted
    """
    return invalidate_pattern(f"analytics:{user_id}*")


# =============================================================================
# Build Suggestions Caching
# =============================================================================

def get_cached_build_suggestions(user_id: str) -> Optional[dict]:
    """
    Get cached build suggestions for a user.

    Args:
        user_id: Username

    Returns:
        Cached suggestions dict or None
    """
    cache_key = f"build_suggestions:{user_id}"
    return get_cache(cache_key)


def cache_build_suggestions(user_id: str, suggestions: dict, ttl: int = 1800) -> bool:
    """
    Cache build suggestions.

    Args:
        user_id: Username
        suggestions: Suggestions data to cache
        ttl: Time-to-live in seconds (default: 30 minutes)

    Returns:
        True if successful
    """
    cache_key = f"build_suggestions:{user_id}"
    return set_cache(cache_key, suggestions, ttl)


def invalidate_build_suggestions(user_id: str) -> bool:
    """
    Invalidate build suggestions cache for a user.

    Args:
        user_id: Username

    Returns:
        True if successful
    """
    cache_key = f"build_suggestions:{user_id}"
    return delete_cache(cache_key)


# =============================================================================
# Duplicate Detection Caching
# =============================================================================

def get_cached_duplicates(user_id: str, threshold: float) -> Optional[dict]:
    """
    Get cached duplicate detection results.

    Args:
        user_id: Username
        threshold: Similarity threshold used

    Returns:
        Cached duplicates dict or None
    """
    cache_key = f"duplicates:{user_id}:{threshold}"
    return get_cache(cache_key)


def cache_duplicates(user_id: str, threshold: float, duplicates: dict, ttl: int = 86400) -> bool:
    """
    Cache duplicate detection results.

    Args:
        user_id: Username
        threshold: Similarity threshold used
        duplicates: Duplicates data to cache
        ttl: Time-to-live in seconds (default: 24 hours)

    Returns:
        True if successful
    """
    cache_key = f"duplicates:{user_id}:{threshold}"
    return set_cache(cache_key, duplicates, ttl)


def invalidate_duplicates(user_id: str) -> int:
    """
    Invalidate all duplicate detection cache for a user.

    Args:
        user_id: Username

    Returns:
        Number of keys deleted
    """
    return invalidate_pattern(f"duplicates:{user_id}*")


# =============================================================================
# Rate Limiting (Job Queue)
# =============================================================================

def increment_user_job_count(user_id: str, ttl: int = 3600) -> int:
    """
    Increment user's active job count (for rate limiting).

    Args:
        user_id: Username
        ttl: Time-to-live in seconds (default: 1 hour)

    Returns:
        Current job count
    """
    if not redis_client:
        return 0

    try:
        key = f"user:{user_id}:jobs:count"
        count = redis_client.incr(key)
        if count == 1:  # First increment, set TTL
            redis_client.expire(key, ttl)
        return count
    except RedisError as e:
        logger.warning(f"Job count increment error for user '{user_id}': {e}")
        return 0


def get_user_job_count(user_id: str) -> int:
    """
    Get user's current active job count.

    Args:
        user_id: Username

    Returns:
        Current job count
    """
    if not redis_client:
        return 0

    try:
        key = f"user:{user_id}:jobs:count"
        count = redis_client.get(key)
        return int(count) if count else 0
    except (RedisError, ValueError) as e:
        logger.warning(f"Job count get error for user '{user_id}': {e}")
        return 0


def decrement_user_job_count(user_id: str) -> int:
    """
    Decrement user's active job count.

    Args:
        user_id: Username

    Returns:
        Current job count
    """
    if not redis_client:
        return 0

    try:
        key = f"user:{user_id}:jobs:count"
        count = redis_client.decr(key)
        return max(0, count)  # Don't go below 0
    except RedisError as e:
        logger.warning(f"Job count decrement error for user '{user_id}': {e}")
        return 0


# =============================================================================
# Search Results Caching
# =============================================================================

def get_cached_search(user_id: str, query: str, filters: dict) -> Optional[dict]:
    """
    Get cached search results.

    Args:
        user_id: Username
        query: Search query
        filters: Search filters (cluster_id, source_type, skill_level, etc.)

    Returns:
        Cached search results dict or None
    """
    import hashlib
    import json

    # Create cache key from query + filters
    filter_str = json.dumps(filters, sort_keys=True)
    cache_hash = hashlib.md5(f"{query}:{filter_str}".encode()).hexdigest()
    cache_key = f"search:{user_id}:{cache_hash}"
    return get_cache(cache_key)


def cache_search(user_id: str, query: str, filters: dict, results: dict, ttl: int = 300) -> bool:
    """
    Cache search results.

    Args:
        user_id: Username
        query: Search query
        filters: Search filters
        results: Search results to cache
        ttl: Time-to-live in seconds (default: 5 minutes)

    Returns:
        True if successful
    """
    import hashlib
    import json

    filter_str = json.dumps(filters, sort_keys=True)
    cache_hash = hashlib.md5(f"{query}:{filter_str}".encode()).hexdigest()
    cache_key = f"search:{user_id}:{cache_hash}"
    return set_cache(cache_key, results, ttl)


def invalidate_search(user_id: str) -> int:
    """
    Invalidate all search cache for a user.

    Args:
        user_id: Username

    Returns:
        Number of keys deleted
    """
    return invalidate_pattern(f"search:{user_id}*")


# =============================================================================
# Data Change Notifications (Pub/Sub)
# =============================================================================

def notify_data_changed():
    """
    Notify that data has changed (for cache invalidation).
    Publishes to Redis pub/sub channel so backend can reload from database.
    """
    if not redis_client:
        return

    try:
        redis_client.publish("syncboard:data_changed", "reload")
        logger.debug("Published data_changed notification")
    except RedisError as e:
        logger.warning(f"Failed to publish data_changed notification: {e}")


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "redis_client",
    "get_cache",
    "set_cache",
    "delete_cache",
    "invalidate_pattern",
    "get_cached_analytics",
    "cache_analytics",
    "invalidate_analytics",
    "get_cached_build_suggestions",
    "cache_build_suggestions",
    "invalidate_build_suggestions",
    "get_cached_duplicates",
    "cache_duplicates",
    "invalidate_duplicates",
    "get_cached_search",
    "cache_search",
    "invalidate_search",
    "increment_user_job_count",
    "get_user_job_count",
    "decrement_user_job_count",
    "notify_data_changed",
]
