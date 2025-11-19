"""
Add these Pydantic models to your models.py file for API validation.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class KnowledgeBaseCreate(BaseModel):
    """Request to create a new knowledge base."""
    name: str = Field(..., min_length=1, max_length=255, description="Name of the knowledge base")
    description: Optional[str] = Field(None, description="Description of the knowledge base")
    is_default: bool = Field(False, description="Set as default knowledge base")


class KnowledgeBaseUpdate(BaseModel):
    """Request to update a knowledge base."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_default: Optional[bool] = None


class KnowledgeBase(BaseModel):
    """Knowledge base response model."""
    id: str
    name: str
    description: Optional[str]
    owner_username: str
    is_default: bool
    document_count: int
    created_at: datetime
    updated_at: datetime
    last_accessed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class BuildSuggestion(BaseModel):
    """Build suggestion response model."""
    id: int
    knowledge_base_id: str
    title: str
    description: str
    feasibility: str  # high, medium, low
    effort_estimate: Optional[str]
    required_skills: Optional[List[str]]
    missing_knowledge: Optional[List[str]]
    relevant_clusters: Optional[List[int]]
    starter_steps: Optional[List[str]]
    file_structure: Optional[str]
    knowledge_coverage: Optional[str]  # high, medium, low
    created_at: datetime
    is_completed: bool
    completed_at: Optional[datetime]
    notes: Optional[str]
    
    class Config:
        from_attributes = True


class BuildSuggestionUpdate(BaseModel):
    """Request to update a build suggestion (mark complete, add notes)."""
    is_completed: Optional[bool] = None
    notes: Optional[str] = None


class BuildSuggestionGenerate(BaseModel):
    """Request to generate new build suggestions."""
    knowledge_base_id: str
    max_suggestions: int = Field(5, ge=1, le=10, description="Number of suggestions to generate")
    
    
class KnowledgeBaseList(BaseModel):
    """List of knowledge bases."""
    knowledge_bases: List[KnowledgeBase]
    total: int
    
    
class BuildSuggestionList(BaseModel):
    """List of build suggestions."""
    suggestions: List[BuildSuggestion]
    total: int


# Update your existing DocumentMetadata model to include knowledge_base_id
"""
Add to existing DocumentMetadata class:
    knowledge_base_id: str = Field(..., description="Knowledge base ID this document belongs to")
"""
