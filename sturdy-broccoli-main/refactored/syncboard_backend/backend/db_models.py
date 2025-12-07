"""
SQLAlchemy database models (Phase 6).

Maps application domain models to PostgreSQL tables.
Separate from Pydantic models (models.py) which handle API validation.
"""

from sqlalchemy import Column, Integer, BigInteger, String, Float, Text, DateTime, JSON, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship, declarative_base, backref
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

    # Settings (JSON for industry config, preferences, etc.)
    settings = Column(JSON, nullable=True, default=dict)

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
    """Pre-computed build ideas based on individual documents or combined KB knowledge."""
    __tablename__ = "build_idea_seeds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)  # NULL for combined ideas
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


class DBSavedIdea(Base):
    """User-saved build ideas for later reference."""
    __tablename__ = "saved_ideas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)
    idea_seed_id = Column(Integer, ForeignKey("build_idea_seeds.id", ondelete="CASCADE"), nullable=True)
    # For ideas from /what_can_i_build that aren't seed-based
    custom_title = Column(String(500), nullable=True)
    custom_description = Column(Text, nullable=True)
    custom_data = Column(JSON, nullable=True)  # Store full suggestion data
    notes = Column(Text, nullable=True)  # User notes
    status = Column(String(50), default="saved", nullable=False)  # saved, started, completed
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("DBUser", backref="saved_ideas")
    idea_seed = relationship("DBBuildIdeaSeed", backref="saved_by_users")

    __table_args__ = (
        Index('ix_saved_ideas_user_status', 'user_id', 'status'),
    )

    def __repr__(self):
        title = self.custom_title or (self.idea_seed.title if self.idea_seed else "Unknown")
        return f"<DBSavedIdea(user='{self.user_id}', title='{title}')>"


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


class DBDocumentComment(Base):
    """Comments on documents for team collaboration."""
    __tablename__ = "document_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
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
    """Activity log for tracking knowledge base actions."""
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=True, index=True)
    username = Column(String(50), ForeignKey("users.username", ondelete="SET NULL"), nullable=True, index=True)

    # Activity details
    action = Column(String(50), nullable=False)  # created, updated, deleted, shared, etc.
    resource_type = Column(String(50), nullable=False)  # document, cluster, knowledge_base, etc.
    resource_id = Column(String(50), nullable=True)
    resource_name = Column(String(255), nullable=True)

    # Additional context (JSON)
    details = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    knowledge_base = relationship("DBKnowledgeBase", backref="activity_logs")
    user = relationship("DBUser", backref="activity_logs")

    __table_args__ = (
        Index('idx_activity_kb_time', 'knowledge_base_id', 'created_at'),
        Index('idx_activity_action', 'action'),
    )

    def __repr__(self):
        return f"<DBActivityLog(id={self.id}, action='{self.action}', resource='{self.resource_type}')>"


# =============================================================================
# API Rate Tiers & Usage Tracking Models
# =============================================================================

class DBUserSubscription(Base):
    """User subscription/tier for rate limiting and monetization."""
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Plan: free, starter, pro, enterprise
    plan = Column(String(20), default="free", nullable=False)

    # Status: active, cancelled, expired, trial
    status = Column(String(20), default="active", nullable=False)

    # Billing
    stripe_customer_id = Column(String(100), nullable=True)
    stripe_subscription_id = Column(String(100), nullable=True)
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)

    # Trial
    trial_ends_at = Column(DateTime, nullable=True)

    # Timestamps (match migration schema - both migrations)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("DBUser", backref="subscription")
    usage = relationship("DBUsageRecord", back_populates="subscription", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_subscription_plan', 'plan'),
        Index('idx_subscription_status', 'status'),
    )

    def __repr__(self):
        return f"<DBUserSubscription(user='{self.username}', plan='{self.plan}', status='{self.status}')>"


