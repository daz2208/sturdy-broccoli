"""
Tests for Redis caching functionality.

Tests the caching decorators and invalidation logic for:
- Analytics caching
- Build suggestions caching
- Search results caching
- Cache invalidation on document changes
"""

import pytest
from backend.redis_client import (
    redis_client,
    get_cache,
    set_cache,
    delete_cache,
    get_cached_analytics,
    cache_analytics,
    invalidate_analytics,
    get_cached_build_suggestions,
    cache_build_suggestions,
    invalidate_build_suggestions,
    get_cached_search,
    cache_search,
    invalidate_search,
)


@pytest.fixture
def test_user_id():
    """Test user ID for cache operations."""
    return "test_user"


@pytest.fixture(autouse=True)
def cleanup_cache(test_user_id):
    """Clean up cache after each test."""
    yield
    # Cleanup after test
    if redis_client:
        invalidate_analytics(test_user_id)
        invalidate_build_suggestions(test_user_id)
        invalidate_search(test_user_id)


class TestBasicCaching:
    """Test basic Redis cache operations."""

    def test_set_and_get_cache(self):
        """Test basic set and get operations."""
        if not redis_client:
            pytest.skip("Redis not available")

        key = "test:key"
        value = {"data": "test_value", "number": 42}

        # Set cache
        success = set_cache(key, value, ttl=60)
        assert success is True

        # Get cache
        cached = get_cache(key)
        assert cached == value

        # Cleanup
        delete_cache(key)

    def test_delete_cache(self):
        """Test cache deletion."""
        if not redis_client:
            pytest.skip("Redis not available")

        key = "test:delete"
        value = {"data": "to_delete"}

        set_cache(key, value, ttl=60)
        cached = get_cache(key)
        assert cached == value

        # Delete
        delete_cache(key)
        cached_after = get_cache(key)
        assert cached_after is None


class TestAnalyticsCaching:
    """Test analytics caching functionality."""

    def test_cache_analytics(self, test_user_id):
        """Test caching analytics results."""
        if not redis_client:
            pytest.skip("Redis not available")

        analytics_data = {
            "total_docs": 10,
            "total_clusters": 3,
            "top_concepts": ["Python", "Docker", "FastAPI"]
        }

        # Cache analytics
        success = cache_analytics(test_user_id, analytics_data, time_period="30", ttl=600)
        assert success is True

        # Retrieve from cache
        cached = get_cached_analytics(test_user_id, time_period="30")
        assert cached is not None
        assert cached["total_docs"] == 10
        assert cached["total_clusters"] == 3

    def test_invalidate_analytics(self, test_user_id):
        """Test analytics cache invalidation."""
        if not redis_client:
            pytest.skip("Redis not available")

        analytics_data = {"total_docs": 10}

        # Cache analytics
        cache_analytics(test_user_id, analytics_data, time_period="30", ttl=600)
        cached = get_cached_analytics(test_user_id, time_period="30")
        assert cached is not None

        # Invalidate
        deleted_count = invalidate_analytics(test_user_id)
        assert deleted_count >= 1

        # Should be None after invalidation
        cached_after = get_cached_analytics(test_user_id, time_period="30")
        assert cached_after is None


class TestBuildSuggestionsCaching:
    """Test build suggestions caching functionality."""

    def test_cache_build_suggestions(self, test_user_id):
        """Test caching build suggestions."""
        if not redis_client:
            pytest.skip("Redis not available")

        suggestions = {
            "suggestions": [
                {"title": "Docker Management Dashboard", "difficulty": "intermediate"}
            ],
            "knowledge_summary": {"total_docs": 10}
        }

        # Cache suggestions
        success = cache_build_suggestions(test_user_id, suggestions, ttl=1800)
        assert success is True

        # Retrieve from cache
        cached = get_cached_build_suggestions(test_user_id)
        assert cached is not None
        assert len(cached["suggestions"]) == 1
        assert cached["suggestions"][0]["title"] == "Docker Management Dashboard"

    def test_invalidate_build_suggestions(self, test_user_id):
        """Test build suggestions cache invalidation."""
        if not redis_client:
            pytest.skip("Redis not available")

        suggestions = {"suggestions": [{"title": "Test Project"}]}

        # Cache suggestions
        cache_build_suggestions(test_user_id, suggestions, ttl=1800)
        cached = get_cached_build_suggestions(test_user_id)
        assert cached is not None

        # Invalidate
        success = invalidate_build_suggestions(test_user_id)
        assert success is True

        # Should be None after invalidation
        cached_after = get_cached_build_suggestions(test_user_id)
        assert cached_after is None


