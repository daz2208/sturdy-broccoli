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

    # YouTube-specific metadata (Improvement #3)
    video_title = Column(String(512), nullable=True)  # AI-extracted title
    video_creator = Column(String(255), nullable=True)  # Channel/creator name
    video_type = Column(String(50), nullable=True)  # tutorial, talk, demo, discussion, course, review
    target_audience = Column(String(255), nullable=True)  # e.g., "Python beginners", "DevOps engineers"
    key_takeaways = Column(JSON, nullable=True)  # List of main points
    estimated_watch_time = Column(String(50), nullable=True)  # e.g., "15 minutes", "1 hour"

    # Timestamps
    ingested_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Processing status for hierarchical summarization (Phase 9)
    chunking_status = Column(String(50), default='pending', nullable=False)  # pending, processing, completed, failed
    summary_status = Column(String(50), default='pending', nullable=False)  # pending, processing, completed, failed
    chunk_count = Column(Integer, default=0, nullable=False)

    # Phase 10: Document tagging and project association
    document_tags = Column(JSON, nullable=True)  # ['project-postmortem', 'success-story', 'market-research', 'code-example']
    related_project_id = Column(Integer, ForeignKey("project_attempts.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relationships
    owner_user = relationship("DBUser", back_populates="documents")
    related_project = relationship("DBProjectAttempt", backref="related_documents", foreign_keys=[related_project_id])
    cluster = relationship("DBCluster", back_populates="documents")
    concepts = relationship("DBConcept", back_populates="document", cascade="all, delete-orphan")
    knowledge_base = relationship("DBKnowledgeBase", back_populates="documents")
    # Phase 9: Hierarchical summarization relationships
    chunks = relationship("DBDocumentChunk", back_populates="document", cascade="all, delete-orphan")
    summaries = relationship("DBDocumentSummary", back_populates="document", cascade="all, delete-orphan")
    build_ideas = relationship("DBBuildIdeaSeed", back_populates="document", cascade="all, delete-orphan")

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
    # Phase 9: Hierarchical summarization relationships
    document_chunks = relationship("DBDocumentChunk", back_populates="knowledge_base", cascade="all, delete-orphan")
    document_summaries = relationship("DBDocumentSummary", back_populates="knowledge_base", cascade="all, delete-orphan")
    build_idea_seeds = relationship("DBBuildIdeaSeed", back_populates="knowledge_base", cascade="all, delete-orphan")

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


# =============================================================================
# Phase 9: Hierarchical Summarization
# =============================================================================

class DBDocumentChunk(Base):
    """Stores chunks of documents with embeddings for semantic search."""
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)  # Order within document
    start_token = Column(Integer, nullable=False)  # Token position in original doc
    end_token = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)  # Vector embedding as JSON array
    summary = Column(Text, nullable=True)  # 100-200 token summary of this chunk
    concepts = Column(JSON, nullable=True)  # Extracted concepts from this chunk
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Enhanced RAG: Parent-child chunking support
    parent_chunk_id = Column(Integer, ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True, index=True)
    chunk_type = Column(String(20), default='child', nullable=False)  # 'parent' or 'child'
    # Note: embedding_vector column is added via pgvector migration (vector type not in SQLAlchemy)

    # Relationships
    document = relationship("DBDocument", back_populates="chunks")
    knowledge_base = relationship("DBKnowledgeBase", back_populates="document_chunks")
    parent_chunk = relationship("DBDocumentChunk", remote_side=[id], backref="child_chunks")

    # Indexes
    __table_args__ = (
        Index('idx_chunks_doc_index', 'document_id', 'chunk_index'),
        Index('idx_chunks_parent', 'parent_chunk_id'),
        Index('idx_chunks_type', 'chunk_type'),
    )

    def __repr__(self):
        return f"<DBDocumentChunk(doc_id={self.document_id}, chunk={self.chunk_index}, type={self.chunk_type})>"


class DBDocumentSummary(Base):
    """Stores hierarchical summaries at different levels (chunk, section, document)."""
    __tablename__ = "document_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    summary_type = Column(String(50), nullable=False, index=True)  # 'chunk', 'section', 'document'
    summary_level = Column(Integer, nullable=False, index=True)  # 1=chunk, 2=section, 3=document
    parent_id = Column(Integer, ForeignKey("document_summaries.id", ondelete="SET NULL"), nullable=True)
    chunk_id = Column(Integer, ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True)  # For chunk summaries
    short_summary = Column(Text, nullable=False)  # 100-200 tokens
    long_summary = Column(Text, nullable=True)  # 500-1000 tokens (optional)
    key_concepts = Column(JSON, nullable=True)  # Key concepts at this level
    tech_stack = Column(JSON, nullable=True)  # Technologies mentioned
    skill_profile = Column(JSON, nullable=True)  # Skill levels required
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    document = relationship("DBDocument", back_populates="summaries")
    knowledge_base = relationship("DBKnowledgeBase", back_populates="document_summaries")
    parent = relationship("DBDocumentSummary", remote_side=[id], backref="children")
    chunk = relationship("DBDocumentChunk", foreign_keys=[chunk_id])

    def __repr__(self):
        return f"<DBDocumentSummary(doc_id={self.document_id}, type='{self.summary_type}', level={self.summary_level})>"


