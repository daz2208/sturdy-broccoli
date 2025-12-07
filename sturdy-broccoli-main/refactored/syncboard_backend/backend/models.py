"""Data models and schemas for SyncBoard 3.0 Knowledge Bank."""

from enum import Enum
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator, ConfigDict
from typing import List, Optional
from datetime import datetime

from .config import settings


# =============================================================================
# Enums for validated parameters
# =============================================================================

class ExportFormat(str, Enum):
    """Supported export formats."""
    JSON = "json"
    MARKDOWN = "markdown"


class SkillLevel(str, Enum):
    """Skill level classifications."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    UNKNOWN = "unknown"

# =============================================================================
# REMOVED: Board, BoardCreate (entire board system deleted)
# =============================================================================

# =============================================================================
# Upload Models (board_id removed)
# =============================================================================

class DocumentUpload(BaseModel):
    """Schema for uploading a document via URL."""
    url: HttpUrl


class TextUpload(BaseModel):
    """Schema for uploading raw text content directly. Accepts both "content" and "text" field names."""
    model_config = ConfigDict(populate_by_name=True)  # Accept both "content" and "text"

    content: str = Field(..., alias="text")


class FileBytesUpload(BaseModel):
    """Schema for uploading a file encoded as base64 bytes."""
    filename: str
    content: str


class ImageUpload(BaseModel):
    """Schema for uploading images with optional description."""
    filename: str
    content: str  # base64 encoded
    description: Optional[str] = None


class BatchFileItem(BaseModel):
    """Single file in a batch upload."""
    filename: str
    content: str  # base64 encoded


# Configurable batch upload limit from environment
MAX_BATCH_FILES = settings.max_batch_files


class BatchFileUpload(BaseModel):
    """Schema for uploading multiple files in one request."""
    files: List[BatchFileItem] = Field(
        ...,
        min_length=1,
        max_length=MAX_BATCH_FILES,
        description=f"List of files to upload (max {MAX_BATCH_FILES})"
    )


class BatchUrlUpload(BaseModel):
    """Schema for uploading multiple URLs in one request."""
    urls: List[str] = Field(..., min_length=1, max_length=10, description="List of URLs to upload (max 10)")


# =============================================================================
# Search Models
# =============================================================================

class SearchRequest(BaseModel):
    """Schema for search queries."""
    query: str
    top_k: Optional[int] = 5


class SearchResult(BaseModel):
    """Schema for returning search results from the knowledge base."""
    document_id: int
    similarity: float
    snippet: str


# =============================================================================
# Authentication Models
# =============================================================================

class User(BaseModel):
    """Public representation of a user."""
    username: str


class UserCreate(BaseModel):
    """Schema for creating a new user."""
    username: str
    password: str

    @field_validator('username')
    @classmethod
    def username_valid(cls, v):
        """Validate username meets minimum requirements."""
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        if len(v) > 50:
            raise ValueError('Username must be less than 50 characters')
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v

    @field_validator('password')
    @classmethod
    def password_valid(cls, v):
        """Validate password meets security requirements."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if len(v) > 72:
            raise ValueError('Password must be less than 72 characters (bcrypt limitation)')
        return v


class UserLogin(BaseModel):
    """Schema for user login."""
    username: str
    password: str


class Token(BaseModel):
    """Representation of an authentication token returned after login."""
    access_token: str
    token_type: str = "bearer"


# =============================================================================
# AI Generation Models
# =============================================================================

class GenerationRequest(BaseModel):
    """Schema for AI content generation requests."""
    prompt: str
    model: Optional[str] = "gpt-5-mini"
    use_chunks: Optional[bool] = True  # Use chunk-based RAG if available


class CitationInfo(BaseModel):
    """Structured citation information."""
    doc_id: int
    chunk_id: Optional[int] = None
    filename: Optional[str] = None
    source_url: Optional[str] = None
    source_type: str
    relevance: float
    snippet: str  # Preview of the cited content


class GenerationResponse(BaseModel):
    """Response from AI generation with structured citations."""
    response: str
    citations: Optional[List[CitationInfo]] = None
    chunks_used: Optional[int] = None
    documents_used: Optional[int] = None
    model: Optional[str] = None


class BuildSuggestionRequest(BaseModel):
    """Schema for build suggestion requests."""
    max_suggestions: Optional[int] = 5
    enable_quality_filter: Optional[bool] = True  # Filter out low-coverage suggestions


