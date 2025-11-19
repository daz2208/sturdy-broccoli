"""
Clusters Router for SyncBoard 3.0 Knowledge Bank.

Endpoints:
- GET /clusters - Get user's clusters
- PUT /clusters/{cluster_id} - Update cluster information
- GET /export/cluster/{cluster_id} - Export cluster as JSON or Markdown
- GET /export/all - Export entire knowledge bank
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse

from ..models import User
from ..dependencies import (
    get_current_user,
    get_documents,
    get_metadata,
    get_clusters,
    get_users,
    get_storage_lock,
    get_kb_documents,
    get_kb_metadata,
    get_kb_clusters,
    get_user_default_kb_id,
)
from ..database import get_db
from sqlalchemy.orm import Session
from ..sanitization import sanitize_cluster_name
from ..constants import SKILL_LEVELS
from ..db_storage_adapter import save_storage_to_db

# Initialize logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="",
    tags=["clusters"],
    responses={401: {"description": "Unauthorized"}},
)

# =============================================================================
# Get Clusters Endpoint
# =============================================================================

@router.get("/clusters")
async def get_user_clusters(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's clusters.

    Returns all clusters in the user's default knowledge base.

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        List of user's clusters with metadata
    """
    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Get KB-scoped storage
    kb_metadata = get_kb_metadata(kb_id)
    kb_clusters = get_kb_clusters(kb_id)

    user_clusters = []

    for cluster_id, cluster in kb_clusters.items():
        # Check if any docs in cluster belong to user
        has_user_docs = any(
            kb_metadata.get(doc_id) and kb_metadata[doc_id].owner == current_user.username
            for doc_id in cluster.doc_ids
        )

        if has_user_docs:
            user_clusters.append(cluster.dict())

    return {
        "clusters": user_clusters,
        "total": len(user_clusters),
        "knowledge_base_id": kb_id
    }

# =============================================================================
# Update Cluster Endpoint
# =============================================================================