class DBUsageRecord(Base):
    """Track API usage for billing and rate limiting."""
    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subscription_id = Column(Integer, ForeignKey("user_subscriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    username = Column(String(50), nullable=False, index=True)

    # Usage period (monthly)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    # Counters
    api_calls = Column(Integer, default=0, nullable=False)
    documents_uploaded = Column(Integer, default=0, nullable=False)
    ai_requests = Column(Integer, default=0, nullable=False)
    storage_bytes = Column(BigInteger, default=0, nullable=False)
    search_queries = Column(Integer, default=0, nullable=False)
    build_suggestions = Column(Integer, default=0, nullable=False)

    # Timestamps
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    subscription = relationship("DBUserSubscription", back_populates="usage")

    __table_args__ = (
        Index('idx_usage_subscription_period', 'subscription_id', 'period_start'),
        Index('idx_usage_user_period', 'username', 'period_start'),
    )

    def __repr__(self):
        return f"<DBUsageRecord(user='{self.username}', calls={self.api_calls}, period='{self.period_start}')>"


class DBRateLimitOverride(Base):
    """Custom rate limit overrides for specific users."""
    __tablename__ = "rate_limit_overrides"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Override limits (null means use plan defaults)
    max_api_calls_per_minute = Column(Integer, nullable=True)
    max_api_calls_per_day = Column(Integer, nullable=True)
    max_documents_per_month = Column(Integer, nullable=True)
    max_ai_requests_per_day = Column(Integer, nullable=True)
    max_storage_bytes = Column(BigInteger, nullable=True)

    # Metadata
    reason = Column(Text, nullable=True)
    granted_by = Column(String(50), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("DBUser", backref="rate_limit_override")

    def __repr__(self):
        return f"<DBRateLimitOverride(user='{self.username}')>"


# =============================================================================
# Agentic Learning System (Phase: Self-Learning AI)
# =============================================================================

class DBAIDecision(Base):
    """
    Track every AI decision with confidence scores for self-learning.

    This table captures all AI-made decisions (concept extraction, clustering,
    classification, etc.) along with confidence scores. Used to:
    - Identify low-confidence decisions that need validation
    - Learn from user corrections
    - Track accuracy over time
    - Enable A/B testing of AI models
    """
    __tablename__ = "ai_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Decision context
    decision_type = Column(String(50), nullable=False, index=True)  # concept_extraction, clustering, classification, etc.
    username = Column(String(50), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=True, index=True)

    # Related entities
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    cluster_id = Column(Integer, ForeignKey("clusters.id", ondelete="SET NULL"), nullable=True, index=True)

    # Decision details
    input_data = Column(JSON, nullable=False)  # What was analyzed (content sample, concepts, etc.)
    output_data = Column(JSON, nullable=False)  # What was decided (extracted concepts, cluster assignment, etc.)
    confidence_score = Column(Float, nullable=False, index=True)  # 0.0 to 1.0

    # Model metadata
    model_name = Column(String(100), nullable=True)  # gpt-4, gpt-3.5-turbo, custom-v1, etc.
    model_version = Column(String(50), nullable=True)

    # Validation status
    validated = Column(Boolean, default=False, nullable=False, index=True)  # Has user reviewed?
    validation_result = Column(String(20), nullable=True)  # accepted, rejected, modified
    validation_timestamp = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("DBUser")
    document = relationship("DBDocument")
    cluster = relationship("DBCluster")
    knowledge_base = relationship("DBKnowledgeBase")

    # Indexes for analytics queries
    __table_args__ = (
        Index('idx_ai_decision_type_confidence', 'decision_type', 'confidence_score'),
        Index('idx_ai_decision_user_type', 'username', 'decision_type'),
        Index('idx_ai_decision_validation', 'validated', 'confidence_score'),
        Index('idx_ai_decision_created', 'created_at'),
    )

    def __repr__(self):
        return f"<DBAIDecision(type='{self.decision_type}', confidence={self.confidence_score:.2f}, validated={self.validated})>"


class DBUserFeedback(Base):
    """
    Track user actions and corrections to learn from mistakes.

    Captures all user corrections, cluster moves, concept edits, and other
    feedback signals. Used to:
    - Learn user preferences and patterns
    - Improve AI decision accuracy
    - Personalize the system to each user
    - Track which AI decisions were wrong
    """
    __tablename__ = "user_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Feedback context
    feedback_type = Column(String(50), nullable=False, index=True)  # cluster_move, concept_edit, document_delete, etc.
    username = Column(String(50), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=True, index=True)

    # Related entities
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    ai_decision_id = Column(Integer, ForeignKey("ai_decisions.id", ondelete="SET NULL"), nullable=True, index=True)

    # Feedback details
    original_value = Column(JSON, nullable=True)  # What the AI decided
    new_value = Column(JSON, nullable=False)  # What the user changed it to
    context = Column(JSON, nullable=True)  # Additional context (document concepts, cluster info, etc.)

    # User reasoning (optional, if we ask)
    user_reasoning = Column(Text, nullable=True)

    # Processing status
    processed = Column(Boolean, default=False, nullable=False, index=True)  # Has learning system incorporated this?
    processed_at = Column(DateTime, nullable=True)

    # Impact tracking
    improvement_score = Column(Float, nullable=True)  # How much this feedback improved accuracy (calculated later)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("DBUser")
    document = relationship("DBDocument")
    ai_decision = relationship("DBAIDecision")
    knowledge_base = relationship("DBKnowledgeBase")

    # Indexes for learning queries
    __table_args__ = (
        Index('idx_feedback_type_user', 'feedback_type', 'username'),
        Index('idx_feedback_processed', 'processed', 'created_at'),
        Index('idx_feedback_user_kb', 'username', 'knowledge_base_id'),
        Index('idx_feedback_document', 'document_id'),
    )

    def __repr__(self):
        return f"<DBUserFeedback(type='{self.feedback_type}', user='{self.username}', processed={self.processed})>"


# =============================================================================
# True Agentic Learning Models - Persistent learned rules and preferences
# =============================================================================

class DBLearnedRule(Base):
    """
    Extracted rules from user corrections - applied deterministically.

    Unlike prompt injection (temporary), these rules are:
    - Persistent: Stored and applied consistently
    - Deterministic: Applied as pre/post processing, not LLM suggestions
    - Scalable: Unlimited rules (vs ~5 examples in prompts)

    Rule types:
    - concept_rename: "Docker container" → "Docker"
    - concept_reject: Never extract "miscellaneous"
    - confidence_threshold: Raise/lower thresholds for certain content types
    - skill_level_override: User prefers different skill categorization
    """
    __tablename__ = "learned_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=True, index=True)

    # Rule definition
    rule_type = Column(String(50), nullable=False, index=True)  # concept_rename, concept_reject, confidence_adjust, etc.
    condition = Column(JSON, nullable=False)  # When to apply: {"content_contains": "docker", "concept_matches": "container*"}
    action = Column(JSON, nullable=False)  # What to do: {"rename_to": "Docker", "reject": true, "adjust_confidence": -0.1}

    # Learning metadata
    source_feedback_ids = Column(JSON, nullable=True)  # Which feedback(s) generated this rule
    confidence = Column(Float, default=0.5, nullable=False)  # How confident are we in this rule
    times_applied = Column(Integer, default=0, nullable=False)  # How many times has this rule been applied
    times_overridden = Column(Integer, default=0, nullable=False)  # How many times user corrected after rule applied

    # Status
    active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("DBUser", backref="learned_rules")
    knowledge_base = relationship("DBKnowledgeBase", backref="learned_rules")

    __table_args__ = (
        Index('idx_learned_rules_active', 'username', 'active', 'rule_type'),
    )

    def __repr__(self):
        return f"<DBLearnedRule(user='{self.username}', type='{self.rule_type}', active={self.active})>"


class DBConceptVocabulary(Base):
    """
    User's preferred concept vocabulary - for normalization.

    When AI extracts "Docker containerization", if user has
    canonical_name="Docker" with variant="Docker containerization",
    we automatically normalize to "Docker".

    This is deterministic post-processing, not prompt-based.
    """
    __tablename__ = "concept_vocabulary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=True, index=True)

    # Canonical form
    canonical_name = Column(String(255), nullable=False, index=True)  # "Docker"
    category = Column(String(100), nullable=True)  # "containerization", "databases", etc.

    # Variants that should map to canonical
    variants = Column(JSON, nullable=False, default=list)  # ["Docker container", "Docker containerization", "docker"]

    # Preferences
    preferred_skill_level = Column(String(50), nullable=True)  # User's opinion of this concept's level
    always_include = Column(Boolean, default=False)  # Always extract if mentioned
    never_include = Column(Boolean, default=False)  # Never extract

    # Usage tracking
    times_seen = Column(Integer, default=0, nullable=False)
    times_kept = Column(Integer, default=0, nullable=False)  # User kept after review
    times_removed = Column(Integer, default=0, nullable=False)  # User removed after extraction

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("DBUser", backref="concept_vocabulary")
    knowledge_base = relationship("DBKnowledgeBase", backref="concept_vocabulary")

    __table_args__ = (
        Index('idx_vocab_user_canonical', 'username', 'canonical_name'),
        Index('idx_vocab_kb', 'knowledge_base_id'),
    )

    def __repr__(self):
        return f"<DBConceptVocabulary(user='{self.username}', canonical='{self.canonical_name}')>"


class DBUserLearningProfile(Base):
    """
    Aggregated learning profile per user - calibrated thresholds and preferences.

    Updated periodically by analyzing all feedback and decisions.
    Applied during every extraction/classification.
    """
    __tablename__ = "user_learning_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Calibrated confidence thresholds (learned from acceptance rates)
    concept_confidence_threshold = Column(Float, default=0.7, nullable=False)  # Default 0.7, adjusted per user
    cluster_confidence_threshold = Column(Float, default=0.6, nullable=False)
    skill_confidence_threshold = Column(Float, default=0.5, nullable=False)

    # Content preferences (learned from corrections)
    prefers_specific_concepts = Column(Boolean, default=True)  # "React hooks" vs "React"
    prefers_fewer_concepts = Column(Boolean, default=False)  # Quality over quantity
    avg_concepts_per_doc = Column(Float, default=5.0)  # Learned average
    min_concept_length = Column(Integer, default=2)  # User's typical minimum

    # Accuracy tracking (for threshold calibration)
    total_decisions = Column(Integer, default=0)
    decisions_accepted = Column(Integer, default=0)
    decisions_rejected = Column(Integer, default=0)
    decisions_modified = Column(Integer, default=0)
    accuracy_rate = Column(Float, default=0.0)  # decisions_accepted / total_decisions

    # Learning state
    rules_generated = Column(Integer, default=0)
    vocabulary_size = Column(Integer, default=0)
    last_learning_run = Column(DateTime, nullable=True)  # When we last processed feedback

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("DBUser", backref="learning_profile", uselist=False)

    def __repr__(self):
        return f"<DBUserLearningProfile(user='{self.username}', accuracy={self.accuracy_rate:.2%})>"


