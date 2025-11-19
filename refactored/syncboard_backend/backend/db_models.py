"""
SQLAlchemy database models (Phase 6).

Maps application domain models to PostgreSQL tables.
Separate from Pydantic models (models.py) which handle API validation.
"""

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, JSON, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class DBUser(Base):
    """User account table."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    # Documents are cascade deleted when user is deleted
    documents = relationship("DBDocument", back_populates="owner_user", cascade="all, delete-orphan")
    knowledge_bases = relationship("DBKnowledgeBase", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<DBUser(id={self.id}, username='{self.username}')>"


class DBCluster(Base):
    """Cluster/topic grouping table."""
    __tablename__ = "clusters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    primary_concepts = Column(JSON, nullable=False, default=list)  # List of concept names
    skill_level = Column(String(50), nullable=True)  # beginner, intermediate, advanced
    knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    # CASCADE FIX: Removed delete-orphan to prevent automatic document deletion
    # Documents are managed via foreign key (document.cluster_id), not collection
    documents = relationship("DBDocument", back_populates="cluster")
    knowledge_base = relationship("DBKnowledgeBase", back_populates="clusters")

    # Indexes
    __table_args__ = (
        Index('idx_cluster_skill_level', 'skill_level'),
        Index('idx_cluster_kb', 'knowledge_base_id'),
    )

    def __repr__(self):
        return f"<DBCluster(id={self.id}, name='{self.name}', docs={len(self.documents)})>"


class DBDocument(Base):
    """Document metadata table."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(Integer, unique=True, nullable=False, index=True)  # Vector store ID
    owner_username = Column(String(50), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)
    cluster_id = Column(Integer, ForeignKey("clusters.id", ondelete="SET NULL"), nullable=True, index=True)
    knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=True, index=True)

    # Source information
    source_type = Column(String(50), nullable=False, index=True)  # text, url, file, image
    source_url = Column(String(2048), nullable=True)
    filename = Column(String(512), nullable=True)
    image_path = Column(String(1024), nullable=True)

    # Content metadata
    content_length = Column(Integer, nullable=True)
    skill_level = Column(String(50), nullable=True, index=True)

    # Timestamps
    ingested_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    owner_user = relationship("DBUser", back_populates="documents")
    cluster = relationship("DBCluster", back_populates="documents")
    concepts = relationship("DBConcept", back_populates="document", cascade="all, delete-orphan")
    knowledge_base = relationship("DBKnowledgeBase", back_populates="documents")

    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_doc_owner_cluster', 'owner_username', 'cluster_id'),
        Index('idx_doc_source_skill', 'source_type', 'skill_level'),
        Index('idx_doc_ingested', 'ingested_at'),
        Index('idx_doc_kb', 'knowledge_base_id'),
    )

    def __repr__(self):
        return f"<DBDocument(doc_id={self.doc_id}, owner='{self.owner_username}', cluster={self.cluster_id})>"


class DBConcept(Base):
    """Extracted concepts/tags from documents."""
    __tablename__ = "concepts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)

    name = Column(String(255), nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)  # language, framework, concept, etc.
    confidence = Column(Float, nullable=False)  # 0.0 - 1.0

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    document = relationship("DBDocument", back_populates="concepts")

    # Indexes for search
    __table_args__ = (
        Index('idx_concept_name_category', 'name', 'category'),
        Index('idx_concept_confidence', 'confidence'),
    )

    def __repr__(self):
        return f"<DBConcept(name='{self.name}', category='{self.category}', conf={self.confidence:.2f})>"


class DBVectorDocument(Base):
    """
    Stores actual document content and vector data.
    Separate table for performance (large text fields).
    """
    __tablename__ = "vector_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(Integer, unique=True, nullable=False, index=True)  # Links to DBDocument.doc_id
    content = Column(Text, nullable=False)  # Full document text

    # TF-IDF vector representation (stored as JSON for now)
    # In production, consider pgvector extension for native vector search
    tfidf_vector = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<DBVectorDocument(doc_id={self.doc_id}, content_len={len(self.content) if self.content else 0})>"


# =============================================================================
# Phase 7.3-7.5: Advanced Features
# =============================================================================

class DBTag(Base):
    """User-defined tags for documents (Phase 7.3)."""
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, index=True)
    owner_username = Column(String(50), ForeignKey("users.username"), nullable=False, index=True)
    color = Column(String(7), nullable=True)  # Hex color code (e.g., "#00d4ff")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Unique constraint: one tag name per user
    __table_args__ = (
        Index('idx_tag_owner_name', 'owner_username', 'name', unique=True),
    )

    def __repr__(self):
        return f"<DBTag(id={self.id}, name='{self.name}', owner='{self.owner_username}')>"


class DBDocumentTag(Base):
    """Many-to-many relationship between documents and tags (Phase 7.3)."""
    __tablename__ = "document_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Unique constraint: each document-tag pair only once
    __table_args__ = (
        Index('idx_doctag_unique', 'document_id', 'tag_id', unique=True),
    )

    def __repr__(self):
        return f"<DBDocumentTag(doc={self.document_id}, tag={self.tag_id})>"


class DBSavedSearch(Base):
    """Saved search queries for quick access (Phase 7.4)."""
    __tablename__ = "saved_searches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_username = Column(String(50), ForeignKey("users.username"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    query = Column(String(1000), nullable=False)

    # Search filters (stored as JSON)
    filters = Column(JSON, nullable=True)  # {cluster_id, source_type, skill_level, date_from, date_to}

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    use_count = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index('idx_saved_search_owner', 'owner_username'),
    )

    def __repr__(self):
        return f"<DBSavedSearch(id={self.id}, name='{self.name}', owner='{self.owner_username}')>"