# =============================================================================
# NEW: Concept Extraction & Clustering Models
# =============================================================================

class Concept(BaseModel):
    """Extracted concept/topic from content."""
    name: str
    category: str  # "technology", "skill", "tool", "language", "framework", "concept", "domain"
    confidence: float  # 0.0 to 1.0


class DocumentMetadata(BaseModel):
    """Metadata for ingested document."""
    doc_id: Optional[int] = None  # Set after document creation
    owner: Optional[str] = None  # Set by repository/service
    source_type: str  # "youtube", "pdf", "text", "url", "audio", "image"
    source_url: Optional[str] = None
    filename: Optional[str] = None
    concepts: List[Concept] = []
    skill_level: str  # "beginner", "intermediate", "advanced", "unknown"
    cluster_id: Optional[int] = None
    knowledge_base_id: Optional[str] = None  # UUID of knowledge base
    ingested_at: str  # ISO timestamp
    content_length: Optional[int] = None  # Set after calculating content length
    image_path: Optional[str] = None  # For images
    source_zip_filename: Optional[str] = None  # Parent ZIP filename if extracted from archive


class Cluster(BaseModel):
    """Group of related documents."""
    id: int
    name: str  # e.g., "Docker & Containerization"
    primary_concepts: List[str]
    doc_ids: List[int]
    skill_level: str
    knowledge_base_id: Optional[str] = None  # UUID of knowledge base
    doc_count: Optional[int] = None  # Computed from len(doc_ids) if not provided

    def __init__(self, **data):
        super().__init__(**data)
        # Auto-compute doc_count from doc_ids if not provided
        if self.doc_count is None:
            self.doc_count = len(self.doc_ids)


class ClusterUpdate(BaseModel):
    """Schema for updating cluster information with validated fields."""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="New cluster name")
    skill_level: Optional[SkillLevel] = Field(None, description="Skill level classification")

    @field_validator('name')
    @classmethod
    def sanitize_name(cls, v):
        """Sanitize cluster name if provided."""
        if v is not None:
            # Basic sanitization - strip whitespace
            v = v.strip()
            if not v:
                raise ValueError("Cluster name cannot be empty")
        return v


class BuildSuggestion(BaseModel):
    """AI-generated project suggestion with comprehensive details."""
    title: str
    description: str
    feasibility: str  # "high", "medium", "low"
    effort_estimate: str  # "1 day", "1 week", etc.
    complexity_level: Optional[str] = "intermediate"  # "beginner", "intermediate", "advanced"
    required_skills: List[str]
    missing_knowledge: List[str]
    relevant_clusters: List[int]
    starter_steps: List[str]
    file_structure: Optional[str] = None
    starter_code: Optional[str] = None  # Working code snippet to get started
    learning_path: Optional[List[str]] = None  # Step-by-step learning journey
    recommended_resources: Optional[List[str]] = None  # Tutorial links, docs, etc.
    expected_outcomes: Optional[List[str]] = None  # What they'll achieve
    troubleshooting_tips: Optional[List[str]] = None  # Common issues and fixes
    knowledge_coverage: Optional[str] = "medium"  # "high", "medium", "low"


# =============================================================================
# Advanced Features Models (Phases 7.2-7.5)
# =============================================================================

class TagCreate(BaseModel):
    """Schema for creating a new tag."""
    name: str
    color: Optional[str] = None


class SavedSearchCreate(BaseModel):
    """Schema for creating a saved search."""
    name: str
    query: str
    filters: Optional[dict] = None


class RelationshipCreate(BaseModel):
    """Schema for creating a document relationship."""
    target_doc_id: int
    relationship_type: str = "related"
    strength: Optional[float] = None


# =============================================================================
# Cloud Integration Models (Phase 5)
# =============================================================================

class IntegrationToken(BaseModel):
    """Represents an OAuth token for a connected cloud service."""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    user_id: str
    service: str  # "github", "google", "dropbox", "notion"
    access_token: str  # Encrypted
    refresh_token: Optional[str] = None  # Encrypted
    token_type: str = "Bearer"
    expires_at: Optional[datetime] = None
    scope: Optional[str] = None
    provider_user_id: Optional[str] = None
    provider_user_email: Optional[str] = None
    provider_user_name: Optional[str] = None
    connected_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class IntegrationTokenCreate(BaseModel):
    """Request model for creating a new integration token."""
    user_id: str
    service: str
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_at: Optional[datetime] = None
    scope: Optional[str] = None
    provider_user_id: Optional[str] = None
    provider_user_email: Optional[str] = None
    provider_user_name: Optional[str] = None


