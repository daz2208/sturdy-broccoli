"""
Redis-based caching layer for SyncBoard 3.0 Knowledge Bank.

Provides intelligent caching for expensive operations:
- Concept extraction results (AI API calls)
- Content similarity checks
- Computed analytics

Improvement #5: Save 20-40% on API costs by caching repeated/similar content.
"""

import os
import json
import hashlib
import logging
from typing import Optional, Dict, Any
from datetime import timedelta

logger = logging.getLogger(__name__)

# Redis connection (lazy-loaded)
_redis_client = None


def get_redis_client():
    """
    Get or create Redis client with connection pooling.

    Returns:
        Redis client instance or None if Redis is unavailable
    """
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    try:
        import redis
        from redis.connection import ConnectionPool

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        # Create connection pool for efficiency
        pool = ConnectionPool.from_url(
            redis_url,
            max_connections=20,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
            decode_responses=True  # Automatically decode bytes to strings
        )

        _redis_client = redis.Redis(connection_pool=pool)

        # Test connection
        _redis_client.ping()
        logger.info(f"Redis connection established: {redis_url}")

        return _redis_client

    except ImportError:
        logger.warning("redis package not installed - caching disabled")
        return None
    except Exception as e:
        logger.warning(f"Redis connection failed: {e} - caching disabled")
        return None


def generate_cache_key(prefix: str, content: str, **kwargs) -> str:
    """
    Generate a deterministic cache key for content.

    Uses SHA256 hash of content + parameters to create unique key.

    Args:
        prefix: Key prefix (e.g., "concept_extraction", "similarity")
        content: Content to hash
        **kwargs: Additional parameters that affect the result

    Returns:
        Cache key string (e.g., "concept_extraction:abc123def456")
    """
    # Normalize content: strip whitespace, lowercase
    normalized_content = content.strip().lower()

    # Create hash input: content + sorted kwargs
    hash_input = normalized_content
    if kwargs:
        # Sort kwargs for deterministic hashing
        sorted_params = json.dumps(kwargs, sort_keys=True)
        hash_input += sorted_params

    # Generate SHA256 hash (first 16 chars for brevity)
    content_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()[:16]

    return f"{prefix}:{content_hash}"


def get_cached_result(key: str) -> Optional[Dict]:
    """
    Get cached result by key.

    Args:
        key: Cache key

    Returns:
        Cached dict/result or None if not found
    """
    redis = get_redis_client()
    if redis is None:
        return None

    try:
        cached = redis.get(key)
        if cached:
            logger.debug(f"Cache HIT: {key}")
            return json.loads(cached)
        else:
            logger.debug(f"Cache MISS: {key}")
            return None
    except Exception as e:
        logger.warning(f"Cache read error: {e}")
        return None


def set_cached_result(key: str, result: Dict, ttl_seconds: int = 86400) -> bool:
    """
    Store result in cache with expiration.

    Args:
        key: Cache key
        result: Dict/result to cache
        ttl_seconds: Time-to-live in seconds (default: 24 hours)

    Returns:
        True if stored successfully, False otherwise
    """
    redis = get_redis_client()
    if redis is None:
        return False

    try:
        redis.setex(
            key,
            ttl_seconds,
            json.dumps(result)
        )
        logger.debug(f"Cache SET: {key} (TTL: {ttl_seconds}s)")
        return True
    except Exception as e:
        logger.warning(f"Cache write error: {e}")
        return False


def invalidate_cache(pattern: str = None) -> int:
    """
    Invalidate cache entries matching pattern.

    Args:
        pattern: Redis key pattern (e.g., "concept_extraction:*")
                If None, clears all SyncBoard cache keys

    Returns:
        Number of keys deleted
    """
    redis = get_redis_client()
    if redis is None:
        return 0

    try:
        pattern = pattern or "concept_extraction:*"
        keys = redis.keys(pattern)

        if keys:
            deleted = redis.delete(*keys)
            logger.info(f"Invalidated {deleted} cache entries matching '{pattern}'")
            return deleted

        return 0
    except Exception as e:
        logger.warning(f"Cache invalidation error: {e}")
        return 0


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics.

    Returns:
        Dict with cache stats (hits, misses, size, etc.)
    """
    redis = get_redis_client()
    if redis is None:
        return {
            "status": "unavailable",
            "message": "Redis not connected"
        }

    try:
        info = redis.info("stats")
        memory = redis.info("memory")

        # Count keys by prefix
        concept_keys = len(redis.keys("concept_extraction:*"))
        similarity_keys = len(redis.keys("similarity:*"))

        return {
            "status": "connected",
            "total_keys": redis.dbsize(),
            "concept_extraction_keys": concept_keys,
            "similarity_keys": similarity_keys,
            "memory_used_mb": round(memory.get("used_memory", 0) / (1024 * 1024), 2),
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0),
            "hit_rate": round(
                info.get("keyspace_hits", 0) /
                max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1) * 100,
                2
            )
        }
    except Exception as e:
        logger.warning(f"Cache stats error: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


# =============================================================================
# Concept Extraction Cache
# =============================================================================

def get_cached_concepts(content: str, source_type: str, sample_size: int) -> Optional[Dict]:
    """
    Get cached concept extraction result.

    Args:
        content: Document content
        source_type: Type of source (url, file, text, etc.)
        sample_size: Sampling size used for extraction

    Returns:
        Cached extraction result or None
    """
    key = generate_cache_key(
        "concept_extraction",
        content,
        source_type=source_type,
        sample_size=sample_size
    )
    return get_cached_result(key)


def cache_concepts(
    content: str,
    source_type: str,
    sample_size: int,
    result: Dict,
    ttl_days: int = 7
) -> bool:
    """
    Cache concept extraction result.

    Args:
        content: Document content
        source_type: Type of source
        sample_size: Sampling size used
        result: Extraction result to cache
        ttl_days: Time-to-live in days (default: 7 days)

    Returns:
        True if cached successfully
    """
    key = generate_cache_key(
        "concept_extraction",
        content,
        source_type=source_type,
        sample_size=sample_size
    )

    # Store for 7 days by default (604800 seconds)
    ttl_seconds = ttl_days * 24 * 60 * 60

    return set_cached_result(key, result, ttl_seconds)


# =============================================================================
# Content Similarity Cache
# =============================================================================

def get_cached_similarity(content1: str, content2: str) -> Optional[float]:
    """
    Get cached similarity score between two pieces of content.

    Args:
        content1: First content
        content2: Second content

    Returns:
        Cached similarity score (0-1) or None
    """
    # Sort content to ensure consistent key regardless of order
    sorted_content = tuple(sorted([content1, content2]))
    combined = f"{sorted_content[0]}|||{sorted_content[1]}"

    key = generate_cache_key("similarity", combined)
    result = get_cached_result(key)

    if result:
        return result.get("similarity")
    return None


def cache_similarity(content1: str, content2: str, similarity: float) -> bool:
    """
    Cache similarity score between two pieces of content.

    Args:
        content1: First content
        content2: Second content
        similarity: Similarity score (0-1)

    Returns:
        True if cached successfully
    """
    sorted_content = tuple(sorted([content1, content2]))
    combined = f"{sorted_content[0]}|||{sorted_content[1]}"

    key = generate_cache_key("similarity", combined)
    result = {"similarity": similarity}

    # Store for 30 days (longer TTL since content similarity doesn't change)
    return set_cached_result(key, result, ttl_seconds=30 * 24 * 60 * 60)