class DBDocumentRelationship(Base):
    """Links between related documents (Phase 7.5)."""
    __tablename__ = "document_relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_doc_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    target_doc_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)

    relationship_type = Column(String(50), nullable=False, default="related")
    # Types: "related", "prerequisite", "followup", "alternative", "supersedes"

    strength = Column(Float, nullable=True)  # 0.0-1.0, for AI-discovered relationships
    created_by_username = Column(String(50), nullable=True)  # Null if AI-generated
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Prevent duplicate relationships
    __table_args__ = (
        Index('idx_doc_rel_unique', 'source_doc_id', 'target_doc_id', 'relationship_type', unique=True),
    )

    def __repr__(self):
        return f"<DBDocumentRelationship(source={self.source_doc_id}, target={self.target_doc_id}, type='{self.relationship_type}')>"


# =============================================================================
# Phase 5: Cloud Integrations
# =============================================================================

class DBIntegrationToken(Base):
    """Stores encrypted OAuth tokens for cloud service integrations (Phase 5)."""
    __tablename__ = "integration_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)
    service = Column(String(50), nullable=False, index=True)  # 'github', 'google', 'dropbox', 'notion'

    # Encrypted tokens
    access_token = Column(Text, nullable=False)  # Encrypted with Fernet
    refresh_token = Column(Text, nullable=True)  # Encrypted (if provider supports refresh)

    # Token metadata
    token_type = Column(String(50), default="Bearer", nullable=False)
    expires_at = Column(DateTime, nullable=True, index=True)  # For automatic refresh
    scope = Column(Text, nullable=True)  # Granted OAuth scopes

    # Provider user information
    provider_user_id = Column(String(255), nullable=True)
    provider_user_email = Column(String(255), nullable=True)
    provider_user_name = Column(String(255), nullable=True)

    # Timestamps
    connected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Constraints: one connection per service per user
    __table_args__ = (
        Index('idx_integration_token_user_service', 'user_id', 'service', unique=True),
        Index('idx_integration_token_expires', 'expires_at'),
    )

    def __repr__(self):
        return f"<DBIntegrationToken(user='{self.user_id}', service='{self.service}')>"


class DBIntegrationImport(Base):
    """Tracks cloud service import jobs and provides audit history (Phase 5)."""
    __tablename__ = "integration_imports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)
    service = Column(String(50), nullable=False, index=True)  # 'github', 'google', 'dropbox', 'notion'

    # Job tracking
    job_id = Column(String(255), unique=True, nullable=False, index=True)  # Celery task ID
    status = Column(String(50), nullable=False, default="pending", index=True)  # pending, processing, completed, failed

    # Import statistics
    file_count = Column(Integer, nullable=True)
    files_processed = Column(Integer, default=0, nullable=False)
    files_failed = Column(Integer, default=0, nullable=False)
    total_size_bytes = Column(Integer, nullable=True)

    # Service-specific metadata (e.g., repo name, folder path)
    import_metadata = Column(JSON, nullable=True)

    # Error information
    error_message = Column(Text, nullable=True)

    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('idx_integration_import_user_service', 'user_id', 'service'),
        Index('idx_integration_import_status', 'status'),
        Index('idx_integration_import_created', 'created_at'),
    )

    def __repr__(self):
        return f"<DBIntegrationImport(job='{self.job_id}', service='{self.service}', status='{self.status}')>"


# =============================================================================
# Phase 8: Multi-Knowledge Base Support
# =============================================================================

class DBKnowledgeBase(Base):
    """Knowledge base for organizing documents into separate contexts."""
    __tablename__ = "knowledge_bases"

    id = Column(String(36), primary_key=True)  # UUID
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    owner_username = Column(String(50), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)
    is_default = Column(Boolean, default=False, nullable=False, index=True)

    # Metadata
    document_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_accessed_at = Column(DateTime, nullable=True)

    # Relationships
    owner = relationship("DBUser", back_populates="knowledge_bases")
    documents = relationship("DBDocument", back_populates="knowledge_base", cascade="all, delete-orphan")
    clusters = relationship("DBCluster", back_populates="knowledge_base", cascade="all, delete-orphan")
    build_suggestions = relationship("DBBuildSuggestion", back_populates="knowledge_base", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_kb_owner_name', 'owner_username', 'name'),
    )

    def __repr__(self):
        return f"<DBKnowledgeBase(id='{self.id}', name='{self.name}', docs={self.document_count})>"


class DBBuildSuggestion(Base):
    """Saved build suggestions generated from knowledge base analysis."""
    __tablename__ = "build_suggestions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)

    # Core suggestion data
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    feasibility = Column(String(20), nullable=False)  # high, medium, low
    effort_estimate = Column(String(100), nullable=True)

    # JSON fields for complex data
    required_skills = Column(JSON, nullable=True)  # ["skill1", "skill2"]
    missing_knowledge = Column(JSON, nullable=True)  # ["gap1", "gap2"]
    relevant_clusters = Column(JSON, nullable=True)  # [0, 1, 2]
    starter_steps = Column(JSON, nullable=True)  # ["step1", "step2"]
    file_structure = Column(Text, nullable=True)
    knowledge_coverage = Column(String(20), nullable=True)  # high, medium, low

    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    is_completed = Column(Boolean, default=False, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)  # User notes about the project

    # Relationships
    knowledge_base = relationship("DBKnowledgeBase", back_populates="build_suggestions")

    # Indexes
    __table_args__ = (
        Index('idx_suggestion_kb_created', 'knowledge_base_id', 'created_at'),
        Index('idx_suggestion_feasibility', 'feasibility'),
    )

    def __repr__(self):
        return f"<DBBuildSuggestion(id={self.id}, title='{self.title}', feasibility='{self.feasibility}')>"
