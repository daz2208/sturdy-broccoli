"""
Knowledge Base API Router

Endpoints for managing knowledge bases and build suggestions.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid
from datetime import datetime

from ..database import get_db
from ..dependencies import get_current_user, get_kb_documents, get_kb_metadata, get_kb_clusters, get_build_suggester
from ..db_models import DBKnowledgeBase, DBBuildSuggestion, DBDocument, DBCluster
from ..models import (
    KnowledgeBase,
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseList,
    SavedBuildSuggestion,
    BuildSuggestionUpdate,
    BuildSuggestionList,
    BuildSuggestionGenerate,
    User
)

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


# =============================================================================
# Knowledge Base CRUD
# =============================================================================

@router.get("", response_model=KnowledgeBaseList)
async def list_knowledge_bases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all knowledge bases for the current user."""
    bases = db.query(DBKnowledgeBase).filter(
        DBKnowledgeBase.owner_username == current_user.username
    ).order_by(
        DBKnowledgeBase.is_default.desc(),
        DBKnowledgeBase.last_accessed_at.desc().nullslast(),
        DBKnowledgeBase.created_at.desc()
    ).all()

    return KnowledgeBaseList(
        knowledge_bases=[KnowledgeBase.model_validate(kb) for kb in bases],
        total=len(bases)
    )


@router.post("", response_model=KnowledgeBase, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    kb_data: KnowledgeBaseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new knowledge base."""

    # If setting as default, unset other defaults
    if kb_data.is_default:
        db.query(DBKnowledgeBase).filter(
            DBKnowledgeBase.owner_username == current_user.username,
            DBKnowledgeBase.is_default == True
        ).update({DBKnowledgeBase.is_default: False})

    # Create new knowledge base
    kb = DBKnowledgeBase(
        id=str(uuid.uuid4()),
        name=kb_data.name,
        description=kb_data.description,
        owner_username=current_user.username,
        is_default=kb_data.is_default,
        document_count=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db.add(kb)
    db.commit()
    db.refresh(kb)

    return KnowledgeBase.model_validate(kb)


@router.get("/{kb_id}", response_model=KnowledgeBase)
async def get_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific knowledge base."""
    kb = db.query(DBKnowledgeBase).filter(
        DBKnowledgeBase.id == kb_id,
        DBKnowledgeBase.owner_username == current_user.username
    ).first()

    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found"
        )

    # Update last accessed timestamp
    kb.last_accessed_at = datetime.utcnow()
    db.commit()

    return KnowledgeBase.model_validate(kb)


@router.patch("/{kb_id}", response_model=KnowledgeBase)
async def update_knowledge_base(
    kb_id: str,
    kb_update: KnowledgeBaseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a knowledge base."""
    kb = db.query(DBKnowledgeBase).filter(
        DBKnowledgeBase.id == kb_id,
        DBKnowledgeBase.owner_username == current_user.username
    ).first()

    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found"
        )

    # Update fields
    if kb_update.name is not None:
        kb.name = kb_update.name
    if kb_update.description is not None:
        kb.description = kb_update.description
    if kb_update.is_default is not None:
        if kb_update.is_default:
            # Unset other defaults
            db.query(DBKnowledgeBase).filter(
                DBKnowledgeBase.owner_username == current_user.username,
                DBKnowledgeBase.id != kb_id
            ).update({DBKnowledgeBase.is_default: False})
        kb.is_default = kb_update.is_default

    kb.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(kb)

    return KnowledgeBase.model_validate(kb)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a knowledge base (and all its documents/clusters)."""
    kb = db.query(DBKnowledgeBase).filter(
        DBKnowledgeBase.id == kb_id,
        DBKnowledgeBase.owner_username == current_user.username
    ).first()

    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found"
        )

    # Prevent deleting the last knowledge base
    kb_count = db.query(DBKnowledgeBase).filter(
        DBKnowledgeBase.owner_username == current_user.username
    ).count()

    if kb_count == 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your only knowledge base"
        )

    # If deleting default, make another one default
    if kb.is_default:
        other_kb = db.query(DBKnowledgeBase).filter(
            DBKnowledgeBase.owner_username == current_user.username,
            DBKnowledgeBase.id != kb_id
        ).first()
        if other_kb:
            other_kb.is_default = True

    db.delete(kb)
    db.commit()


