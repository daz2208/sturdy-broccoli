"""
Database Storage Adapter (Phase 6.5).

Provides file-storage-compatible interface using database backend.
Drop-in replacement for storage.py with database persistence.

Updated for Phase 8: Multi-Knowledge Base support with nested dict structure.
"""

import logging
from typing import Dict, Tuple
from sqlalchemy.orm import Session

from .models import DocumentMetadata, Cluster, Concept
from .db_models import DBUser, DBCluster, DBDocument, DBConcept, DBVectorDocument, DBKnowledgeBase
from .vector_store import VectorStore
from .database import get_db_context

logger = logging.getLogger(__name__)


def load_storage_from_db(
    vector_store: VectorStore
) -> Tuple[Dict[str, Dict[int, str]], Dict[str, Dict[int, DocumentMetadata]], Dict[str, Dict[int, Cluster]], Dict[str, str]]:
    """
    Load documents, metadata, clusters, and users from database.

    Args:
        vector_store: VectorStore instance where document embeddings will be added

    Returns:
        Tuple of (documents, metadata, clusters, users) where:
        - documents: Dict[kb_id, Dict[doc_id, full_text]]
        - metadata: Dict[kb_id, Dict[doc_id, DocumentMetadata]]
        - clusters: Dict[kb_id, Dict[cluster_id, Cluster]]
        - users: Dict[username, hashed_password]
    """
    documents: Dict[str, Dict[int, str]] = {}
    metadata: Dict[str, Dict[int, DocumentMetadata]] = {}
    clusters: Dict[str, Dict[int, Cluster]] = {}
    users: Dict[str, str] = {}

    try:
        with get_db_context() as db:
            # Load vector documents and rebuild vector store
            # CRITICAL FIX: Load in order and verify doc_id alignment
            vector_docs = db.query(DBVectorDocument).order_by(DBVectorDocument.doc_id).all()

            for vdoc in vector_docs:
                # Add to vector store using the persisted document ID
                vector_store.add_document(vdoc.content, doc_id=vdoc.doc_id)

            # Load document metadata (grouped by knowledge base)
            db_docs = db.query(DBDocument).all()
            for db_doc in db_docs:
                kb_id = db_doc.knowledge_base_id or "default"

                # Ensure KB exists in dicts
                if kb_id not in documents:
                    documents[kb_id] = {}
                if kb_id not in metadata:
                    metadata[kb_id] = {}

                # Get content from vector store
                vdoc = db.query(DBVectorDocument).filter_by(doc_id=db_doc.doc_id).first()
                if vdoc:
                    documents[kb_id][db_doc.doc_id] = vdoc.content
                else:
                    # Vector document missing - still load metadata but log warning
                    # Document will be visible but content empty
                    logger.warning(f"Vector document missing for doc_id={db_doc.doc_id}, metadata will be loaded but content empty")
                    documents[kb_id][db_doc.doc_id] = ""  # Empty content so doc still appears

                # Load concepts
                concepts = [
                    Concept(
                        name=c.name,
                        category=c.category,
                        confidence=c.confidence
                    )
                    for c in db_doc.concepts
                ]

                metadata[kb_id][db_doc.doc_id] = DocumentMetadata(
                    doc_id=db_doc.doc_id,
                    owner=db_doc.owner_username,
                    source_type=db_doc.source_type,
                    source_url=db_doc.source_url,
                    filename=db_doc.filename,
                    image_path=db_doc.image_path,
                    concepts=concepts,
                    skill_level=db_doc.skill_level,
                    cluster_id=db_doc.cluster_id,
                    knowledge_base_id=db_doc.knowledge_base_id,
                    ingested_at=db_doc.ingested_at.isoformat() if db_doc.ingested_at else None,
                    content_length=db_doc.content_length
                )

            # Load clusters (grouped by knowledge base)
            db_clusters = db.query(DBCluster).all()
            for db_cluster in db_clusters:
                kb_id = db_cluster.knowledge_base_id or "default"

                if kb_id not in clusters:
                    clusters[kb_id] = {}

                # Get document IDs in this cluster
                doc_ids = [doc.doc_id for doc in db_cluster.documents]

                clusters[kb_id][db_cluster.id] = Cluster(
                    id=db_cluster.id,
                    name=db_cluster.name,
                    doc_ids=doc_ids,
                    primary_concepts=db_cluster.primary_concepts,
                    skill_level=db_cluster.skill_level,
                    knowledge_base_id=db_cluster.knowledge_base_id,
                    doc_count=len(doc_ids)
                )

            # Load users
            db_users = db.query(DBUser).all()
            for db_user in db_users:
                users[db_user.username] = db_user.hashed_password

        total_docs = sum(len(d) for d in documents.values())
        total_clusters = sum(len(c) for c in clusters.values())
        logger.info(f"Loaded from database: {total_docs} documents in {len(documents)} KBs, {total_clusters} clusters, {len(users)} users")

    except Exception as e:
        logger.warning(f"Database load failed: {e}. Starting with empty state.")

    return documents, metadata, clusters, users