class IntegrationConnectionStatus(BaseModel):
    """Status of a single service connection."""
    connected: bool
    user: Optional[str] = None  # Provider username
    email: Optional[str] = None
    connected_at: Optional[datetime] = None
    last_sync: Optional[datetime] = None


class IntegrationsStatus(BaseModel):
    """Overall status of all integrations for a user."""
    connections: dict = Field(
        default_factory=lambda: {
            "github": IntegrationConnectionStatus(connected=False),
            "google": IntegrationConnectionStatus(connected=False),
            "dropbox": IntegrationConnectionStatus(connected=False),
            "notion": IntegrationConnectionStatus(connected=False),
        }
    )


class IntegrationImport(BaseModel):
    """Represents a cloud service import job."""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    user_id: str
    service: str
    job_id: str  # Celery task ID
    status: str = "pending"  # "pending", "processing", "completed", "failed"
    file_count: Optional[int] = None
    files_processed: int = 0
    files_failed: int = 0
    total_size_bytes: Optional[int] = None
    import_metadata: Optional[dict] = None  # Service-specific data
    error_message: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class IntegrationImportCreate(BaseModel):
    """Request model for creating a new import job."""
    user_id: str
    service: str
    job_id: str
    file_count: Optional[int] = None
    import_metadata: Optional[dict] = None


class IntegrationImportUpdate(BaseModel):
    """Update model for import job progress."""
    status: Optional[str] = None
    files_processed: Optional[int] = None
    files_failed: Optional[int] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None


class GitHubRepository(BaseModel):
    """Represents a GitHub repository."""
    id: int
    name: str
    full_name: str
    description: Optional[str] = None
    private: bool
    url: str
    default_branch: str = "main"
    size: int
    language: Optional[str] = None
    updated_at: datetime


class GitHubFile(BaseModel):
    """Represents a file in a GitHub repository."""
    name: str
    path: str
    type: str  # "file" or "dir"
    size: int
    sha: Optional[str] = None
    url: Optional[str] = None


class GitHubImportRequest(BaseModel):
    """Request to import files from GitHub."""
    owner: str
    repo: str
    files: List[str]  # List of file paths
    branch: str = "main"


class GoogleDriveFile(BaseModel):
    """Represents a Google Drive file or folder."""
    id: str
    name: str
    mimeType: str
    size: Optional[int] = None
    modifiedTime: datetime
    iconLink: Optional[str] = None
    webViewLink: Optional[str] = None


class GoogleDriveImportRequest(BaseModel):
    """Request to import files from Google Drive."""
    file_ids: List[str]


class DropboxEntry(BaseModel):
    """Represents a Dropbox file or folder."""
    tag: str  # "file" or "folder"
    name: str
    path_lower: str
    id: str
    size: Optional[int] = None
    server_modified: Optional[datetime] = None


class DropboxImportRequest(BaseModel):
    """Request to import files from Dropbox."""
    paths: List[str]


class NotionPage(BaseModel):
    """Represents a Notion page or database."""
    id: str
    object: str  # "page" or "database"
    created_time: datetime
    last_edited_time: datetime
    title: str
    url: str


class NotionImportRequest(BaseModel):
    """Request to import pages from Notion."""
    page_ids: List[str]
    include_children: bool = False


class OAuthState(BaseModel):
    """Temporary OAuth state stored in Redis."""
    user_id: str
    service: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class OAuthCallbackParams(BaseModel):
    """Query parameters received in OAuth callback."""
    code: str
    state: str
    error: Optional[str] = None
    error_description: Optional[str] = None


# =============================================================================
# Knowledge Base Models (Phase 8)
# =============================================================================

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
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str]
    owner_username: str
    is_default: bool
    document_count: int
    created_at: datetime
    updated_at: datetime
    last_accessed_at: Optional[datetime]


class KnowledgeBaseList(BaseModel):
    """List of knowledge bases."""
    knowledge_bases: List[KnowledgeBase]
    total: int


class SavedBuildSuggestion(BaseModel):
    """Saved build suggestion from database."""
    model_config = ConfigDict(from_attributes=True)

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


class BuildSuggestionUpdate(BaseModel):
    """Request to update a build suggestion (mark complete, add notes)."""
    is_completed: Optional[bool] = None
    notes: Optional[str] = None