class DBBuildIdeaSeed(Base):
    """Pre-computed build ideas based on individual documents."""
    __tablename__ = "build_idea_seeds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    difficulty = Column(String(50), nullable=False, index=True)  # 'beginner', 'intermediate', 'advanced'
    dependencies = Column(JSON, nullable=True)  # List of required concepts/other docs
    referenced_sections = Column(JSON, nullable=True)  # Which sections support this idea
    feasibility = Column(String(50), nullable=True)  # 'high', 'medium', 'low'
    effort_estimate = Column(String(100), nullable=True)  # "2-3 days", "1 week", etc.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    document = relationship("DBDocument", back_populates="build_ideas")
    knowledge_base = relationship("DBKnowledgeBase", back_populates="build_idea_seeds")

    def __repr__(self):
        return f"<DBBuildIdeaSeed(doc_id={self.document_id}, title='{self.title}', difficulty='{self.difficulty}')>"


# =============================================================================
# Phase 10: SyncBoard 3.0 Enhancements - Goal-Driven Creation Engine
# =============================================================================

class DBProjectGoal(Base):
    """User project goals and constraints for personalized suggestions."""
    __tablename__ = "project_goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)
    goal_type = Column(String(50), nullable=False, index=True)  # 'revenue', 'learning', 'portfolio', 'automation'
    priority = Column(Integer, default=0, nullable=False)  # Higher = more important
    constraints = Column(JSON, nullable=True)  # {time_available, budget, target_market, tech_stack_preference, deployment_preference}
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("DBUser", backref="project_goals")

    # Indexes
    __table_args__ = (
        Index('idx_project_goals_user', 'user_id'),
        Index('idx_project_goals_type', 'goal_type'),
        Index('idx_project_goals_priority', 'user_id', 'priority'),
    )

    def __repr__(self):
        return f"<DBProjectGoal(id={self.id}, user='{self.user_id}', type='{self.goal_type}', priority={self.priority})>"


class DBProjectAttempt(Base):
    """Tracks user's project attempts for learning and pattern recognition."""
    __tablename__ = "project_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)
    suggestion_id = Column(String(255), nullable=True)  # Links to build suggestion that inspired this
    title = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default='planned', index=True)  # 'planned', 'in_progress', 'completed', 'abandoned'

    # Timestamps
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    abandoned_at = Column(DateTime, nullable=True)

    # Project details
    repository_url = Column(String(500), nullable=True)
    demo_url = Column(String(500), nullable=True)
    learnings = Column(Text, nullable=True)  # What went right/wrong
    difficulty_rating = Column(Integer, nullable=True)  # 1-10, actual vs estimated
    time_spent_hours = Column(Integer, nullable=True)
    revenue_generated = Column(Float, nullable=True)  # Decimal for currency
    extra_data = Column(JSON, nullable=True)  # Extra metadata (renamed from 'metadata' which is reserved)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("DBUser", backref="project_attempts")
    generated_code = relationship("DBGeneratedCode", back_populates="project_attempt", cascade="all, delete-orphan")
    market_validations = relationship("DBMarketValidation", back_populates="project_attempt", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_project_attempts_user', 'user_id'),
        Index('idx_project_attempts_status', 'status'),
        Index('idx_project_attempts_user_status', 'user_id', 'status'),
        Index('idx_project_attempts_created', 'created_at'),
    )

    def __repr__(self):
        return f"<DBProjectAttempt(id={self.id}, title='{self.title}', status='{self.status}')>"


class DBGeneratedCode(Base):
    """Stores generated code files for projects."""
    __tablename__ = "generated_code"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)
    project_attempt_id = Column(Integer, ForeignKey("project_attempts.id", ondelete="CASCADE"), nullable=True, index=True)
    generation_type = Column(String(50), nullable=False, index=True)  # 'starter_project', 'component', 'n8n_workflow', 'script'
    language = Column(String(50), nullable=True)  # 'python', 'javascript', 'json', etc
    filename = Column(String(255), nullable=True)
    code_content = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    dependencies = Column(JSON, nullable=True)  # List of required packages/libraries
    setup_instructions = Column(Text, nullable=True)
    prompt_used = Column(Text, nullable=True)  # Original prompt for regeneration
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("DBUser", backref="generated_code")
    project_attempt = relationship("DBProjectAttempt", back_populates="generated_code")

    # Indexes
    __table_args__ = (
        Index('idx_generated_code_user', 'user_id'),
        Index('idx_generated_code_project', 'project_attempt_id'),
        Index('idx_generated_code_type', 'generation_type'),
    )

    def __repr__(self):
        return f"<DBGeneratedCode(id={self.id}, filename='{self.filename}', type='{self.generation_type}')>"


