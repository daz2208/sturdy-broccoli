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

from ..models import User, ClusterUpdate, ExportFormat
from ..dependencies import (
    get_current_user,
    get_repository,
    get_user_default_kb_id,
)
from ..repository_interface import KnowledgeBankRepository
from ..database import get_db
from sqlalchemy.orm import Session
from ..sanitization import sanitize_cluster_name
from ..constants import SKILL_LEVELS
from ..websocket_manager import broadcast_cluster_updated, broadcast_cluster_deleted

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
    repo: KnowledgeBankRepository = Depends(get_repository),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's clusters.

    Returns all clusters in the user's default knowledge base.

    Args:
        repo: Repository instance
        current_user: Authenticated user
        db: Database session

    Returns:
        List of user's clusters with metadata
    """
    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Get KB-scoped storage from repository
    kb_metadata = await repo.get_metadata_by_kb(kb_id)
    kb_clusters = await repo.get_clusters_by_kb(kb_id)

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
    updates: ClusterUpdate,
    repo: KnowledgeBankRepository = Depends(get_repository),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update cluster information (rename, change skill level).

    Args:
        cluster_id: ID of cluster to update
        updates: Validated ClusterUpdate model with optional name and skill_level
        repo: Repository instance
        user: Authenticated user
        db: Database session

    Returns:
        Updated cluster information

    Raises:
        HTTPException 404: If cluster not found
        HTTPException 422: If validation fails (handled by Pydantic)
    """
    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(user.username, db)

    # Get cluster from repository
    cluster = await repo.get_cluster(cluster_id)
    if not cluster:
        raise HTTPException(404, f"Cluster {cluster_id} not found")

    # Verify cluster belongs to user's KB (check via any document in the cluster)
    if cluster.doc_ids:
        # Check first document's KB
        first_doc_meta = await repo.get_document_metadata(cluster.doc_ids[0])
        if first_doc_meta and first_doc_meta.knowledge_base_id != kb_id:
            raise HTTPException(404, f"Cluster {cluster_id} not found")

    # Update fields if provided (Pydantic already validated)
    if updates.name is not None:
        # Additional sanitization for safety
        cluster.name = sanitize_cluster_name(updates.name)

    if updates.skill_level is not None:
        cluster.skill_level = updates.skill_level.value

    # Update cluster using repository
    success = await repo.update_cluster(cluster)
    if not success:
        raise HTTPException(500, "Failed to update cluster")

    logger.info(f"Updated cluster {cluster_id} in KB {kb_id}: {cluster.name}")

    # Broadcast WebSocket event for real-time updates
    try:
        await broadcast_cluster_updated(
            knowledge_base_id=kb_id,
            cluster_id=cluster_id,
            cluster_name=cluster.name,
            document_count=len(cluster.doc_ids)
        )
    except Exception as ws_err:
        logger.warning(f"WebSocket broadcast failed (non-critical): {ws_err}")

    return {"message": "Cluster updated", "cluster": cluster.dict()}

# =============================================================================
# Delete Cluster Endpoint
# =============================================================================