class BuildSuggestionGenerate(BaseModel):
    """Request to generate new build suggestions."""
    max_suggestions: int = Field(5, ge=1, le=10, description="Number of suggestions to generate")


class BuildSuggestionList(BaseModel):
    """List of build suggestions."""
    suggestions: List[SavedBuildSuggestion]
    total: int


# =============================================================================
# Phase 10: SyncBoard 3.0 Enhancement Models
# =============================================================================

class ProjectGoalCreate(BaseModel):
    """Schema for creating a project goal."""
    goal_type: str = Field(..., description="Type of goal: 'revenue', 'learning', 'portfolio', 'automation'")
    priority: int = Field(0, ge=0, le=100, description="Priority level (higher = more important)")
    constraints: Optional[dict] = Field(None, description="Constraints: time_available, budget, target_market, tech_stack_preference, deployment_preference")

    @field_validator('goal_type')
    @classmethod
    def validate_goal_type(cls, v):
        allowed = ['revenue', 'learning', 'portfolio', 'automation']
        if v not in allowed:
            raise ValueError(f"goal_type must be one of: {', '.join(allowed)}")
        return v


class ProjectGoalUpdate(BaseModel):
    """Schema for updating a project goal."""
    goal_type: Optional[str] = None
    priority: Optional[int] = Field(None, ge=0, le=100)
    constraints: Optional[dict] = None

    @field_validator('goal_type')
    @classmethod
    def validate_goal_type(cls, v):
        if v is None:
            return v
        allowed = ['revenue', 'learning', 'portfolio', 'automation']
        if v not in allowed:
            raise ValueError(f"goal_type must be one of: {', '.join(allowed)}")
        return v


class ProjectGoalResponse(BaseModel):
    """Response model for project goal."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    goal_type: str
    priority: int
    constraints: Optional[dict]
    created_at: datetime
    updated_at: datetime


class ProjectAttemptCreate(BaseModel):
    """Schema for creating a project attempt."""
    suggestion_id: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=255)
    status: str = Field("planned", description="Status: 'planned', 'in_progress', 'completed', 'abandoned'")
    repository_url: Optional[str] = Field(None, max_length=500)
    demo_url: Optional[str] = Field(None, max_length=500)

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        allowed = ['planned', 'in_progress', 'completed', 'abandoned']
        if v not in allowed:
            raise ValueError(f"status must be one of: {', '.join(allowed)}")
        return v


class ProjectAttemptUpdate(BaseModel):
    """Schema for updating a project attempt."""
    status: Optional[str] = None
    repository_url: Optional[str] = None
    demo_url: Optional[str] = None
    learnings: Optional[str] = None
    difficulty_rating: Optional[int] = Field(None, ge=1, le=10)
    time_spent_hours: Optional[int] = Field(None, ge=0)
    revenue_generated: Optional[float] = Field(None, ge=0)

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        if v is None:
            return v
        allowed = ['planned', 'in_progress', 'completed', 'abandoned']
        if v not in allowed:
            raise ValueError(f"status must be one of: {', '.join(allowed)}")
        return v


class ProjectAttemptResponse(BaseModel):
    """Response model for project attempt."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    suggestion_id: Optional[str]
    title: str
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    abandoned_at: Optional[datetime]
    repository_url: Optional[str]
    demo_url: Optional[str]
    learnings: Optional[str]
    difficulty_rating: Optional[int]
    time_spent_hours: Optional[int]
    revenue_generated: Optional[float]
    created_at: datetime
    updated_at: datetime


class ProjectStatsResponse(BaseModel):
    """Response model for project statistics."""
    total_projects: int
    completed: int
    in_progress: int
    abandoned: int
    planned: int
    completion_rate: float
    average_time_hours: float
    total_revenue: float


class N8nGenerationRequest(BaseModel):
    """Schema for n8n workflow generation request."""
    task_description: str = Field(..., min_length=10, max_length=5000, description="Description of what the workflow should do")
    available_integrations: Optional[List[str]] = Field(None, description="List of available integrations: gmail, slack, openai, etc.")


