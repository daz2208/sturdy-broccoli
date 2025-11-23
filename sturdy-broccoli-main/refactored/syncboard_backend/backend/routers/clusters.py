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
    updates: ClusterUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update cluster information (rename, change skill level).

    Args:
        cluster_id: ID of cluster to update
        updates: Validated ClusterUpdate model with optional name and skill_level
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

        # Update fields if provided (Pydantic already validated)
        if updates.name is not None:
            # Additional sanitization for safety
            cluster.name = sanitize_cluster_name(updates.name)

        if updates.skill_level is not None:
            cluster.skill_level = updates.skill_level.value

        # Save to database
        save_storage_to_db(documents, metadata, clusters, users)

    logger.info(f"Updated cluster {cluster_id} in KB {kb_id}: {cluster.name}")
    return {"message": "Cluster updated", "cluster": cluster.dict()}

# =============================================================================
# Delete Cluster Endpoint
# =============================================================================

@router.delete("/clusters/{cluster_id}")
async def delete_cluster(
    cluster_id: int,
    delete_documents: bool = False,
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

    # Get KB-scoped storage
    kb_documents = get_kb_documents(kb_id)
    kb_metadata = get_kb_metadata(kb_id)
    kb_clusters = get_kb_clusters(kb_id)

    if cluster_id not in kb_clusters:
        raise HTTPException(404, f"Cluster {cluster_id} not found")

    cluster = kb_clusters[cluster_id]

    # Check if user owns any documents in this cluster
    has_user_docs = any(
        kb_metadata.get(doc_id) and kb_metadata[doc_id].owner == user.username
        for doc_id in cluster.doc_ids
    )

    if not has_user_docs:
        raise HTTPException(403, "You don't have permission to delete this cluster")

    # Get global storage for save
    documents = get_documents()
    metadata = get_metadata()
    clusters = get_clusters()
    users = get_users()
    storage_lock = get_storage_lock()

    cluster_name = cluster.name
    doc_count = len(cluster.doc_ids)
    doc_ids_to_process = list(cluster.doc_ids)  # Make a copy

    # CRITICAL: Use lock for thread-safe modifications
    async with storage_lock:
        # STEP 1: DELETE FROM DATABASE FIRST (so it doesn't come back on restart!)
        from ..db_models import DBCluster, DBDocument, DBVectorDocument

        # Delete cluster from database
        db_cluster = db.query(DBCluster).filter_by(id=cluster_id).first()
        if db_cluster:
            db.delete(db_cluster)
            db.commit()
            logger.info(f"Deleted cluster {cluster_id} from DATABASE")

        if delete_documents:
            # DELETE DOCUMENTS PERMANENTLY FROM DATABASE
            deleted_count = 0
            for doc_id in doc_ids_to_process:
                # Only delete documents owned by this user
                if doc_id in kb_metadata and kb_metadata[doc_id].owner == user.username:
                    # Delete from DATABASE first
                    db_doc = db.query(DBDocument).filter_by(doc_id=doc_id).first()
                    if db_doc:
                        db.delete(db_doc)
                        logger.info(f"Deleted document {doc_id} from DATABASE")

                    db_vdoc = db.query(DBVectorDocument).filter_by(doc_id=doc_id).first()
                    if db_vdoc:
                        db.delete(db_vdoc)
                        logger.info(f"Deleted vector document {doc_id} from DATABASE")

                    # Now remove from in-memory storage
                    if doc_id in documents:
                        del documents[doc_id]
                    if doc_id in kb_documents:
                        del kb_documents[doc_id]
                    if doc_id in metadata:
                        del metadata[doc_id]
                    if doc_id in kb_metadata:
                        del kb_metadata[doc_id]

                    deleted_count += 1

            # Commit database deletions
            db.commit()

            # Remove cluster from in-memory storage
            if cluster_id in clusters:
                del clusters[cluster_id]
            if cluster_id in kb_clusters:
                del kb_clusters[cluster_id]

            logger.info(f"Deleted cluster {cluster_id} '{cluster_name}' in KB {kb_id} and DELETED {deleted_count} documents permanently")
            return {
                "message": f"Cluster '{cluster_name}' and {deleted_count} documents deleted permanently",
                "cluster_id": cluster_id,
                "cluster_name": cluster_name,
                "documents_deleted": deleted_count
            }
        else:
            # KEEP DOCUMENTS - just uncluster them in DATABASE
            for doc_id in doc_ids_to_process:
                # Update in DATABASE first
                db_doc = db.query(DBDocument).filter_by(doc_id=doc_id).first()
                if db_doc:
                    db_doc.cluster_id = None
                    logger.info(f"Unclustered document {doc_id} in DATABASE")

                # Update in-memory storage
                if doc_id in metadata:
                    metadata[doc_id].cluster_id = None
                if doc_id in kb_metadata:
                    kb_metadata[doc_id].cluster_id = None

            # Commit database updates
            db.commit()

            # Remove cluster from in-memory storage
            if cluster_id in clusters:
                del clusters[cluster_id]
            if cluster_id in kb_clusters:
                del kb_clusters[cluster_id]

            logger.info(f"Deleted cluster {cluster_id} '{cluster_name}' in KB {kb_id} ({doc_count} documents now unclustered)")
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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export a cluster as JSON or Markdown.

    Args:
        cluster_id: ID of cluster to export
        format: Export format (json or markdown)
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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export entire knowledge bank.

    Args:
        format: Export format (json or markdown)
        user: Authenticated user
        db: Database session

    Returns:
        Exported knowledge bank data

    Raises:
        HTTPException 422: If invalid format (handled by Enum validation)
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
