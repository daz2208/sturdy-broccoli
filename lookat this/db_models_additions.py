"""
Add these models to your existing db_models.py file.

Place these AFTER your existing models (after DBVectorDocument).
"""

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, JSON, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship
from datetime import datetime

# Add to your existing Base in db_models.py


class DBKnowledgeBase(Base):
    """Knowledge base for organizing documents into separate contexts."""
    __tablename__ = "knowledge_bases"

    id = Column(String(36), primary_key=True)  # UUID
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    owner_username = Column(String(50), ForeignKey("users.username"), nullable=False, index=True)
    is_default = Column(Boolean, default=False, nullable=False, index=True)
    
    # Metadata
    document_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_accessed_at = Column(DateTime, nullable=True)
    
    # Relationships
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


# IMPORTANT: You also need to UPDATE your existing DBDocument and DBCluster models
# Add these lines to their class definitions:

"""
In DBDocument class, add:
    knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_base = relationship("DBKnowledgeBase", back_populates="documents")

In DBCluster class, add:
    knowledge_base_id = Column(String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_base = relationship("DBKnowledgeBase", back_populates="clusters")
"""