@router.get("/{kb_id}/stats")
async def get_knowledge_base_stats(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get statistics for a knowledge base.

    Returns:
        - total_documents: Number of documents in the KB
        - total_clusters: Number of clusters in the KB
        - total_concepts: Total concepts extracted
        - disk_usage_mb: Approximate storage used
    """
    kb = db.query(DBKnowledgeBase).filter(
        DBKnowledgeBase.id == kb_id,
        DBKnowledgeBase.owner_username == current_user.username
    ).first()

    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found"
        )

    # Count documents
    total_documents = db.query(DBDocument).filter(
        DBDocument.knowledge_base_id == kb_id
    ).count()

    # Count clusters
    total_clusters = db.query(DBCluster).filter(
        DBCluster.knowledge_base_id == kb_id
    ).count()

    # Estimate total concepts (from documents)
    from sqlalchemy import func
    from ..db_models import DBConcept
    total_concepts = db.query(DBConcept).join(DBDocument).filter(
        DBDocument.knowledge_base_id == kb_id
    ).count()

    # Estimate disk usage (based on content length)
    content_size = db.query(func.sum(DBDocument.content_length)).filter(
        DBDocument.knowledge_base_id == kb_id
    ).scalar() or 0
    disk_usage_mb = round(content_size / (1024 * 1024), 2)

    return {
        "knowledge_base_id": kb_id,
        "total_documents": total_documents,
        "total_clusters": total_clusters,
        "total_concepts": total_concepts,
        "disk_usage_mb": disk_usage_mb
    }


# =============================================================================
# Build Suggestions
# =============================================================================

@router.post("/{kb_id}/suggestions/generate", response_model=BuildSuggestionList)
async def generate_build_suggestions(
    kb_id: str,
    gen_request: BuildSuggestionGenerate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate new build suggestions for a knowledge base."""
    # Verify knowledge base exists and belongs to user
    kb = db.query(DBKnowledgeBase).filter(
        DBKnowledgeBase.id == kb_id,
        DBKnowledgeBase.owner_username == current_user.username
    ).first()

    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found"
        )

    # Get documents, metadata, clusters for THIS knowledge base only
    kb_docs = get_kb_documents(kb_id)
    kb_meta = get_kb_metadata(kb_id)
    kb_clusts = get_kb_clusters(kb_id)

    # Generate suggestions
    suggester = get_build_suggester()
    suggestions = await suggester.analyze_knowledge_bank(
        clusters=kb_clusts,
        metadata=kb_meta,
        documents=kb_docs,
        max_suggestions=gen_request.max_suggestions
    )

    # Save suggestions to database
    db_suggestions = []
    for suggestion in suggestions:
        db_suggestion = DBBuildSuggestion(
            knowledge_base_id=kb_id,
            title=suggestion.title,
            description=suggestion.description,
            feasibility=suggestion.feasibility,
            effort_estimate=suggestion.effort_estimate,
            required_skills=suggestion.required_skills,
            missing_knowledge=suggestion.missing_knowledge,
            relevant_clusters=suggestion.relevant_clusters,
            starter_steps=suggestion.starter_steps,
            file_structure=suggestion.file_structure,
            knowledge_coverage=getattr(suggestion, 'knowledge_coverage', None),
            created_at=datetime.utcnow()
        )
        db.add(db_suggestion)
        db_suggestions.append(db_suggestion)

    db.commit()

    # Refresh to get IDs
    for s in db_suggestions:
        db.refresh(s)

    return BuildSuggestionList(
        suggestions=[SavedBuildSuggestion.model_validate(s) for s in db_suggestions],
        total=len(db_suggestions)
    )


@router.get("/{kb_id}/suggestions", response_model=BuildSuggestionList)
async def list_build_suggestions(
    kb_id: str,
    include_completed: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all saved build suggestions for a knowledge base."""
    # Verify knowledge base access
    kb = db.query(DBKnowledgeBase).filter(
        DBKnowledgeBase.id == kb_id,
        DBKnowledgeBase.owner_username == current_user.username
    ).first()

    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found"
        )

    query = db.query(DBBuildSuggestion).filter(
        DBBuildSuggestion.knowledge_base_id == kb_id
    )

    if not include_completed:
        query = query.filter(DBBuildSuggestion.is_completed == False)

    suggestions = query.order_by(DBBuildSuggestion.created_at.desc()).all()

    return BuildSuggestionList(
        suggestions=[SavedBuildSuggestion.model_validate(s) for s in suggestions],
        total=len(suggestions)
    )


@router.patch("/{kb_id}/suggestions/{suggestion_id}", response_model=SavedBuildSuggestion)
async def update_build_suggestion(
    kb_id: str,
    suggestion_id: int,
    update_data: BuildSuggestionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a build suggestion (mark complete, add notes)."""
    # Verify ownership through knowledge base
    suggestion = db.query(DBBuildSuggestion).join(DBKnowledgeBase).filter(
        DBBuildSuggestion.id == suggestion_id,
        DBBuildSuggestion.knowledge_base_id == kb_id,
        DBKnowledgeBase.owner_username == current_user.username
    ).first()

    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Build suggestion not found"
        )

    if update_data.is_completed is not None:
        suggestion.is_completed = update_data.is_completed
        if update_data.is_completed:
            suggestion.completed_at = datetime.utcnow()
        else:
            suggestion.completed_at = None

    if update_data.notes is not None:
        suggestion.notes = update_data.notes

    db.commit()
    db.refresh(suggestion)

    return SavedBuildSuggestion.model_validate(suggestion)


@router.delete("/{kb_id}/suggestions/{suggestion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_build_suggestion(
    kb_id: str,
    suggestion_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a build suggestion."""
    suggestion = db.query(DBBuildSuggestion).join(DBKnowledgeBase).filter(
        DBBuildSuggestion.id == suggestion_id,
        DBBuildSuggestion.knowledge_base_id == kb_id,
        DBKnowledgeBase.owner_username == current_user.username
    ).first()

    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Build suggestion not found"
        )

    db.delete(suggestion)
    db.commit()