@router.delete("/clusters/{cluster_id}")
async def delete_cluster(
    cluster_id: int,
    delete_documents: bool = False,
    repo: KnowledgeBankRepository = Depends(get_repository),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a cluster.

    By default, documents in the cluster become unclustered (cluster_id set to NULL).
    If delete_documents=true, all documents in the cluster are permanently deleted.

    Args:
        cluster_id: ID of cluster to delete
        delete_documents: If true, also delete all documents in the cluster (default: false)
        repo: Repository instance
        user: Authenticated user
        db: Database session

    Returns:
        Success message with deleted cluster info

    Raises:
        HTTPException 404: If cluster not found
        HTTPException 403: If user doesn't own any documents in cluster
    """
    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(user.username, db)

    # Get cluster from repository
    cluster = await repo.get_cluster(cluster_id)
    if not cluster:
        raise HTTPException(404, f"Cluster {cluster_id} not found")

    # Get metadata for documents in cluster
    kb_metadata = await repo.get_metadata_by_kb(kb_id)

    # Check if user owns any documents in this cluster
    has_user_docs = any(
        kb_metadata.get(doc_id) and kb_metadata[doc_id].owner == user.username
        for doc_id in cluster.doc_ids
    )

    if not has_user_docs:
        raise HTTPException(403, "You don't have permission to delete this cluster")

    cluster_name = cluster.name
    doc_count = len(cluster.doc_ids)
    doc_ids_to_process = list(cluster.doc_ids)  # Make a copy

    if delete_documents:
        # DELETE DOCUMENTS PERMANENTLY
        deleted_count = 0
        for doc_id in doc_ids_to_process:
            # Only delete documents owned by this user
            if doc_id in kb_metadata and kb_metadata[doc_id].owner == user.username:
                success = await repo.delete_document(doc_id)
                if success:
                    deleted_count += 1
                    logger.info(f"Deleted document {doc_id}")

        # Delete cluster using repository
        success = await repo.delete_cluster(cluster_id)
        if not success:
            logger.warning(f"Failed to delete cluster {cluster_id} from repository")

        logger.info(f"Deleted cluster {cluster_id} '{cluster_name}' in KB {kb_id} and DELETED {deleted_count} documents permanently")

        # Broadcast WebSocket event for real-time updates
        try:
            await broadcast_cluster_deleted(
                knowledge_base_id=kb_id,
                cluster_id=cluster_id
            )
        except Exception as ws_err:
            logger.warning(f"WebSocket broadcast failed (non-critical): {ws_err}")

        return {
            "message": f"Cluster '{cluster_name}' and {deleted_count} documents deleted permanently",
            "cluster_id": cluster_id,
            "cluster_name": cluster_name,
            "documents_deleted": deleted_count
        }
    else:
        # KEEP DOCUMENTS - delete cluster (documents automatically unclustered via CASCADE)
        success = await repo.delete_cluster(cluster_id)
        if not success:
            raise HTTPException(500, "Failed to delete cluster")

        logger.info(f"Deleted cluster {cluster_id} '{cluster_name}' in KB {kb_id} ({doc_count} documents now unclustered)")

        # Broadcast WebSocket event for real-time updates
        try:
            await broadcast_cluster_deleted(
                knowledge_base_id=kb_id,
                cluster_id=cluster_id
            )
        except Exception as ws_err:
            logger.warning(f"WebSocket broadcast failed (non-critical): {ws_err}")

        return {
            "message": f"Cluster '{cluster_name}' deleted successfully",
            "cluster_id": cluster_id,
            "cluster_name": cluster_name,
            "documents_unclustered": doc_count
        }

# =============================================================================
# Export Cluster Endpoint
# =============================================================================

@router.get("/export/cluster/{cluster_id}")
async def export_cluster(
    cluster_id: int,
    format: ExportFormat = ExportFormat.JSON,
    repo: KnowledgeBankRepository = Depends(get_repository),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export a cluster as JSON or Markdown.

    Args:
        cluster_id: ID of cluster to export
        format: Export format (json or markdown)
        repo: Repository instance
        user: Authenticated user
        db: Database session

    Returns:
        Exported cluster data

    Raises:
        HTTPException 404: If cluster not found
        HTTPException 422: If invalid format (handled by Enum validation)
    """
    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(user.username, db)

    # Get KB-scoped storage from repository
    kb_documents = await repo.get_documents_by_kb(kb_id)
    kb_metadata = await repo.get_metadata_by_kb(kb_id)
    kb_clusters = await repo.get_clusters_by_kb(kb_id)

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
    
    if format == ExportFormat.MARKDOWN:
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
    format: ExportFormat = ExportFormat.JSON,
    repo: KnowledgeBankRepository = Depends(get_repository),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export entire knowledge bank.

    Args:
        format: Export format (json or markdown)
        repo: Repository instance
        user: Authenticated user
        db: Database session

    Returns:
        Exported knowledge bank data

    Raises:
        HTTPException 422: If invalid format (handled by Enum validation)
    """
    # Get user's default knowledge base
    kb_id = get_user_default_kb_id(user.username, db)

    # Get KB-scoped storage from repository
    kb_documents = await repo.get_documents_by_kb(kb_id)
    kb_metadata = await repo.get_metadata_by_kb(kb_id)
    kb_clusters = await repo.get_clusters_by_kb(kb_id)

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

    if format == ExportFormat.MARKDOWN:
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