class DBN8nWorkflow(Base):
    """Stores generated n8n workflows."""
    __tablename__ = "n8n_workflows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    workflow_json = Column(JSON, nullable=False)  # Complete n8n workflow
    task_description = Column(Text, nullable=False)  # What it does
    required_integrations = Column(JSON, nullable=True)  # ['gmail', 'slack', 'openai', etc]
    trigger_type = Column(String(100), nullable=True)  # 'webhook', 'schedule', 'manual', etc
    estimated_complexity = Column(String(50), nullable=True)  # 'simple', 'medium', 'complex'
    tested = Column(Boolean, default=False, nullable=False)
    deployed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("DBUser", backref="n8n_workflows")

    # Indexes
    __table_args__ = (
        Index('idx_n8n_workflows_user', 'user_id'),
        Index('idx_n8n_workflows_trigger', 'trigger_type'),
        Index('idx_n8n_workflows_complexity', 'estimated_complexity'),
    )

    def __repr__(self):
        return f"<DBN8nWorkflow(id={self.id}, title='{self.title}', trigger='{self.trigger_type}')>"


class DBMarketValidation(Base):
    """Stores market validation results for project ideas."""
    __tablename__ = "market_validations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_attempt_id = Column(Integer, ForeignKey("project_attempts.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(String(255), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)

    # Validation results
    validation_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    market_size_estimate = Column(String(100), nullable=True)  # 'small', 'medium', 'large', 'niche'
    competition_level = Column(String(100), nullable=True)  # 'low', 'medium', 'high', 'crowded'
    competitors = Column(JSON, nullable=True)  # List of competitor names/urls
    unique_advantage = Column(Text, nullable=True)  # What makes this different
    potential_revenue_estimate = Column(String(100), nullable=True)  # '$0-1k/mo', '$1k-5k/mo', etc
    validation_sources = Column(JSON, nullable=True)  # Where info came from
    recommendation = Column(String(50), nullable=True)  # 'proceed', 'pivot', 'abandon'
    reasoning = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)  # 0.0-1.0

    # Full validation data
    full_analysis = Column(JSON, nullable=True)  # Complete analysis response

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project_attempt = relationship("DBProjectAttempt", back_populates="market_validations")
    user = relationship("DBUser", backref="market_validations")

    # Indexes
    __table_args__ = (
        Index('idx_market_validations_project', 'project_attempt_id'),
        Index('idx_market_validations_user', 'user_id'),
        Index('idx_market_validations_recommendation', 'recommendation'),
    )

    def __repr__(self):
        return f"<DBMarketValidation(id={self.id}, recommendation='{self.recommendation}', confidence={self.confidence_score})>"


# =============================================================================
# Team Collaboration Models
# =============================================================================

class DBTeam(Base):
    """Team/Organization for collaborative knowledge management."""
    __tablename__ = "teams"

    id = Column(String(36), primary_key=True)  # UUID
    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    owner_username = Column(String(50), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)

    # Settings
    is_public = Column(Boolean, default=False, nullable=False)
    allow_member_invites = Column(Boolean, default=False, nullable=False)
    max_members = Column(Integer, default=10, nullable=False)

    # Stats
    member_count = Column(Integer, default=1, nullable=False)
    kb_count = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    owner = relationship("DBUser", foreign_keys=[owner_username], backref="owned_teams")
    members = relationship("DBTeamMember", back_populates="team", cascade="all, delete-orphan")
    invitations = relationship("DBTeamInvitation", back_populates="team", cascade="all, delete-orphan")
    knowledge_bases = relationship("DBTeamKnowledgeBase", back_populates="team", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_teams_owner', 'owner_username'),
    )

    def __repr__(self):
        return f"<DBTeam(id='{self.id}', name='{self.name}', members={self.member_count})>"


class DBTeamMember(Base):
    """Team membership with role-based access control."""
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    username = Column(String(50), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)

    # Role: owner, admin, member, viewer
    role = Column(String(20), default="member", nullable=False)

    # Permissions (can override role defaults)
    can_invite = Column(Boolean, default=False, nullable=False)
    can_edit_docs = Column(Boolean, default=True, nullable=False)
    can_delete_docs = Column(Boolean, default=False, nullable=False)
    can_manage_kb = Column(Boolean, default=False, nullable=False)

    # Timestamps
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_active_at = Column(DateTime, nullable=True)

    # Relationships
    team = relationship("DBTeam", back_populates="members")
    user = relationship("DBUser", backref="team_memberships")

    __table_args__ = (
        Index('idx_team_members_team_role', 'team_id', 'role'),
        Index('idx_team_members_user', 'username'),
    )

    def __repr__(self):
        return f"<DBTeamMember(team_id='{self.team_id}', user='{self.username}', role='{self.role}')>"


