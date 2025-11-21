"""
Advanced features service (Phase 7.3-7.5).

Handles tags, saved searches, and document relationships.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from .db_models import (
    DBTag,
    DBDocumentTag,
    DBSavedSearch,
    DBDocumentRelationship,
    DBDocument
)

logger = logging.getLogger(__name__)


class TagsService:
    """Manage user-defined tags for documents (Phase 7.3)."""

    def __init__(self, db: Session):
        self.db = db

    def create_tag(self, name: str, username: str, color: Optional[str] = None) -> Dict[str, Any]:
        """Create a new tag for the user."""
        # Check if tag already exists
        existing = self.db.query(DBTag).filter(
            and_(DBTag.name == name, DBTag.owner_username == username)
        ).first()

        if existing:
            return {
                "id": existing.id,
                "name": existing.name,
                "color": existing.color,
                "created_at": existing.created_at.isoformat() if existing.created_at else None
            }

        tag = DBTag(name=name, owner_username=username, color=color)
        self.db.add(tag)
        self.db.commit()

        logger.info(f"Created tag '{name}' for user {username}")

        return {
            "id": tag.id,
            "name": tag.name,
            "color": tag.color,
            "created_at": tag.created_at.isoformat() if tag.created_at else None
        }

    def get_user_tags(self, username: str) -> List[Dict[str, Any]]:
        """Get all tags for a user with document counts."""
        tags = self.db.query(DBTag).filter(
            DBTag.owner_username == username
        ).all()

        result = []
        for tag in tags:
            doc_count = self.db.query(DBDocumentTag).filter(
                DBDocumentTag.tag_id == tag.id
            ).count()

            result.append({
                "id": tag.id,
                "name": tag.name,
                "color": tag.color,
                "document_count": doc_count,
                "created_at": tag.created_at.isoformat()
            })

        return result

    def add_tag_to_document(self, doc_id: int, tag_id: int, username: str) -> Dict[str, Any]:
        """Add a tag to a document."""
        # Verify document ownership
        doc = self.db.query(DBDocument).filter(
            and_(DBDocument.doc_id == doc_id, DBDocument.owner_username == username)
        ).first()

        if not doc:
            raise ValueError("Document not found or not owned by user")

        # Verify tag ownership
        tag = self.db.query(DBTag).filter(
            and_(DBTag.id == tag_id, DBTag.owner_username == username)
        ).first()

        if not tag:
            raise ValueError("Tag not found or not owned by user")

        # Check if already tagged
        existing = self.db.query(DBDocumentTag).filter(
            and_(DBDocumentTag.document_id == doc.id, DBDocumentTag.tag_id == tag_id)
        ).first()

        if existing:
            return {"status": "already_tagged"}

        # Add tag
        doc_tag = DBDocumentTag(document_id=doc.id, tag_id=tag_id)
        self.db.add(doc_tag)
        self.db.commit()

        return {"status": "tagged", "doc_id": doc_id, "tag_id": tag_id}

    def remove_tag_from_document(self, doc_id: int, tag_id: int, username: str) -> Dict[str, Any]:
        """Remove a tag from a document."""
        # Verify document ownership
        doc = self.db.query(DBDocument).filter(
            and_(DBDocument.doc_id == doc_id, DBDocument.owner_username == username)
        ).first()

        if not doc:
            raise ValueError("Document not found")

        # Remove tag
        deleted = self.db.query(DBDocumentTag).filter(
            and_(DBDocumentTag.document_id == doc.id, DBDocumentTag.tag_id == tag_id)
        ).delete()

        self.db.commit()

        return {"status": "removed" if deleted > 0 else "not_found"}

    def get_document_tags(self, doc_id: int) -> List[Dict[str, Any]]:
        """Get all tags for a document."""
        doc = self.db.query(DBDocument).filter(DBDocument.doc_id == doc_id).first()
        if not doc:
            return []

        doc_tags = self.db.query(DBTag).join(DBDocumentTag).filter(
            DBDocumentTag.document_id == doc.id
        ).all()

        return [
            {
                "id": tag.id,
                "name": tag.name,
                "color": tag.color
            }
            for tag in doc_tags
        ]

    def delete_tag(self, tag_id: int, username: str) -> Dict[str, Any]:
        """Delete a tag (removes from all documents)."""
        tag = self.db.query(DBTag).filter(
            and_(DBTag.id == tag_id, DBTag.owner_username == username)
        ).first()

        if not tag:
            raise ValueError("Tag not found")

        # Delete all document-tag relationships
        self.db.query(DBDocumentTag).filter(DBDocumentTag.tag_id == tag_id).delete()

        # Delete tag
        self.db.delete(tag)
        self.db.commit()

        return {"status": "deleted", "tag_id": tag_id}


class SavedSearchesService:
    """Manage saved search queries (Phase 7.4)."""

    def __init__(self, db: Session):
        self.db = db

    def save_search(
        self,
        name: str,
        query: str,
        filters: Optional[Dict[str, Any]],
        username: str
    ) -> Dict[str, Any]:
        """Save a search query for quick access."""
        saved_search = DBSavedSearch(
            owner_username=username,
            name=name,
            query=query,
            filters=filters
        )

        self.db.add(saved_search)
        self.db.commit()

        logger.info(f"Saved search '{name}' for user {username}")

        return {
            "id": saved_search.id,
            "name": saved_search.name,
            "query": saved_search.query,
            "filters": saved_search.filters,
            "created_at": saved_search.created_at.isoformat() if saved_search.created_at else None
        }

    def get_saved_searches(self, username: str) -> List[Dict[str, Any]]:
        """Get all saved searches for a user."""
        searches = self.db.query(DBSavedSearch).filter(
            DBSavedSearch.owner_username == username
        ).order_by(DBSavedSearch.last_used_at.desc().nullsfirst()).all()

        return [
            {
                "id": search.id,
                "name": search.name,
                "query": search.query,
                "filters": search.filters,
                "use_count": search.use_count,
                "last_used_at": search.last_used_at.isoformat() if search.last_used_at else None,
                "created_at": search.created_at.isoformat() if search.created_at else None
            }
            for search in searches
        ]

    def use_saved_search(self, search_id: int, username: str) -> Dict[str, Any]:
        """Mark a saved search as used (updates stats)."""
        search = self.db.query(DBSavedSearch).filter(
            and_(DBSavedSearch.id == search_id, DBSavedSearch.owner_username == username)
        ).first()

        if not search:
            raise ValueError("Saved search not found")

        search.use_count += 1
        search.last_used_at = datetime.utcnow()
        self.db.commit()

        return {
            "query": search.query,
            "filters": search.filters
        }

    def delete_saved_search(self, search_id: int, username: str) -> Dict[str, Any]:
        """Delete a saved search."""
        deleted = self.db.query(DBSavedSearch).filter(
            and_(DBSavedSearch.id == search_id, DBSavedSearch.owner_username == username)
        ).delete()

        self.db.commit()

        return {"status": "deleted" if deleted > 0 else "not_found"}


class DocumentRelationshipsService:
    """Manage relationships between documents (Phase 7.5)."""

    def __init__(self, db: Session, vector_store=None, documents=None):
        self.db = db
        self.vector_store = vector_store
        self.documents = documents

    def add_relationship(
        self,
        source_doc_id: int,
        target_doc_id: int,
        relationship_type: str,
        username: str,
        strength: Optional[float] = None
    ) -> Dict[str, Any]:
        """Create a relationship between two documents."""
        # Verify document ownership
        source_doc = self.db.query(DBDocument).filter(
            and_(DBDocument.doc_id == source_doc_id, DBDocument.owner_username == username)
        ).first()

        target_doc = self.db.query(DBDocument).filter(
            and_(DBDocument.doc_id == target_doc_id, DBDocument.owner_username == username)
        ).first()

        if not source_doc or not target_doc:
            raise ValueError("One or both documents not found or not owned by user")

        # Check if relationship already exists
        existing = self.db.query(DBDocumentRelationship).filter(
            and_(
                DBDocumentRelationship.source_doc_id == source_doc.id,
                DBDocumentRelationship.target_doc_id == target_doc.id,
                DBDocumentRelationship.relationship_type == relationship_type
            )
        ).first()

        if existing:
            return {"status": "already_exists", "relationship_id": existing.id}

        # Create relationship
        relationship = DBDocumentRelationship(
            source_doc_id=source_doc.id,
            target_doc_id=target_doc.id,
            relationship_type=relationship_type,
            strength=strength,
            created_by_username=username
        )

        self.db.add(relationship)
        self.db.commit()

        logger.info(f"Created {relationship_type} relationship: {source_doc_id} -> {target_doc_id}")

        return {
            "status": "created",
            "relationship_id": relationship.id,
            "source_doc_id": source_doc_id,
            "target_doc_id": target_doc_id,
            "type": relationship_type
        }

    def get_related_documents(
        self,
        doc_id: int,
        relationship_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all documents related to a given document."""
        doc = self.db.query(DBDocument).filter(DBDocument.doc_id == doc_id).first()
        if not doc:
            return []

        # Query relationships where this doc is source or target
        query = self.db.query(DBDocumentRelationship).filter(
            or_(
                DBDocumentRelationship.source_doc_id == doc.id,
                DBDocumentRelationship.target_doc_id == doc.id
            )
        )

        if relationship_type:
            query = query.filter(DBDocumentRelationship.relationship_type == relationship_type)

        relationships = query.all()

        # Build result list
        result = []
        for rel in relationships:
            # Determine which is the "other" document
            if rel.source_doc_id == doc.id:
                other_doc_internal_id = rel.target_doc_id
                direction = "outgoing"
            else:
                other_doc_internal_id = rel.source_doc_id
                direction = "incoming"

            # Get the other document's doc_id
            other_doc = self.db.query(DBDocument).filter(
                DBDocument.id == other_doc_internal_id
            ).first()

            if other_doc:
                result.append({
                    "doc_id": other_doc.doc_id,
                    "relationship_type": rel.relationship_type,
                    "direction": direction,
                    "strength": rel.strength,
                    "source_type": other_doc.source_type,
                    "skill_level": other_doc.skill_level,
                    "cluster_id": other_doc.cluster_id
                })

        return result

    def delete_relationship(
        self,
        source_doc_id: int,
        target_doc_id: int,
        username: str
    ) -> Dict[str, Any]:
        """Delete a relationship between documents."""
        # Get internal IDs
        source_doc = self.db.query(DBDocument).filter(
            and_(DBDocument.doc_id == source_doc_id, DBDocument.owner_username == username)
        ).first()

        target_doc = self.db.query(DBDocument).filter(
            and_(DBDocument.doc_id == target_doc_id, DBDocument.owner_username == username)
        ).first()

        if not source_doc or not target_doc:
            raise ValueError("Document not found")

        # Delete relationship
        deleted = self.db.query(DBDocumentRelationship).filter(
            and_(
                DBDocumentRelationship.source_doc_id == source_doc.id,
                DBDocumentRelationship.target_doc_id == target_doc.id
            )
        ).delete()

        self.db.commit()

        return {"status": "deleted" if deleted > 0 else "not_found"}

    def find_related_documents(
        self,
        doc_id: int,
        username: str,
        top_k: int = 5,
        min_similarity: float = 0.1
    ) -> List[Dict[str, Any]]:
        """
        Auto-discover documents similar to this one using vector search.

        Args:
            doc_id: Document ID to find related documents for
            username: Username for ownership verification
            top_k: Maximum number of related documents to return
            min_similarity: Minimum similarity score threshold (0.0-1.0)

        Returns:
            List of related documents with similarity scores and metadata
        """
        # Verify document exists and user owns it
        doc = self.db.query(DBDocument).filter(
            and_(DBDocument.doc_id == doc_id, DBDocument.owner_username == username)
        ).first()

        if not doc:
            raise ValueError("Document not found or not owned by user")

        # Check if vector store and documents are available
        if not self.vector_store or not self.documents:
            logger.warning("Vector store or documents not available for auto-discovery")
            return []

        # Get document content from in-memory store
        # Documents are nested by kb_id
        kb_id = doc.knowledge_base_id
        if not kb_id or kb_id not in self.documents:
            logger.warning(f"Document {doc_id} not found in in-memory store")
            return []

        if doc_id not in self.documents[kb_id]:
            logger.warning(f"Document {doc_id} not in KB {kb_id}")
            return []

        doc_content = self.documents[kb_id][doc_id]

        # Use search_by_doc_id for document-to-document similarity
        # This method returns (doc_id, similarity_score) tuples
        try:
            search_results = self.vector_store.search_by_doc_id(doc_id, top_k=top_k + 1)
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

        # Filter out self and documents below similarity threshold
        related = []
        for result_doc_id, similarity_score in search_results:
            # Skip self-match
            if result_doc_id == doc_id:
                continue

            # Check similarity threshold
            if similarity_score < min_similarity:
                continue

            # Verify the related document exists in database and belongs to same user
            related_doc = self.db.query(DBDocument).filter(
                and_(
                    DBDocument.doc_id == result_doc_id,
                    DBDocument.owner_username == username
                )
            ).first()

            if related_doc:
                related.append({
                    "doc_id": result_doc_id,
                    "similarity_score": round(similarity_score, 4),
                    "source_type": related_doc.source_type,
                    "skill_level": related_doc.skill_level,
                    "cluster_id": related_doc.cluster_id,
                    "filename": related_doc.filename,
                    "source_url": related_doc.source_url,
                    "ingested_at": related_doc.ingested_at.isoformat() if related_doc.ingested_at else None
                })

            # Stop when we have enough results
            if len(related) >= top_k:
                break

        logger.info(f"Found {len(related)} related documents for doc {doc_id}")
        return related
