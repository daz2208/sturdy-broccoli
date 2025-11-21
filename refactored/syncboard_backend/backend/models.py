"""Data models and schemas for SyncBoard 3.0 Knowledge Bank."""

from pydantic import BaseModel, Field, HttpUrl, field_validator, ConfigDict
from typing import List, Optional
from datetime import datetime

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


class BatchFileUpload(BaseModel):
    """Schema for uploading multiple files in one request."""
    files: List[BatchFileItem] = Field(..., min_length=1, max_length=20, description="List of files to upload (max 20)")


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