class N8nWorkflowResponse(BaseModel):
    """Response model for n8n workflow."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    title: str
    description: Optional[str]
    workflow_json: dict
    task_description: str
    required_integrations: Optional[List[str]]
    trigger_type: Optional[str]
    estimated_complexity: Optional[str]
    tested: bool
    deployed: bool
    created_at: datetime
    updated_at: datetime


class N8nWorkflowUpdate(BaseModel):
    """Schema for updating n8n workflow."""
    tested: Optional[bool] = None
    deployed: Optional[bool] = None


class GeneratedCodeResponse(BaseModel):
    """Response model for generated code."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    project_attempt_id: Optional[int]
    generation_type: str
    language: Optional[str]
    filename: Optional[str]
    code_content: str
    description: Optional[str]
    dependencies: Optional[List[str]]
    setup_instructions: Optional[str]
    created_at: datetime


class MarketValidationRequest(BaseModel):
    """Schema for market validation request."""
    project_title: str = Field(..., min_length=1, max_length=255)
    project_description: str = Field(..., min_length=10, max_length=5000)
    target_market: str = Field(..., min_length=1, max_length=500)


class MarketValidationResponse(BaseModel):
    """Response model for market validation."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_attempt_id: Optional[int]
    user_id: str
    validation_date: datetime
    market_size_estimate: Optional[str]
    competition_level: Optional[str]
    competitors: Optional[List[str]]
    unique_advantage: Optional[str]
    potential_revenue_estimate: Optional[str]
    validation_sources: Optional[List[str]]
    recommendation: Optional[str]
    reasoning: Optional[str]
    confidence_score: Optional[float]
    full_analysis: Optional[dict]
    created_at: datetime


class GoalDrivenSuggestionsRequest(BaseModel):
    """Schema for goal-driven build suggestions request."""
    max_suggestions: int = Field(5, ge=1, le=10)
    enable_quality_filter: bool = Field(True, description="Filter out low-coverage suggestions")


class GoalDrivenSuggestionsResponse(BaseModel):
    """Response model for goal-driven build suggestions."""
    suggestions: List[dict]
    user_goal: str
    total_documents: int
    total_clusters: int


# =============================================================================
# Saved Ideas Models
# =============================================================================

class SaveIdeaRequest(BaseModel):
    """Request model for saving an idea."""
    idea_seed_id: Optional[int] = Field(None, ge=1, description="ID of pre-computed idea seed")
    title: Optional[str] = Field(None, min_length=1, max_length=500, description="Custom idea title")
    description: Optional[str] = Field(None, min_length=1, max_length=10000, description="Custom idea description")
    suggestion_data: Optional[dict] = Field(None, description="Full suggestion data from /what_can_i_build")
    notes: Optional[str] = Field("", max_length=5000, description="User notes")

    @field_validator('title', 'description')
    @classmethod
    def strip_whitespace(cls, v):
        """Strip leading/trailing whitespace."""
        if v:
            return v.strip()
        return v

    @model_validator(mode='after')
    def validate_idea_source(self):
        """Ensure either idea_seed_id or title is provided."""
        if not self.idea_seed_id and not self.title:
            raise ValueError("Must provide either idea_seed_id or title")

        # If using custom idea, description is required
        if self.title and not self.idea_seed_id:
            if not self.description:
                raise ValueError("Description is required when providing a custom title")

        return self


class UpdateSavedIdeaRequest(BaseModel):
    """Request model for updating a saved idea."""
    status: Optional[str] = Field(None, pattern="^(saved|started|completed)$", description="Idea status")
    notes: Optional[str] = Field(None, max_length=5000, description="User notes")

    @model_validator(mode='after')
    def validate_at_least_one_field(self):
        """Ensure at least one field is being updated."""
        if not self.status and not self.notes:
            raise ValueError("Must provide at least one field to update")
        return self


class SavedIdeaResponse(BaseModel):
    """Response model for a saved idea."""
    id: int
    title: str
    description: Optional[str]
    difficulty: Optional[str]
    feasibility: Optional[str]
    effort_estimate: Optional[str]
    notes: str
    status: str
    saved_at: str

    class Config:
        from_attributes = True


class MegaProjectRequest(BaseModel):
    """Request model for creating a mega project."""
    idea_ids: List[int] = Field(..., min_length=2, max_length=10, description="List of saved idea IDs to combine")
    custom_title: Optional[str] = Field(None, max_length=500, description="Custom title for the mega project")

    @field_validator('idea_ids')
    @classmethod
    def validate_unique_ids(cls, v):
        """Ensure all IDs are unique."""
        if len(v) != len(set(v)):
            raise ValueError("idea_ids must contain unique values")
        return v