class TestSearchCaching:
    """Test search results caching functionality."""

    def test_cache_search(self, test_user_id):
        """Test caching search results."""
        if not redis_client:
            pytest.skip("Redis not available")

        query = "Python tutorial"
        filters = {
            "top_k": 10,
            "cluster_id": None,
            "source_type": "text"
        }
        results = {
            "results": [
                {"doc_id": 1, "score": 0.95, "content": "Python tutorial content"}
            ],
            "total_results": 1
        }

        # Cache search
        success = cache_search(test_user_id, query, filters, results, ttl=300)
        assert success is True

        # Retrieve from cache
        cached = get_cached_search(test_user_id, query, filters)
        assert cached is not None
        assert cached["total_results"] == 1
        assert len(cached["results"]) == 1

    def test_search_cache_key_uniqueness(self, test_user_id):
        """Test that different queries/filters create different cache keys."""
        if not redis_client:
            pytest.skip("Redis not available")

        query1 = "Python tutorial"
        query2 = "Docker tutorial"
        filters = {"top_k": 10}
        results1 = {"results": [{"doc_id": 1}], "total_results": 1}
        results2 = {"results": [{"doc_id": 2}], "total_results": 1}

        # Cache both
        cache_search(test_user_id, query1, filters, results1, ttl=300)
        cache_search(test_user_id, query2, filters, results2, ttl=300)

        # Retrieve - should get different results
        cached1 = get_cached_search(test_user_id, query1, filters)
        cached2 = get_cached_search(test_user_id, query2, filters)

        assert cached1["results"][0]["doc_id"] == 1
        assert cached2["results"][0]["doc_id"] == 2

    def test_invalidate_search(self, test_user_id):
        """Test search cache invalidation."""
        if not redis_client:
            pytest.skip("Redis not available")

        query = "test query"
        filters = {"top_k": 10}
        results = {"results": [], "total_results": 0}

        # Cache search
        cache_search(test_user_id, query, filters, results, ttl=300)
        cached = get_cached_search(test_user_id, query, filters)
        assert cached is not None

        # Invalidate all search caches for user
        deleted_count = invalidate_search(test_user_id)
        assert deleted_count >= 1

        # Should be None after invalidation
        cached_after = get_cached_search(test_user_id, query, filters)
        assert cached_after is None


class TestCacheInvalidationOnChanges:
    """Test that caches are properly invalidated when documents change."""

    def test_all_caches_invalidated_together(self, test_user_id):
        """Test that all caches can be invalidated together (simulating document change)."""
        if not redis_client:
            pytest.skip("Redis not available")

        # Set up all caches
        cache_analytics(test_user_id, {"total_docs": 10}, time_period="30", ttl=600)
        cache_build_suggestions(test_user_id, {"suggestions": []}, ttl=1800)
        cache_search(test_user_id, "test", {}, {"results": []}, ttl=300)

        # Verify all are cached
        assert get_cached_analytics(test_user_id, time_period="30") is not None
        assert get_cached_build_suggestions(test_user_id) is not None
        assert get_cached_search(test_user_id, "test", {}) is not None

        # Invalidate all (simulating document add/delete)
        invalidate_analytics(test_user_id)
        invalidate_build_suggestions(test_user_id)
        invalidate_search(test_user_id)

        # Verify all are invalidated
        assert get_cached_analytics(test_user_id, time_period="30") is None
        assert get_cached_build_suggestions(test_user_id) is None
        assert get_cached_search(test_user_id, "test", {}) is None


class TestCacheTTL:
    """Test cache time-to-live behavior."""

    def test_cache_expires_after_ttl(self, test_user_id):
        """Test that cache entries expire after TTL (requires waiting)."""
        if not redis_client:
            pytest.skip("Redis not available")

        import time

        # Set cache with very short TTL (2 seconds)
        key = "test:ttl"
        value = {"data": "expires_soon"}
        set_cache(key, value, ttl=2)

        # Should be available immediately
        cached = get_cache(key)
        assert cached == value

        # Wait for expiration
        time.sleep(3)

        # Should be None after TTL
        cached_after = get_cache(key)
        assert cached_after is None


# =============================================================================
# Integration Tests (Optional - run if Redis is available)
# =============================================================================

def test_redis_connection():
    """Test that Redis connection is available."""
    if redis_client:
        try:
            redis_client.ping()
            assert True, "Redis is connected"
        except Exception as e:
            pytest.fail(f"Redis connection failed: {e}")
    else:
        pytest.skip("Redis not available - caching disabled")
