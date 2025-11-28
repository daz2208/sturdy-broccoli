"""
Search Router for SyncBoard 3.0 Knowledge Bank.

Endpoints:
- GET /search_full - Semantic search with filters
- GET /search/summaries - Search through document summaries
- GET /search/summaries/stats - Get summary statistics
"""

import logging
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..models import User


def validate_iso_date(date_str: Optional[str], param_name: str) -> Optional[datetime]:
    """
    Validate and parse ISO format date string.

    Args:
        date_str: Date string in ISO format (e.g., "2024-01-15" or "2024-01-15T10:30:00Z")
        param_name: Parameter name for error messages

    Returns:
        Parsed datetime object or None

    Raises:
        HTTPException 400 if date format is invalid
    """
    if date_str is None:
        return None

    try:
        # Handle various ISO formats
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except (ValueError, AttributeError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format for '{param_name}': '{date_str}'. "
                   f"Expected ISO format (e.g., '2024-01-15' or '2024-01-15T10:30:00Z')"
        )
from ..dependencies import (
    get_current_user,
    get_repository,
    get_user_default_kb_id,
)
from ..repository_interface import KnowledgeBankRepository
from ..database import get_db
from sqlalchemy.orm import Session
from fastapi import Query
from ..sanitization import validate_positive_integer
from ..constants import DEFAULT_TOP_K, MAX_TOP_K, SNIPPET_LENGTH
from ..redis_client import get_cached_search, cache_search

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(
    prefix="",
    tags=["search"],
    responses={401: {"description": "Unauthorized"}},
)

# =============================================================================
# Search Endpoint
# =============================================================================

