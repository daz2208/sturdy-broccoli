"""
Duplicate detection service (Phase 7.2).

Uses TF-IDF vector similarity to identify potentially duplicate documents.
"""

import logging
from typing import List, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from .db_models import DBDocument, DBVectorDocument
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Detect duplicate or highly similar documents."""

    def __init__(self, db: Session, vector_store: VectorStore):
        """
        Initialize duplicate detector.

        Args:
            db: Database session
            vector_store: Vector store for similarity calculations
        """
        self.db = db
        self.vector_store = vector_store

    def _extract_title_from_content(self, content: str, source_type: str) -> str:
        """
        Extract title from document content.

        For YouTube/TikTok: Extracts from "YOUTUBE VIDEO: ..." or "TIKTOK VIDEO: ..." header
        For web articles: Extracts from first line or content
        Returns None if no title found.
        """
        if not content:
            return None

        lines = content.split('\n')

        # YouTube videos
        if source_type == 'url' and 'YOUTUBE VIDEO:' in content[:200]:
            for line in lines[:5]:
                if line.startswith('YOUTUBE VIDEO:'):
                    return line.replace('YOUTUBE VIDEO:', '').strip()

        # TikTok videos
        if source_type == 'url' and 'TIKTOK VIDEO:' in content[:200]:
            for line in lines[:5]:
                if line.startswith('TIKTOK VIDEO:'):
                    return line.replace('TIKTOK VIDEO:', '').strip()

        # Web articles
        if source_type == 'url' and 'WEB ARTICLE:' in content[:200]:
            for line in lines[:5]:
                if line.startswith('WEB ARTICLE:'):
                    return line.replace('WEB ARTICLE:', '').strip()

        return None

    def _build_duplicate_list(self, duplicates: list, duplicate_docs_meta: list) -> list:
        """Build list of duplicate documents with titles extracted from content."""
        result = []
        for dup in duplicates:
            doc_id = dup["doc_id"]
            meta = next((d for d in duplicate_docs_meta if d.doc_id == doc_id), None)

            # Get content for title extraction
            doc_vec = self.db.query(DBVectorDocument).filter(
                DBVectorDocument.doc_id == doc_id
            ).first()
            title = self._extract_title_from_content(
                doc_vec.content if doc_vec else "",
                meta.source_type if meta else ""
            )

            result.append({
                "doc_id": doc_id,
                "similarity": dup["similarity"],
                "title": title,
                "source_type": meta.source_type if meta else None,
                "source_url": meta.source_url if meta else None,
                "filename": meta.filename if meta else None,
                "skill_level": meta.skill_level if meta else None,
                "cluster_id": meta.cluster_id if meta else None,
                "created_at": meta.ingested_at.isoformat() if meta and meta.ingested_at else None
            })
        return result

    def find_duplicates(
        self,
        username: str,
        similarity_threshold: float = 0.85,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Find duplicate documents based on content similarity.

        Args:
            username: Username to filter documents
            similarity_threshold: Minimum similarity score (0-1) to consider duplicates
            limit: Maximum number of duplicate groups to return

        Returns:
            Dictionary with duplicate_groups and total_duplicates_found
        """
        # Get user's documents with content for title extraction
        user_docs = self.db.query(DBDocument).filter(
            DBDocument.owner_username == username
        ).all()

        if len(user_docs) < 2:
            return {"duplicate_groups": [], "total_duplicates_found": 0}

        doc_ids = [doc.doc_id for doc in user_docs]

        # Find duplicates using vector similarity
        duplicate_groups = []

        # Track which documents we've already grouped
        grouped_docs = set()

        for i, doc_id1 in enumerate(doc_ids):
            if doc_id1 in grouped_docs:
                continue

            # Find similar documents
            similar_docs = self.vector_store.search_by_doc_id(
                doc_id1,
                top_k=min(20, len(doc_ids))
            )

            # Filter by similarity threshold and user's documents
            duplicates = []
            for sim_doc_id, similarity in similar_docs:
                if (
                    sim_doc_id != doc_id1
                    and sim_doc_id in doc_ids
                    and sim_doc_id not in grouped_docs
                    and similarity >= similarity_threshold
                ):
                    duplicates.append({
                        "doc_id": sim_doc_id,
                        "similarity": float(similarity)
                    })
                    grouped_docs.add(sim_doc_id)

            if duplicates:
                # Get document metadata
                main_doc = next((d for d in user_docs if d.doc_id == doc_id1), None)

                duplicate_ids = [d["doc_id"] for d in duplicates]
                duplicate_docs_meta = [
                    d for d in user_docs if d.doc_id in duplicate_ids
                ]

                # Get content for title extraction
                main_doc_vec = self.db.query(DBVectorDocument).filter(
                    DBVectorDocument.doc_id == doc_id1
                ).first()
                main_doc_title = self._extract_title_from_content(
                    main_doc_vec.content if main_doc_vec else "",
                    main_doc.source_type if main_doc else ""
                )

                group = {
                    "primary_doc": {
                        "doc_id": doc_id1,
                        "title": main_doc_title,
                        "source_type": main_doc.source_type if main_doc else None,
                        "source_url": main_doc.source_url if main_doc else None,
                        "filename": main_doc.filename if main_doc else None,
                        "skill_level": main_doc.skill_level if main_doc else None,
                        "cluster_id": main_doc.cluster_id if main_doc else None,
                        "created_at": main_doc.ingested_at.isoformat() if main_doc and main_doc.ingested_at else None
                    },
                    "duplicates": self._build_duplicate_list(duplicates, duplicate_docs_meta),
                    "group_size": len(duplicates) + 1
                }

                duplicate_groups.append(group)
                grouped_docs.add(doc_id1)

                if len(duplicate_groups) >= limit:
                    break

        # Sort by group size (largest groups first)
        duplicate_groups.sort(key=lambda g: g["group_size"], reverse=True)

        # Count total duplicates (not including primary docs)
        total_duplicates = sum(len(g["duplicates"]) for g in duplicate_groups)

        return {
            "duplicate_groups": duplicate_groups,
            "total_duplicates_found": total_duplicates
        }

    def compare_two_documents(
        self,
        doc_id1: int,
        doc_id2: int,
        username: str
    ) -> Dict[str, Any]:
        """
        Compare two specific documents.

        Args:
            doc_id1: First document ID
            doc_id2: Second document ID
            username: Username for authorization check

        Returns:
            Dictionary with similarity_score, doc1, and doc2 info
        """
        # Verify both documents belong to user
        doc1_meta = self.db.query(DBDocument).filter(
            DBDocument.doc_id == doc_id1,
            DBDocument.owner_username == username
        ).first()

        if not doc1_meta:
            raise ValueError(f"Document not found")

        doc2_meta = self.db.query(DBDocument).filter(
            DBDocument.doc_id == doc_id2,
            DBDocument.owner_username == username
        ).first()

        if not doc2_meta:
            raise ValueError(f"Document not found")

        # Same document check
        if doc_id1 == doc_id2:
            return {
                "similarity_score": 1.0,
                "doc1": {
                    "doc_id": doc_id1,
                    "source_type": doc1_meta.source_type,
                    "skill_level": doc1_meta.skill_level,
                    "cluster_id": doc1_meta.cluster_id
                },
                "doc2": {
                    "doc_id": doc_id2,
                    "source_type": doc2_meta.source_type,
                    "skill_level": doc2_meta.skill_level,
                    "cluster_id": doc2_meta.cluster_id
                }
            }

        # Calculate similarity
        similarity = 0.0
        results = self.vector_store.search_by_doc_id(doc_id1, top_k=100)
        for did, sim in results:
            if did == doc_id2:
                similarity = float(sim)
                break

        return {
            "similarity_score": similarity,
            "doc1": {
                "doc_id": doc_id1,
                "source_type": doc1_meta.source_type,
                "skill_level": doc1_meta.skill_level,
                "cluster_id": doc1_meta.cluster_id
            },
            "doc2": {
                "doc_id": doc_id2,
                "source_type": doc2_meta.source_type,
                "skill_level": doc2_meta.skill_level,
                "cluster_id": doc2_meta.cluster_id
            }
        }

    def get_duplicate_content(
        self,
        doc_id1: int,
        doc_id2: int
    ) -> Dict[str, Any]:
        """
        Get content and metadata for two documents to compare.

        Args:
            doc_id1: First document ID
            doc_id2: Second document ID

        Returns:
            Dictionary with both documents' content and metadata
        """
        doc1_vec = self.db.query(DBVectorDocument).filter(
            DBVectorDocument.doc_id == doc_id1
        ).first()

        doc2_vec = self.db.query(DBVectorDocument).filter(
            DBVectorDocument.doc_id == doc_id2
        ).first()

        doc1_meta = self.db.query(DBDocument).filter(
            DBDocument.doc_id == doc_id1
        ).first()

        doc2_meta = self.db.query(DBDocument).filter(
            DBDocument.doc_id == doc_id2
        ).first()

        # Calculate similarity
        similarity = 0.0
        if doc1_vec and doc2_vec:
            results = self.vector_store.search_by_doc_id(doc_id1, top_k=100)
            for did, sim in results:
                if did == doc_id2:
                    similarity = float(sim)
                    break

        # Extract titles from content
        doc1_title = self._extract_title_from_content(
            doc1_vec.content if doc1_vec else "",
            doc1_meta.source_type if doc1_meta else ""
        )
        doc2_title = self._extract_title_from_content(
            doc2_vec.content if doc2_vec else "",
            doc2_meta.source_type if doc2_meta else ""
        )

        return {
            "doc1": {
                "doc_id": doc_id1,
                "title": doc1_title,
                "content": doc1_vec.content if doc1_vec else "",
                "source_type": doc1_meta.source_type if doc1_meta else None,
                "source_url": doc1_meta.source_url if doc1_meta else None,
                "filename": doc1_meta.filename if doc1_meta else None,
                "skill_level": doc1_meta.skill_level if doc1_meta else None,
                "cluster_id": doc1_meta.cluster_id if doc1_meta else None,
                "created_at": doc1_meta.ingested_at.isoformat() if doc1_meta and doc1_meta.ingested_at else None
            },
            "doc2": {
                "doc_id": doc_id2,
                "title": doc2_title,
                "content": doc2_vec.content if doc2_vec else "",
                "source_type": doc2_meta.source_type if doc2_meta else None,
                "source_url": doc2_meta.source_url if doc2_meta else None,
                "filename": doc2_meta.filename if doc2_meta else None,
                "skill_level": doc2_meta.skill_level if doc2_meta else None,
                "cluster_id": doc2_meta.cluster_id if doc2_meta else None,
                "created_at": doc2_meta.ingested_at.isoformat() if doc2_meta and doc2_meta.ingested_at else None
            },
            "similarity": similarity
        }

    def merge_duplicates(
        self,
        keep_doc_id: int,
        delete_doc_ids: List[int],
        username: str
    ) -> Dict[str, Any]:
        """
        Merge duplicate documents by keeping one and deleting others.

        Args:
            keep_doc_id: Document ID to keep
            delete_doc_ids: List of document IDs to delete
            username: Username for authorization check

        Returns:
            Result dictionary with merge status
        """
        # Verify keep document exists and belongs to user
        keep_doc = self.db.query(DBDocument).filter(
            DBDocument.doc_id == keep_doc_id,
            DBDocument.owner_username == username
        ).first()

        if not keep_doc:
            raise ValueError(f"Document {keep_doc_id} not found")

        # Verify all delete documents exist and belong to user
        delete_docs = []
        for doc_id in delete_doc_ids:
            doc = self.db.query(DBDocument).filter(
                DBDocument.doc_id == doc_id,
                DBDocument.owner_username == username
            ).first()

            if not doc:
                raise ValueError(f"Document {doc_id} not found")

            delete_docs.append(doc)

        # Delete the duplicate documents
        deleted_ids = []
        for doc in delete_docs:
            # Delete from vector documents
            vector_doc = self.db.query(DBVectorDocument).filter(
                DBVectorDocument.doc_id == doc.doc_id
            ).first()
            if vector_doc:
                self.db.delete(vector_doc)

            # Delete concepts - Use document_id (foreign key to documents.id)
            from .db_models import DBConcept
            concepts = self.db.query(DBConcept).filter(
                DBConcept.document_id == doc.id
            ).all()
            for concept in concepts:
                self.db.delete(concept)

            # Delete document
            self.db.delete(doc)

            # Remove from vector store
            if self.vector_store:
                self.vector_store.remove_document(doc.doc_id)

            deleted_ids.append(doc.doc_id)

        self.db.commit()

        logger.info(f"Merged duplicates: kept doc {keep_doc_id}, deleted {len(deleted_ids)} documents")

        return {
            "status": "merged",
            "kept_doc_id": keep_doc_id,
            "deleted_doc_ids": deleted_ids
        }
