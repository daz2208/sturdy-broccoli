"""
Pydantic models for cloud service integrations.

Handles OAuth token storage and import job tracking for:
- GitHub
- Google Drive
- Dropbox
- Notion
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


# =============================================================================
# Integration Token Models
# =============================================================================

class IntegrationToken(BaseModel):
    """Represents an OAuth token for a connected cloud service."""
    id: Optional[int] = None
    user_id: str
    service: Literal["github", "google", "dropbox", "notion"]
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

    class Config:
        from_attributes = True


class IntegrationTokenCreate(BaseModel):
    """Request model for creating a new integration token."""
    user_id: str
    service: Literal["github", "google", "dropbox", "notion"]
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
    connections: dict[str, IntegrationConnectionStatus] = Field(
        default_factory=lambda: {
            "github": IntegrationConnectionStatus(connected=False),
            "google": IntegrationConnectionStatus(connected=False),
            "dropbox": IntegrationConnectionStatus(connected=False),
            "notion": IntegrationConnectionStatus(connected=False),
        }
    )


# =============================================================================
# Import Job Models
# =============================================================================

class IntegrationImport(BaseModel):
    """Represents a cloud service import job."""
    id: Optional[int] = None
    user_id: str
    service: Literal["github", "google", "dropbox", "notion"]
    job_id: str  # Celery task ID
    status: Literal["pending", "processing", "completed", "failed"] = "pending"
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

    class Config:
        from_attributes = True


class IntegrationImportCreate(BaseModel):
    """Request model for creating a new import job."""
    user_id: str
    service: Literal["github", "google", "dropbox", "notion"]
    job_id: str
    file_count: Optional[int] = None
    import_metadata: Optional[dict] = None


class IntegrationImportUpdate(BaseModel):
    """Update model for import job progress."""
    status: Optional[Literal["pending", "processing", "completed", "failed"]] = None
    files_processed: Optional[int] = None
    files_failed: Optional[int] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None


# =============================================================================
# GitHub-Specific Models
# =============================================================================

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
    type: Literal["file", "dir"]
    size: int
    sha: Optional[str] = None
    url: Optional[str] = None


class GitHubImportRequest(BaseModel):
    """Request to import files from GitHub."""
    owner: str
    repo: str
    files: list[str]  # List of file paths
    branch: str = "main"


# =============================================================================
# Google Drive-Specific Models
# =============================================================================

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
    file_ids: list[str]


# =============================================================================
# Dropbox-Specific Models
# =============================================================================

class DropboxEntry(BaseModel):
    """Represents a Dropbox file or folder."""
    tag: Literal["file", "folder"]
    name: str
    path_lower: str
    id: str
    size: Optional[int] = None
    server_modified: Optional[datetime] = None


class DropboxImportRequest(BaseModel):
    """Request to import files from Dropbox."""
    paths: list[str]


# =============================================================================
# Notion-Specific Models
# =============================================================================

class NotionPage(BaseModel):
    """Represents a Notion page or database."""
    id: str
    object: Literal["page", "database"]
    created_time: datetime
    last_edited_time: datetime
    title: str
    url: str


class NotionImportRequest(BaseModel):
    """Request to import pages from Notion."""
    page_ids: list[str]
    include_children: bool = False


# =============================================================================
# OAuth State Models
# =============================================================================

class OAuthState(BaseModel):
    """Temporary OAuth state stored in Redis."""
    user_id: str
    service: Literal["github", "google", "dropbox", "notion"]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class OAuthCallbackParams(BaseModel):
    """Query parameters received in OAuth callback."""
    code: str
    state: str
    error: Optional[str] = None
    error_description: Optional[str] = None