@router.get("/search_full")
@limiter.limit("30/minute")
async def search_full_content(
    q: str,
    top_k: int = DEFAULT_TOP_K,
    cluster_id: Optional[int] = None,
    full_content: bool = False,
    source_type: Optional[str] = None,
    skill_level: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    request: Request = None,
    repo: KnowledgeBankRepository = Depends(get_repository),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search documents with optional filters.

    Rate limited to 30 searches per minute.

    Filters:
    - source_type: Filter by source (text, url, pdf, etc.)
    - skill_level: Filter by skill level (beginner, intermediate, advanced)
    - date_from/date_to: Filter by ingestion date (ISO format)
    - cluster_id: Filter by cluster
    - full_content: Return full content or 500-char snippet

    By default returns 500-char snippets for performance.

    Args:
        q: Search query
        top_k: Number of results to return (max 50)
        cluster_id: Optional cluster filter
        full_content: Return full content or snippet
        source_type: Optional source type filter
        skill_level: Optional skill level filter
        date_from: Optional start date filter (ISO format)
        date_to: Optional end date filter (ISO format)
        request: FastAPI request (for rate limiting)
        current_user: Authenticated user
        db: Database session

    Returns:
        Search results with metadata and cluster information

    Raises:
        HTTPException 400: If date_from or date_to have invalid format
    """
    # Validate date parameters early (fail fast with clear error message)
    parsed_date_from = validate_iso_date(date_from, "date_from")
    parsed_date_to = validate_iso_date(date_to, "date_to")

    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Get KB-scoped storage from repository
    kb_documents = await repo.get_documents_by_kb(kb_id)
    kb_metadata = await repo.get_metadata_by_kb(kb_id)
    kb_clusters = await repo.get_clusters_by_kb(kb_id)
    vector_store = repo.vector_store

    # Validate top_k parameter
    top_k = validate_positive_integer(top_k, "top_k", max_value=MAX_TOP_K)
    if top_k < 1:
        top_k = DEFAULT_TOP_K

    # Get user's documents (all docs in user's KB)
    user_doc_ids = [
        doc_id for doc_id, meta in kb_metadata.items()
        if meta.owner == current_user.username
    ]
    
    if not user_doc_ids:
        return {"results": [], "grouped_by_cluster": {}}
    
    # Apply filters
    filtered_ids = user_doc_ids.copy()

    # Filter by cluster
    if cluster_id is not None:
        filtered_ids = [
            doc_id for doc_id in filtered_ids
            if kb_metadata[doc_id].cluster_id == cluster_id
        ]

    # Filter by source type
    if source_type:
        filtered_ids = [
            doc_id for doc_id in filtered_ids
            if kb_metadata[doc_id].source_type == source_type
        ]

    # Filter by skill level
    if skill_level:
        filtered_ids = [
            doc_id for doc_id in filtered_ids
            if kb_metadata[doc_id].skill_level == skill_level
        ]

    # Filter by date range (using pre-validated dates)
    if parsed_date_from or parsed_date_to:
        date_filtered = []
        for doc_id in filtered_ids:
            meta = kb_metadata[doc_id]
            if not meta.ingested_at:
                continue

            try:
                doc_date = datetime.fromisoformat(meta.ingested_at.replace('Z', '+00:00'))

                if parsed_date_from and doc_date < parsed_date_from:
                    continue

                if parsed_date_to and doc_date > parsed_date_to:
                    continue

                date_filtered.append(doc_id)
            except (ValueError, TypeError):
                # Skip documents with invalid or missing dates in metadata
                continue

        filtered_ids = date_filtered
    
    if not filtered_ids:
        return {"results": [], "grouped_by_cluster": {}, "filters_applied": {
            "source_type": source_type,
            "skill_level": skill_level,
            "date_from": date_from,
            "date_to": date_to,
            "cluster_id": cluster_id
        }}

    # Check cache first (5-10x faster for cached results)
    filters_dict = {
        "top_k": top_k,
        "cluster_id": cluster_id,
        "full_content": full_content,
        "source_type": source_type,
        "skill_level": skill_level,
        "date_from": date_from,
        "date_to": date_to
    }
    cached_results = get_cached_search(
        user_id=current_user.username,
        query=q,
        filters=filters_dict
    )

    if cached_results:
        logger.info(f"Cache HIT: Search for '{q}' by {current_user.username}")
        return cached_results

    # Cache miss - perform search (expensive TF-IDF computation)
    logger.info(f"Cache MISS: Searching for '{q}' by {current_user.username}")
    search_results = vector_store.search(
        query=q,
        top_k=top_k,
        allowed_doc_ids=filtered_ids
    )

    # Build response with metadata
    results = []
    cluster_groups = {}

    for doc_id, score, snippet in search_results:
        meta = kb_metadata[doc_id]
        cluster = kb_clusters.get(meta.cluster_id) if meta.cluster_id else None

        # Return full content or snippet based on parameter
        # Always return full content for now (snippets can be confusing)
        content = kb_documents[doc_id]

        results.append({
            "doc_id": doc_id,
            "score": score,
            "content": content,
            "metadata": meta.dict(),
            "cluster": cluster.dict() if cluster else None
        })

        # Group by cluster
        if meta.cluster_id:
            if meta.cluster_id not in cluster_groups:
                cluster_groups[meta.cluster_id] = []
            cluster_groups[meta.cluster_id].append(doc_id)

    response = {
        "results": results,
        "grouped_by_cluster": cluster_groups,
        "filters_applied": {
            "source_type": source_type,
            "skill_level": skill_level,
            "date_from": date_from,
            "date_to": date_to,
            "cluster_id": cluster_id
        },
        "total_results": len(results),
        "knowledge_base_id": kb_id
    }

    # Cache the result for 5 minutes (300 seconds)
    cache_search(
        user_id=current_user.username,
        query=q,
        filters=filters_dict,
        results=response,
        ttl=300
    )

    return response


# =============================================================================
# Summary Search Endpoints
# =============================================================================

@router.get("/search/summaries")
@limiter.limit("30/minute")
async def search_summaries(
    request: Request,
    q: Optional[str] = None,
    concepts: Optional[str] = None,
    technologies: Optional[str] = None,
    level: Optional[int] = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search through document summaries for faster, context-aware results.

    Searches summary content, concepts, and technologies.

    Args:
        q: Text query to search in summaries
        concepts: Comma-separated list of concepts to filter by
        technologies: Comma-separated list of technologies to filter by
        level: Summary level filter (1=chunk, 2=section, 3=document)
        limit: Maximum results (default 20, max 50)
        current_user: Authenticated user
        db: Database session

    Returns:
        Search results with summaries and relevance scores
    """
    from ..summary_search_service import search_summaries as do_search

    # Validate level
    if level and level not in [1, 2, 3]:
        raise HTTPException(400, "Invalid level. Use: 1 (chunk), 2 (section), 3 (document)")

    # Validate limit
    limit = max(1, min(50, limit))

    # Parse comma-separated filters
    concept_list = [c.strip() for c in concepts.split(",")] if concepts else None
    tech_list = [t.strip() for t in technologies.split(",")] if technologies else None

    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Search summaries
    results = await do_search(
        db=db,
        knowledge_base_id=kb_id,
        query=q,
        concepts=concept_list,
        technologies=tech_list,
        level=level,
        limit=limit
    )

    return {
        "results": results,
        "total_results": len(results),
        "filters_applied": {
            "query": q,
            "concepts": concept_list,
            "technologies": tech_list,
            "level": level
        },
        "knowledge_base_id": kb_id
    }


@router.get("/search/summaries/stats")
@limiter.limit("30/minute")
async def get_summary_stats(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get statistics about summaries in the knowledge base.

    Returns counts of summaries by level, unique concepts, and technologies.
    """
    from ..summary_search_service import get_summary_stats as fetch_stats

    kb_id = get_user_default_kb_id(current_user.username, db)

    stats = await fetch_stats(db, kb_id)

    return {
        "knowledge_base_id": kb_id,
        "stats": stats
    }