@router.put("/clusters/{cluster_id}")
async def update_cluster(
    cluster_id: int,
    updates: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update cluster information (rename, etc).

    Args:
        cluster_id: ID of cluster to update
        updates: Dictionary of fields to update
        user: Authenticated user
        db: Database session

    Returns:
        Updated cluster information

    Raises:
        HTTPException 404: If cluster not found
    """
    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(user.username, db)

    # Get KB-scoped storage
    kb_clusters = get_kb_clusters(kb_id)

    # Get global storage for save
    documents = get_documents()
    metadata = get_metadata()
    clusters = get_clusters()
    users = get_users()
    storage_lock = get_storage_lock()

    if cluster_id not in kb_clusters:
        raise HTTPException(404, f"Cluster {cluster_id} not found")

    # CRITICAL: Use lock for thread-safe modifications to shared state
    async with storage_lock:
        cluster = kb_clusters[cluster_id]

        # Update allowed fields
        if 'name' in updates:
            # Sanitize cluster name
            cluster.name = sanitize_cluster_name(updates['name'])

        if 'skill_level' in updates:
            if updates['skill_level'] in SKILL_LEVELS:
                cluster.skill_level = updates['skill_level']

        # Save to database
        save_storage_to_db(documents, metadata, clusters, users)

    logger.info(f"Updated cluster {cluster_id} in KB {kb_id}: {cluster.name}")
    return {"message": "Cluster updated", "cluster": cluster.dict()}

# =============================================================================
# Export Cluster Endpoint
# =============================================================================

@router.get("/export/cluster/{cluster_id}")
async def export_cluster(
    cluster_id: int,
    format: str = "json",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export a cluster as JSON or Markdown.

    Args:
        cluster_id: ID of cluster to export
        format: Export format ("json" or "markdown")
        user: Authenticated user
        db: Database session

    Returns:
        Exported cluster data

    Raises:
        HTTPException 404: If cluster not found
    """
    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(user.username, db)

    # Get KB-scoped storage
    kb_documents = get_kb_documents(kb_id)
    kb_metadata = get_kb_metadata(kb_id)
    kb_clusters = get_kb_clusters(kb_id)

    if cluster_id not in kb_clusters:
        raise HTTPException(404, f"Cluster {cluster_id} not found")

    cluster = kb_clusters[cluster_id]

    # Gather all documents in cluster
    cluster_docs = []
    for doc_id in cluster.doc_ids:
        if doc_id in kb_documents:
            meta = kb_metadata.get(doc_id)
            cluster_docs.append({
                "doc_id": doc_id,
                "content": kb_documents[doc_id],
                "metadata": meta.dict() if meta else None
            })
    
    if format == "markdown":
        # Build markdown export
        md_content = f"# {cluster.name}\n\n"
        md_content += f"**Skill Level:** {cluster.skill_level}\n"
        md_content += f"**Primary Concepts:** {', '.join(cluster.primary_concepts)}\n"
        md_content += f"**Documents:** {len(cluster_docs)}\n\n"
        md_content += "---\n\n"
        
        for doc in cluster_docs:
            meta = doc['metadata']
            md_content += f"## Document {doc['doc_id']}\n\n"
            if meta:
                md_content += f"**Source:** {meta.get('source_type', 'unknown')}\n"
                md_content += f"**Topic:** {meta.get('primary_topic', 'N/A')}\n"
                md_content += f"**Concepts:** {', '.join([c['name'] for c in meta.get('concepts', [])])}\n\n"
            md_content += f"{doc['content']}\n\n"
            md_content += "---\n\n"
        
        return JSONResponse({
            "cluster_id": cluster_id,
            "cluster_name": cluster.name,
            "format": "markdown",
            "content": md_content
        })
    
    else:  # JSON format
        return {
            "cluster_id": cluster_id,
            "cluster": cluster.dict(),
            "documents": cluster_docs,
            "export_date": datetime.utcnow().isoformat()
        }

# =============================================================================
# Export All Endpoint
# =============================================================================

@router.get("/export/all")
async def export_all(
    format: str = "json",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export entire knowledge bank.

    Args:
        format: Export format ("json" or "markdown")
        user: Authenticated user
        db: Database session

    Returns:
        Exported knowledge bank data
    """
    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(user.username, db)

    # Get KB-scoped storage
    kb_documents = get_kb_documents(kb_id)
    kb_metadata = get_kb_metadata(kb_id)
    kb_clusters = get_kb_clusters(kb_id)

    all_docs = []
    for doc_id in sorted(kb_documents.keys()):
        meta = kb_metadata.get(doc_id)
        cluster_id = meta.cluster_id if meta else None
        cluster_name = kb_clusters[cluster_id].name if cluster_id in kb_clusters else None

        all_docs.append({
            "doc_id": doc_id,
            "content": kb_documents[doc_id],
            "metadata": meta.dict() if meta else None,
            "cluster_name": cluster_name
        })

    if format == "markdown":
        md_content = f"# Knowledge Bank Export\n\n"
        md_content += f"**Export Date:** {datetime.utcnow().isoformat()}\n"
        md_content += f"**Total Documents:** {len(all_docs)}\n"
        md_content += f"**Total Clusters:** {len(kb_clusters)}\n\n"
        md_content += "---\n\n"

        # Group by cluster
        for cluster in kb_clusters.values():
            md_content += f"# Cluster: {cluster.name}\n\n"
            cluster_docs = [d for d in all_docs if d['metadata'] and d['metadata']['cluster_id'] == cluster.id]

            for doc in cluster_docs:
                meta = doc['metadata']
                md_content += f"## Document {doc['doc_id']}\n\n"
                if meta:
                    md_content += f"**Topic:** {meta.get('primary_topic', 'N/A')}\n"
                md_content += f"{doc['content']}\n\n"
                md_content += "---\n\n"

        return JSONResponse({
            "format": "markdown",
            "content": md_content,
            "knowledge_base_id": kb_id
        })

    else:  # JSON
        return {
            "documents": all_docs,
            "clusters": [c.dict() for c in kb_clusters.values()],
            "export_date": datetime.utcnow().isoformat(),
            "total_documents": len(all_docs),
            "total_clusters": len(kb_clusters),
            "knowledge_base_id": kb_id
        }