class DBTeamInvitation(Base):
    """Pending team invitations."""
    __tablename__ = "team_invitations"

    id = Column(String(36), primary_key=True)  # UUID
    team_id = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    invited_username = Column(String(50), nullable=True)  # If user exists

    # Invitation details
    role = Column(String(20), default="member", nullable=False)
    token = Column(String(64), nullable=False, unique=True, index=True)
    message = Column(Text, nullable=True)

    # Inviter info
    invited_by = Column(String(50), ForeignKey("users.username", ondelete="SET NULL"), nullable=True)

    # Status
    status = Column(String(20), default="pending", nullable=False)  # pending, accepted, declined, expired
    expires_at = Column(DateTime, nullable=False)
    responded_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    team = relationship("DBTeam", back_populates="invitations")
    inviter = relationship("DBUser", backref="sent_invitations")

    __table_args__ = (
        Index('idx_invitations_team_status', 'team_id', 'status'),
        Index('idx_invitations_email', 'email'),
    )

    def __repr__(self):
        return f"<DBTeamInvitation(id='{self.id}', email='{self.email}', status='{self.status}')>"


class DBTeamKnowledgeBase(Base):
    """Association between teams and knowledge bases for shared access."""
    __tablename__ = "team_knowledge_bases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)

    # Access level: read, write, admin
    access_level = Column(String(20), default="read", nullable=False)

    # Who shared it
    shared_by = Column(String(50), ForeignKey("users.username", ondelete="SET NULL"), nullable=True)
    shared_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    team = relationship("DBTeam", back_populates="knowledge_bases")
    knowledge_base = relationship("DBKnowledgeBase", backref="team_shares")
    sharer = relationship("DBUser", backref="shared_kbs")

    __table_args__ = (
        Index('idx_team_kb_team', 'team_id'),
        Index('idx_team_kb_kb', 'knowledge_base_id'),
    )

    def __repr__(self):
        return f"<DBTeamKnowledgeBase(team='{self.team_id}', kb='{self.knowledge_base_id}', access='{self.access_level}')>"


class DBDocumentComment(Base):
    """Comments on documents for team collaboration."""
    __tablename__ = "document_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.doc_id", ondelete="CASCADE"), nullable=False, index=True)
    username = Column(String(50), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)

    # Comment content
    content = Column(Text, nullable=False)

    # Threading
    parent_comment_id = Column(Integer, ForeignKey("document_comments.id", ondelete="CASCADE"), nullable=True)

    # Mentions (comma-separated usernames)
    mentions = Column(Text, nullable=True)

    # Status
    is_resolved = Column(Boolean, default=False, nullable=False)
    resolved_by = Column(String(50), nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    document = relationship("DBDocument", backref="comments")
    author = relationship("DBUser", foreign_keys=[username], backref="comments")
    replies = relationship("DBDocumentComment", backref=backref("parent", remote_side=[id]))

    __table_args__ = (
        Index('idx_comments_document', 'document_id'),
        Index('idx_comments_author', 'username'),
    )

    def __repr__(self):
        return f"<DBDocumentComment(id={self.id}, doc={self.document_id}, author='{self.username}')>"


class DBActivityLog(Base):
    """Activity log for tracking team actions."""
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), nullable=True, index=True)
    knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=True, index=True)
    username = Column(String(50), ForeignKey("users.username", ondelete="SET NULL"), nullable=True, index=True)

    # Activity details
    action = Column(String(50), nullable=False)  # created, updated, deleted, shared, invited, etc.
    resource_type = Column(String(50), nullable=False)  # document, cluster, team, knowledge_base, etc.
    resource_id = Column(String(50), nullable=True)
    resource_name = Column(String(255), nullable=True)

    # Additional context (JSON)
    metadata = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    team = relationship("DBTeam", backref="activity_logs")
    knowledge_base = relationship("DBKnowledgeBase", backref="activity_logs")
    user = relationship("DBUser", backref="activity_logs")

    __table_args__ = (
        Index('idx_activity_team_time', 'team_id', 'created_at'),
        Index('idx_activity_kb_time', 'knowledge_base_id', 'created_at'),
        Index('idx_activity_action', 'action'),
    )

    def __repr__(self):
        return f"<DBActivityLog(id={self.id}, action='{self.action}', resource='{self.resource_type}')>"
