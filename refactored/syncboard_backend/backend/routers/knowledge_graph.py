"""
Knowledge Graph Router for SyncBoard 3.0 Knowledge Bank.

Endpoints:
- GET /knowledge-graph/stats - Get graph statistics
- POST /knowledge-graph/build - Build/rebuild knowledge graph
- GET /knowledge-graph/related/{doc_id} - Get related documents
- GET /knowledge-graph/concepts - Get concept cloud
- GET /knowledge-graph/technologies - Get technology cloud
- GET /knowledge-graph/path - Find learning path between concepts
- GET /knowledge-graph/by-concept/{concept} - Find documents by concept
- GET /knowledge-graph/by-tech/{technology} - Find documents by technology
"""

import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from ..models import User
from ..dependencies import get_current_user, get_user_default_kb_id
from ..database import get_db

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(
    prefix="/knowledge-graph",
    tags=["knowledge-graph"],
    responses={401: {"description": "Unauthorized"}},
)


# =============================================================================
# Graph Statistics Endpoint
# =============================================================================

@router.get("/stats")
@limiter.limit("30/minute")
async def get_graph_stats(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get statistics about the knowledge graph.

    Returns counts of documents, relationships, concepts, and technologies.
    """
    from ..knowledge_graph_service import get_graph_stats as fetch_stats

    kb_id = get_user_default_kb_id(current_user.username, db)

    try:
        stats = await fetch_stats(db, kb_id)
        return {
            "knowledge_base_id": kb_id,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Failed to get graph stats: {e}")
        raise HTTPException(500, f"Failed to get graph stats: {str(e)}")


# =============================================================================
# Build Graph Endpoint
# =============================================================================

@router.post("/build")
@limiter.limit("3/minute")
async def build_knowledge_graph(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Build or rebuild the knowledge graph.

    This is an expensive operation - rate limited to 3/minute.
    Requires documents to have summaries generated first.
    """
    from ..knowledge_graph_service import get_knowledge_graph

    kb_id = get_user_default_kb_id(current_user.username, db)

    try:
        graph = await get_knowledge_graph(db, kb_id, rebuild=True)

        return {
            "status": "success",
            "knowledge_base_id": kb_id,
            "stats": {
                "total_documents": len(graph._nodes),
                "total_relationships": len(graph._relationships),
                "unique_concepts": len(graph._concept_index),
                "unique_technologies": len(graph._tech_index)
            }
        }
    except Exception as e:
        logger.error(f"Failed to build knowledge graph: {e}")
        raise HTTPException(500, f"Failed to build graph: {str(e)}")


# =============================================================================
# Related Documents Endpoint
# =============================================================================

@router.get("/related/{doc_id}")
@limiter.limit("30/minute")
async def get_related_documents(
    doc_id: int,
    request: Request,
    relationship_type: str = None,
    min_strength: float = 0.1,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get documents related to a specific document.

    Args:
        doc_id: Document ID to find relationships for
        relationship_type: Filter by type (shared_concept, shared_tech, same_cluster)
        min_strength: Minimum relationship strength (0.0-1.0)
        limit: Maximum results

    Returns:
        List of related documents with relationship info
    """
    from ..knowledge_graph_service import get_knowledge_graph

    # Validate relationship_type
    valid_types = ["shared_concept", "shared_tech", "same_cluster"]
    if relationship_type and relationship_type not in valid_types:
        raise HTTPException(400, f"Invalid relationship_type. Use: {', '.join(valid_types)}")

    # Validate parameters
    min_strength = max(0.0, min(1.0, min_strength))
    limit = max(1, min(50, limit))

    kb_id = get_user_default_kb_id(current_user.username, db)

    try:
        graph = await get_knowledge_graph(db, kb_id)
        related = graph.get_related_documents(
            doc_id=doc_id,
            relationship_type=relationship_type,
            min_strength=min_strength,
            limit=limit
        )

        return {
            "doc_id": doc_id,
            "count": len(related),
            "related_documents": related
        }
    except Exception as e:
        logger.error(f"Failed to get related documents: {e}")
        raise HTTPException(500, f"Failed to get related documents: {str(e)}")


# =============================================================================
# Concept Cloud Endpoint
# =============================================================================

@router.get("/concepts")
@limiter.limit("30/minute")
async def get_concept_cloud(
    request: Request,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get top concepts across all documents.

    Returns concepts sorted by document count (most common first).
    Useful for building concept clouds or tag visualizations.
    """
    from ..knowledge_graph_service import get_knowledge_graph

    limit = max(1, min(100, limit))
    kb_id = get_user_default_kb_id(current_user.username, db)

    try:
        graph = await get_knowledge_graph(db, kb_id)
        concepts = graph.get_concept_cloud(limit=limit)

        return {
            "count": len(concepts),
            "concepts": concepts
        }
    except Exception as e:
        logger.error(f"Failed to get concept cloud: {e}")
        raise HTTPException(500, f"Failed to get concept cloud: {str(e)}")


# =============================================================================
# Technology Cloud Endpoint
# =============================================================================

@router.get("/technologies")
@limiter.limit("30/minute")
async def get_technology_cloud(
    request: Request,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get top technologies across all documents.

    Returns technologies sorted by document count (most common first).
    Useful for understanding the tech stack covered in the knowledge bank.
    """
    from ..knowledge_graph_service import get_knowledge_graph

    limit = max(1, min(100, limit))
    kb_id = get_user_default_kb_id(current_user.username, db)

    try:
        graph = await get_knowledge_graph(db, kb_id)
        technologies = graph.get_tech_cloud(limit=limit)

        return {
            "count": len(technologies),
            "technologies": technologies
        }
    except Exception as e:
        logger.error(f"Failed to get technology cloud: {e}")
        raise HTTPException(500, f"Failed to get technology cloud: {str(e)}")


# =============================================================================
# Learning Path Endpoint
# =============================================================================

@router.get("/path")
@limiter.limit("10/minute")
async def find_learning_path(
    request: Request,
    start_concept: str,
    end_concept: str,
    max_steps: int = 5,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Find a learning path from one concept to another.

    Uses BFS to find the shortest path through related documents.
    Useful for planning learning journeys through the knowledge bank.

    Args:
        start_concept: Starting concept (e.g., "python basics")
        end_concept: Target concept (e.g., "machine learning")
        max_steps: Maximum number of steps in the path

    Returns:
        List of documents forming a learning path
    """
    from ..knowledge_graph_service import get_knowledge_graph

    if not start_concept or not end_concept:
        raise HTTPException(400, "Both start_concept and end_concept are required")

    max_steps = max(1, min(10, max_steps))
    kb_id = get_user_default_kb_id(current_user.username, db)

    try:
        graph = await get_knowledge_graph(db, kb_id)
        path = graph.find_learning_path(
            start_concept=start_concept,
            end_concept=end_concept,
            max_steps=max_steps
        )

        if not path:
            return {
                "found": False,
                "message": f"No path found from '{start_concept}' to '{end_concept}' within {max_steps} steps",
                "path": []
            }

        return {
            "found": True,
            "start_concept": start_concept,
            "end_concept": end_concept,
            "steps": len(path),
            "path": path
        }
    except Exception as e:
        logger.error(f"Failed to find learning path: {e}")
        raise HTTPException(500, f"Failed to find path: {str(e)}")


# =============================================================================
# Find by Concept Endpoint
# =============================================================================

@router.get("/by-concept/{concept}")
@limiter.limit("30/minute")
async def find_documents_by_concept(
    concept: str,
    request: Request,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Find documents that cover a specific concept.

    Args:
        concept: The concept to search for
        limit: Maximum results

    Returns:
        List of documents containing the concept
    """
    from ..knowledge_graph_service import get_knowledge_graph

    limit = max(1, min(50, limit))
    kb_id = get_user_default_kb_id(current_user.username, db)

    try:
        graph = await get_knowledge_graph(db, kb_id)
        documents = graph.find_documents_by_concept(concept=concept, limit=limit)

        return {
            "concept": concept,
            "count": len(documents),
            "documents": documents
        }
    except Exception as e:
        logger.error(f"Failed to find documents by concept: {e}")
        raise HTTPException(500, f"Failed to find documents: {str(e)}")


# =============================================================================
# Find by Technology Endpoint
# =============================================================================

@router.get("/by-tech/{technology}")
@limiter.limit("30/minute")
async def find_documents_by_technology(
    technology: str,
    request: Request,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Find documents that use a specific technology.

    Args:
        technology: The technology to search for (e.g., "python", "react")
        limit: Maximum results

    Returns:
        List of documents using the technology
    """
    from ..knowledge_graph_service import get_knowledge_graph

    limit = max(1, min(50, limit))
    kb_id = get_user_default_kb_id(current_user.username, db)

    try:
        graph = await get_knowledge_graph(db, kb_id)
        documents = graph.find_documents_by_tech(technology=technology, limit=limit)

        return {
            "technology": technology,
            "count": len(documents),
            "documents": documents
        }
    except Exception as e:
        logger.error(f"Failed to find documents by technology: {e}")
        raise HTTPException(500, f"Failed to find documents: {str(e)}")
