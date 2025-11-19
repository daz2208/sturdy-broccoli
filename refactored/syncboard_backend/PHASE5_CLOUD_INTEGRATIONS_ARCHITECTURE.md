# Phase 5: Cloud Integrations - Architecture & Design

**Version:** 1.0
**Date:** 2025-11-16
**Status:** 🟡 Planning Phase

---

## Executive Summary

This document outlines the complete architecture for integrating cloud storage services with SyncBoard 3.0 Knowledge Bank. The implementation will enable users to seamlessly import documents from:

- **GitHub** - Repositories, files, README, documentation
- **Google Drive** - Documents, PDFs, spreadsheets, presentations
- **Dropbox** - Files and folders
- **Notion** - Pages, databases, wikis

**Design Principles:**
- ✅ Production-ready OAuth 2.0 flows
- ✅ Secure token storage and management
- ✅ Intuitive, beautiful UI
- ✅ Comprehensive error handling
- ✅ Rate limiting and API quota management
- ✅ Background processing via Celery
- ✅ Complete audit logging

---

## Table of Contents

1. [OAuth Architecture](#oauth-architecture)
2. [Backend API Design](#backend-api-design)
3. [Database Schema](#database-schema)
4. [Frontend UI Design](#frontend-ui-design)
5. [Security Considerations](#security-considerations)
6. [Error Handling Strategy](#error-handling-strategy)
7. [Implementation Phases](#implementation-phases)

---

## OAuth Architecture

### General OAuth 2.0 Flow

All integrations follow the standard OAuth 2.0 Authorization Code flow:

```
┌──────────┐                                           ┌─────────────────┐
│          │ 1. Click "Connect" button                 │                 │
│  User    ├──────────────────────────────────────────>│   SyncBoard     │
│          │                                           │   Frontend      │
└──────────┘                                           └────────┬────────┘
                                                                │
                                                                │ 2. GET /integrations/{service}/authorize
                                                                │
                                                                v
                                                       ┌────────────────┐
                                                       │   SyncBoard    │
                                                       │   Backend      │
                                                       └────────┬───────┘
                                                                │
                                                                │ 3. Generate state token
                                                                │ 4. Redirect to provider OAuth
                                                                │
                                                                v
┌──────────┐                                           ┌─────────────────┐
│          │ 5. User authorizes app                    │    Provider     │
│  User    ├──────────────────────────────────────────>│  (GitHub, etc)  │
│          │                                           │                 │
└──────────┘                                           └────────┬────────┘
     ^                                                          │
     │                                                          │ 6. Redirect to callback with code
     │                                                          │
     │                                                          v
     │                                                 ┌────────────────┐
     │                                                 │   SyncBoard    │
     │                                                 │   Callback     │
     │                                                 └────────┬───────┘
     │                                                          │
     │                                                          │ 7. Exchange code for access_token
     │                                                          │ 8. Store encrypted token in DB
     │                                                          │ 9. Redirect to success page
     │                                                          │
     └──────────────────────────────────────────────────────────┘
```

### Service-Specific OAuth Details

#### 1. GitHub OAuth

**Provider:** GitHub OAuth Apps
**Documentation:** https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps

**Required Scopes:**
- `repo` - Access private repositories
- `read:user` - Read user profile info

**OAuth URLs:**
- **Authorize:** `https://github.com/login/oauth/authorize`
- **Token Exchange:** `https://github.com/login/oauth/access_token`
- **User Info:** `https://api.github.com/user`

**Registration Steps:**
1. Go to GitHub Settings → Developer Settings → OAuth Apps
2. Click "New OAuth App"
3. Set callback URL: `https://yourdomain.com/integrations/github/callback`
4. Note Client ID and Client Secret

**Environment Variables:**
```env
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
GITHUB_REDIRECT_URI=http://localhost:8000/integrations/github/callback
```

---

#### 2. Google Drive OAuth

**Provider:** Google Cloud Platform
**Documentation:** https://developers.google.com/identity/protocols/oauth2

**Required Scopes:**
- `https://www.googleapis.com/auth/drive.readonly` - Read files
- `https://www.googleapis.com/auth/userinfo.email` - User email

**OAuth URLs:**
- **Authorize:** `https://accounts.google.com/o/oauth2/v2/auth`
- **Token Exchange:** `https://oauth2.googleapis.com/token`
- **Token Refresh:** `https://oauth2.googleapis.com/token`
- **Revoke:** `https://oauth2.googleapis.com/revoke`

**Registration Steps:**
1. Go to Google Cloud Console → APIs & Services → Credentials
2. Create OAuth 2.0 Client ID (Web application)
3. Add authorized redirect URI: `https://yourdomain.com/integrations/google/callback`
4. Enable Google Drive API
5. Note Client ID and Client Secret

**Environment Variables:**
```env
GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/integrations/google/callback
```

**Token Refresh:**
- Google tokens expire after 1 hour
- Must request `access_type=offline` to get refresh_token
- Implement automatic token refresh before API calls

---

#### 3. Dropbox OAuth

**Provider:** Dropbox App Console
**Documentation:** https://www.dropbox.com/developers/documentation/http/documentation

**Required Scopes:**
- `files.metadata.read` - List files and folders
- `files.content.read` - Download file contents

**OAuth URLs:**
- **Authorize:** `https://www.dropbox.com/oauth2/authorize`
- **Token Exchange:** `https://api.dropboxapi.com/oauth2/token`

**Registration Steps:**
1. Go to Dropbox App Console
2. Create new app with "Scoped access"
3. Set permissions: files.metadata.read, files.content.read
4. Add redirect URI: `https://yourdomain.com/integrations/dropbox/callback`
5. Note App key and App secret

**Environment Variables:**
```env
DROPBOX_APP_KEY=your_app_key
DROPBOX_APP_SECRET=your_app_secret
DROPBOX_REDIRECT_URI=http://localhost:8000/integrations/dropbox/callback
```

---

#### 4. Notion OAuth

**Provider:** Notion Integrations
**Documentation:** https://developers.notion.com/docs/authorization

**Required Capabilities:**
- Read content
- Read user information

**OAuth URLs:**
- **Authorize:** `https://api.notion.com/v1/oauth/authorize`
- **Token Exchange:** `https://api.notion.com/v1/oauth/token`

**Registration Steps:**
1. Go to Notion Developers → My Integrations
2. Create new integration (Public integration for OAuth)
3. Add redirect URI: `https://yourdomain.com/integrations/notion/callback`
4. Note OAuth client ID and OAuth client secret

**Environment Variables:**
```env
NOTION_CLIENT_ID=your_client_id
NOTION_CLIENT_SECRET=your_client_secret
NOTION_REDIRECT_URI=http://localhost:8000/integrations/notion/callback
```

---

## Backend API Design

### Router Structure

Create new router: `backend/routers/integrations.py`

```python
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
import secrets

router = APIRouter(
    prefix="/integrations",
    tags=["integrations"],
    responses={401: {"description": "Unauthorized"}},
)
```

### API Endpoints

#### Generic Endpoints (All Services)

**1. Initiate OAuth Flow**

```http
GET /integrations/{service}/authorize
```

**Parameters:**
- `service`: github | google | dropbox | notion

**Flow:**
1. Generate random `state` token (CSRF protection)
2. Store `state` in Redis with user_id (expires in 10 minutes)
3. Build OAuth authorization URL with:
   - client_id
   - redirect_uri
   - scope
   - state
   - response_type=code
4. Redirect user to provider's OAuth page

**Response:**
```python
RedirectResponse(url=auth_url, status_code=302)
```

---

**2. OAuth Callback Handler**

```http
GET /integrations/{service}/callback?code=...&state=...
```

**Parameters:**
- `service`: github | google | dropbox | notion
- `code`: Authorization code from provider
- `state`: State token for CSRF validation

**Flow:**
1. Verify `state` token matches Redis stored value
2. Exchange `code` for `access_token` via provider's token endpoint
3. Fetch user info from provider
4. Encrypt and store token in database
5. Redirect to success page

**Response:**
```python
RedirectResponse(url="/integrations?success=github", status_code=302)
```

**Error Handling:**
- Invalid state → 400 Bad Request
- Code exchange fails → 500 Internal Server Error
- Show user-friendly error page

---

**3. Get Connection Status**

```http
GET /integrations/status
```

**Response:**
```json
{
    "connections": {
        "github": {
            "connected": true,
            "user": "johndoe",
            "email": "john@example.com",
            "connected_at": "2025-11-16T10:30:00Z",
            "last_sync": "2025-11-16T15:45:00Z"
        },
        "google": {
            "connected": false
        },
        "dropbox": {
            "connected": false
        },
        "notion": {
            "connected": false
        }
    }
}
```

---

**4. Disconnect Service**

```http
POST /integrations/{service}/disconnect
```

**Flow:**
1. Revoke OAuth token with provider (if supported)
2. Delete encrypted token from database
3. Log disconnection event

**Response:**
```json
{
    "message": "GitHub disconnected successfully"
}
```

---

#### GitHub-Specific Endpoints

**1. List Repositories**

```http
GET /integrations/github/repos?page=1&per_page=30
```

**Response:**
```json
{
    "repositories": [
        {
            "id": 12345,
            "name": "my-project",
            "full_name": "johndoe/my-project",
            "description": "A cool project",
            "private": false,
            "url": "https://github.com/johndoe/my-project",
            "default_branch": "main",
            "size": 1024,
            "language": "Python",
            "updated_at": "2025-11-15T10:30:00Z"
        }
    ],
    "total_count": 45,
    "page": 1,
    "per_page": 30
}
```

---

**2. Browse Repository Files**

```http
GET /integrations/github/repos/{owner}/{repo}/files?path=/docs
```

**Response:**
```json
{
    "path": "/docs",
    "files": [
        {
            "name": "README.md",
            "path": "docs/README.md",
            "type": "file",
            "size": 2048,
            "sha": "abc123...",
            "url": "https://api.github.com/..."
        },
        {
            "name": "guides",
            "path": "docs/guides",
            "type": "dir",
            "size": 0
        }
    ]
}
```

---

**3. Import GitHub Files**

```http
POST /integrations/github/import
```

**Request Body:**
```json
{
    "owner": "johndoe",
    "repo": "my-project",
    "files": [
        "README.md",
        "docs/architecture.md",
        "src/main.py"
    ],
    "branch": "main"
}
```

**Flow:**
1. Validate user has GitHub connected
2. Queue Celery task: `import_github_files`
3. Task fetches each file via GitHub API
4. Task processes files through existing ingestion pipeline
5. Return job_id for progress tracking

**Response:**
```json
{
    "job_id": "abc-123-def-456",
    "message": "Import queued",
    "file_count": 3
}
```

---

#### Google Drive-Specific Endpoints

**1. List Files/Folders**

```http
GET /integrations/google/files?parent_id=root&page_token=...
```

**Response:**
```json
{
    "files": [
        {
            "id": "1abc...",
            "name": "Project Documents",
            "mimeType": "application/vnd.google-apps.folder",
            "size": null,
            "modifiedTime": "2025-11-15T10:30:00Z",
            "iconLink": "https://..."
        },
        {
            "id": "2def...",
            "name": "Report.pdf",
            "mimeType": "application/pdf",
            "size": 204800,
            "modifiedTime": "2025-11-14T08:15:00Z"
        }
    ],
    "nextPageToken": "token123"
}
```

---

**2. Import Google Drive Files**

```http
POST /integrations/google/import
```

**Request Body:**
```json
{
    "file_ids": [
        "1abc...",
        "2def..."
    ]
}
```

**Flow:**
1. Validate Google Drive connected
2. Queue Celery task: `import_google_drive_files`
3. Task downloads files via Drive API
4. Handle Google Workspace files (export as PDF/DOCX)
5. Process through ingestion pipeline

**Response:**
```json
{
    "job_id": "xyz-789",
    "message": "Import queued",
    "file_count": 2
}
```

---

#### Dropbox-Specific Endpoints

**1. List Files/Folders**

```http
GET /integrations/dropbox/files?path=/Documents
```

**Response:**
```json
{
    "entries": [
        {
            ".tag": "folder",
            "name": "Work",
            "path_lower": "/documents/work",
            "id": "id:abc123"
        },
        {
            ".tag": "file",
            "name": "notes.txt",
            "path_lower": "/documents/notes.txt",
            "size": 1024,
            "server_modified": "2025-11-15T10:30:00Z"
        }
    ],
    "cursor": "cursor123",
    "has_more": false
}
```

---

**2. Import Dropbox Files**

```http
POST /integrations/dropbox/import
```

**Request Body:**
```json
{
    "paths": [
        "/Documents/notes.txt",
        "/Work/project.pdf"
    ]
}
```

**Response:**
```json
{
    "job_id": "dropbox-456",
    "message": "Import queued",
    "file_count": 2
}
```

---

#### Notion-Specific Endpoints

**1. List Pages/Databases**

```http
GET /integrations/notion/pages?page_size=50
```

**Response:**
```json
{
    "results": [
        {
            "id": "page-123",
            "object": "page",
            "created_time": "2025-11-15T10:30:00Z",
            "last_edited_time": "2025-11-16T08:00:00Z",
            "title": "Project Documentation",
            "url": "https://notion.so/..."
        },
        {
            "id": "db-456",
            "object": "database",
            "title": "Task List",
            "url": "https://notion.so/..."
        }
    ],
    "has_more": false,
    "next_cursor": null
}
```

---

**2. Import Notion Pages**

```http
POST /integrations/notion/import
```

**Request Body:**
```json
{
    "page_ids": [
        "page-123",
        "page-456"
    ],
    "include_children": true
}
```

**Flow:**
1. Validate Notion connected
2. Queue Celery task: `import_notion_pages`
3. Task fetches page content via Notion API
4. Convert Notion blocks to markdown
5. Process through ingestion pipeline

**Response:**
```json
{
    "job_id": "notion-789",
    "message": "Import queued",
    "page_count": 2
}
```

---

## Database Schema

### New Table: `integration_tokens`

**Purpose:** Store encrypted OAuth tokens for connected services

```sql
CREATE TABLE integration_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    service VARCHAR(50) NOT NULL,  -- 'github', 'google', 'dropbox', 'notion'
    access_token TEXT NOT NULL,     -- Encrypted
    refresh_token TEXT,             -- Encrypted (if provider supports)
    token_type VARCHAR(50),         -- 'Bearer'
    expires_at TIMESTAMP,           -- Token expiration
    scope TEXT,                     -- Granted scopes
    provider_user_id VARCHAR(255),  -- User ID from provider
    provider_user_email VARCHAR(255),
    provider_user_name VARCHAR(255),
    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(user_id, service)  -- One connection per service per user
);

CREATE INDEX idx_integration_tokens_user ON integration_tokens(user_id);
CREATE INDEX idx_integration_tokens_service ON integration_tokens(service);
```

**Schema Notes:**
- `access_token` and `refresh_token` are encrypted using Fernet encryption (see Security section)
- `expires_at` enables automatic token refresh
- `last_used` tracks activity for audit logs

---

### New Table: `integration_imports`

**Purpose:** Track import history and job status

```sql
CREATE TABLE integration_imports (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    service VARCHAR(50) NOT NULL,
    job_id VARCHAR(255) UNIQUE NOT NULL,  -- Celery task ID
    status VARCHAR(50) NOT NULL,  -- 'pending', 'processing', 'completed', 'failed'
    file_count INTEGER,
    files_processed INTEGER DEFAULT 0,
    files_failed INTEGER DEFAULT 0,
    total_size_bytes BIGINT,
    metadata JSONB,  -- Service-specific data (repo name, folder path, etc.)
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_integration_imports_user ON integration_imports(user_id);
CREATE INDEX idx_integration_imports_job ON integration_imports(job_id);
CREATE INDEX idx_integration_imports_service ON integration_imports(service);
```

**Usage:**
- Track all import jobs (similar to existing job status but persisted)
- Enable import history view in UI
- Audit trail for compliance

---

## Frontend UI Design

### New Tab: "Integrations"

**Location:** Add to main navigation tabs (alongside Upload, Search, Clusters, Duplicates, Analytics)

**Layout:**

```
┌────────────────────────────────────────────────────────────┐
│  SyncBoard 3.0 Knowledge Bank                              │
│  ┌──────────┬────────┬──────────┬────────────┬──────────┐  │
│  │ Upload   │ Search │ Clusters │ Duplicates │ Analytics│  │
│  └──────────┴────────┴──────────┴────────────┴──────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Integrations                                   [NEW] │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓  │
│  ┃ Connect Your Cloud Services                         ┃  │
│  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛  │
│                                                            │
│  ┌──────────────────────┐  ┌──────────────────────┐      │
│  │  🐙 GitHub           │  │  📁 Google Drive     │      │
│  │  ───────────────     │  │  ───────────────     │      │
│  │  Status: Connected   │  │  Status: Not Connected│     │
│  │  User: johndoe       │  │                       │     │
│  │  Last sync: 2h ago   │  │  Import files from    │     │
│  │                      │  │  Google Drive         │     │
│  │  [Browse Files]      │  │                       │     │
│  │  [Disconnect]        │  │  [Connect]            │     │
│  └──────────────────────┘  └──────────────────────┘      │
│                                                            │
│  ┌──────────────────────┐  ┌──────────────────────┐      │
│  │  📦 Dropbox          │  │  📝 Notion           │      │
│  │  ───────────────     │  │  ───────────────     │      │
│  │  Status: Not Connected│ │  Status: Not Connected│     │
│  │                      │  │                       │     │
│  │  Store and share     │  │  Import your notes    │     │
│  │  files from Dropbox  │  │  and wikis            │     │
│  │                      │  │                       │     │
│  │  [Connect]           │  │  [Connect]            │     │
│  └──────────────────────┘  └──────────────────────┘      │
│                                                            │
│  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓  │
│  ┃ Recent Imports                                      ┃  │
│  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛  │
│                                                            │
│  🐙 GitHub: my-project/README.md → Doc 42  [2 hours ago]  │
│  📁 Google: Project Docs → 5 files         [1 day ago]    │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

### Service Card Component

Each service gets a card with:

**Connected State:**
```html
<div class="integration-card connected">
    <div class="integration-header">
        <span class="integration-icon">🐙</span>
        <h3>GitHub</h3>
        <span class="status-badge connected">✓ Connected</span>
    </div>
    <div class="integration-body">
        <p class="user-info">
            <strong>User:</strong> johndoe<br>
            <strong>Email:</strong> john@example.com
        </p>
        <p class="last-sync">Last sync: 2 hours ago</p>
    </div>
    <div class="integration-actions">
        <button class="btn-primary" onclick="browseGitHub()">
            Browse Repositories
        </button>
        <button class="btn-secondary" onclick="disconnectGitHub()">
            Disconnect
        </button>
    </div>
</div>
```

**Disconnected State:**
```html
<div class="integration-card disconnected">
    <div class="integration-header">
        <span class="integration-icon">📁</span>
        <h3>Google Drive</h3>
        <span class="status-badge disconnected">Not Connected</span>
    </div>
    <div class="integration-body">
        <p class="description">
            Import documents, PDFs, spreadsheets, and presentations
            from your Google Drive.
        </p>
    </div>
    <div class="integration-actions">
        <button class="btn-primary" onclick="connectGoogle()">
            Connect Google Drive
        </button>
    </div>
</div>
```

---

### File Browser Modal (GitHub Example)

When user clicks "Browse Repositories":

```
┌──────────────────────────────────────────────────────┐
│  Browse GitHub Repositories                    [×]   │
├──────────────────────────────────────────────────────┤
│                                                      │
│  Search: [___________________________] [Search]      │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │ ☐ my-project                          [Browse]│ │
│  │   Python · Updated 2 hours ago · Private      │ │
│  │   A cool project for doing things             │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │ ☐ docs-site                           [Browse]│ │
│  │   Markdown · Updated 1 day ago · Public       │ │
│  │   Documentation website                       │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  [Previous] Page 1 of 5 [Next]                      │
│                                                      │
│  [Cancel]                      [Import Selected (0)]│
└──────────────────────────────────────────────────────┘
```

**When user clicks "Browse" on a repository:**

```
┌──────────────────────────────────────────────────────┐
│  my-project                              [← Back] [×]│
├──────────────────────────────────────────────────────┤
│                                                      │
│  Branch: [main ▼]        Path: /                    │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │ ☑ README.md                              2 KB │ │
│  │ ☐ 📁 src/                                      │ │
│  │ ☑ 📁 docs/                                     │ │
│  │ ☐ requirements.txt                       500 B│ │
│  │ ☐ LICENSE                                1 KB │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  [Select All] [Deselect All]                        │
│                                                      │
│  Selected: 2 items (README.md, docs/)               │
│                                                      │
│  [Cancel]                      [Import Selected (2)]│
└──────────────────────────────────────────────────────┘
```

---

### Import Progress Modal

After clicking "Import Selected":

```
┌──────────────────────────────────────────────────────┐
│  Importing from GitHub                         [×]   │
├──────────────────────────────────────────────────────┤
│                                                      │
│  Importing 2 files from my-project...               │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │ ████████████████░░░░░░░░░░░░░░░░░░░░ 60%    │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  ✓ README.md → Doc 42                               │
│  ⏳ Processing docs/architecture.md...              │
│                                                      │
│  [Close]                                            │
└──────────────────────────────────────────────────────┘
```

---

## Security Considerations

### 1. Token Encryption

**Method:** Fernet Symmetric Encryption (cryptography library)

**Implementation:**
```python
from cryptography.fernet import Fernet
import os

# Generate key once, store in environment
# ENCRYPTION_KEY=your-32-byte-base64-encoded-key
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    raise ValueError("ENCRYPTION_KEY must be set")

cipher = Fernet(ENCRYPTION_KEY.encode())

def encrypt_token(token: str) -> str:
    """Encrypt OAuth token before storing in database."""
    return cipher.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    """Decrypt OAuth token when retrieving from database."""
    return cipher.decrypt(encrypted_token.encode()).decode()
```

**Key Management:**
- Store `ENCRYPTION_KEY` in `.env` file (never commit to git)
- Use different keys for dev/staging/production
- Rotate keys periodically (requires re-encrypting all tokens)

---

### 2. CSRF Protection (State Token)

**Problem:** OAuth callback can be hijacked by malicious sites

**Solution:** Generate random state token, validate on callback

```python
import secrets

def initiate_oauth(user_id: str, service: str):
    # Generate cryptographically secure random token
    state = secrets.token_urlsafe(32)

    # Store in Redis with 10-minute expiration
    redis_client.setex(
        f"oauth_state:{state}",
        600,  # 10 minutes
        json.dumps({"user_id": user_id, "service": service})
    )

    # Include in OAuth URL
    auth_url = f"{OAUTH_URL}?state={state}&..."
    return auth_url

def handle_callback(code: str, state: str):
    # Verify state exists in Redis
    data = redis_client.get(f"oauth_state:{state}")
    if not data:
        raise HTTPException(400, "Invalid or expired state token")

    # Delete state (single use)
    redis_client.delete(f"oauth_state:{state}")

    # Continue with token exchange...
```

---

### 3. Token Refresh Strategy

**Google Drive Tokens Expire After 1 Hour**

**Implementation:**
```python
def get_google_token(user_id: str) -> str:
    """Get valid Google access token, refresh if needed."""
    token_row = db.query(IntegrationToken).filter_by(
        user_id=user_id,
        service="google"
    ).first()

    if not token_row:
        raise HTTPException(401, "Google Drive not connected")

    # Check if token expired
    if token_row.expires_at and token_row.expires_at < datetime.utcnow():
        # Token expired, refresh it
        new_token = refresh_google_token(token_row.refresh_token)

        # Update database
        token_row.access_token = encrypt_token(new_token["access_token"])
        token_row.expires_at = datetime.utcnow() + timedelta(seconds=new_token["expires_in"])
        db.commit()

    return decrypt_token(token_row.access_token)

def refresh_google_token(encrypted_refresh_token: str) -> dict:
    """Exchange refresh token for new access token."""
    refresh_token = decrypt_token(encrypted_refresh_token)

    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
    )

    if response.status_code != 200:
        raise HTTPException(500, "Failed to refresh Google token")

    return response.json()
```

---

### 4. Rate Limiting

**Protect Against API Quota Exhaustion**

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/integrations/github/import")
@limiter.limit("10/hour")  # Max 10 imports per hour
async def import_github_files(request: Request, ...):
    pass

@router.get("/integrations/google/files")
@limiter.limit("100/hour")  # Max 100 file list requests per hour
async def list_google_files(request: Request, ...):
    pass
```

---

### 5. Scope Minimization

**Only Request Necessary Permissions**

❌ **Bad:**
```python
# Requesting write access when only read needed
GITHUB_SCOPES = "repo,write:repo_hook,delete_repo"
```

✅ **Good:**
```python
# Minimal scopes for read-only import
GITHUB_SCOPES = "repo"  # Can read private repos
# OR
GITHUB_SCOPES = "public_repo"  # Only public repos (if sufficient)
```

---

### 6. Audit Logging

**Log All Integration Activity**

```python
def log_integration_event(
    user_id: str,
    service: str,
    action: str,
    metadata: dict = None
):
    logger.info(
        f"Integration event: user={user_id}, service={service}, "
        f"action={action}, metadata={metadata}"
    )

    # Optionally store in database for compliance
    db.execute(
        """
        INSERT INTO audit_logs (user_id, service, action, metadata, timestamp)
        VALUES (:user_id, :service, :action, :metadata, NOW())
        """,
        {
            "user_id": user_id,
            "service": service,
            "action": action,
            "metadata": json.dumps(metadata or {})
        }
    )
```

**Events to Log:**
- OAuth initiated
- OAuth completed
- Token refreshed
- Service disconnected
- Files imported
- API errors

---

## Error Handling Strategy

### Backend Error Responses

**Standard Error Format:**
```json
{
    "error": "token_expired",
    "message": "Your Google Drive connection expired. Please reconnect.",
    "service": "google",
    "action_required": "reconnect"
}
```

**Error Categories:**

1. **Authentication Errors (401)**
   - Token expired
   - Token revoked
   - Service not connected

2. **Authorization Errors (403)**
   - Insufficient permissions
   - File not accessible
   - Rate limit exceeded

3. **Not Found Errors (404)**
   - File deleted
   - Repository archived
   - Page moved (Notion)

4. **Service Errors (502)**
   - Provider API down
   - Network timeout
   - Invalid response from provider

5. **Quota Errors (429)**
   - Rate limit hit
   - API quota exhausted

---

### Frontend Error Handling

**User-Friendly Error Messages:**

```javascript
async function handleIntegrationError(error, service) {
    const errorMap = {
        'token_expired': {
            title: 'Connection Expired',
            message: `Your ${service} connection expired. Please reconnect.`,
            action: 'reconnect',
            actionText: 'Reconnect'
        },
        'insufficient_permissions': {
            title: 'Permission Denied',
            message: `SyncBoard doesn't have permission to access this ${service} resource.`,
            action: 'help',
            actionText: 'Learn More'
        },
        'rate_limit': {
            title: 'Rate Limit Exceeded',
            message: `You've reached the ${service} API limit. Please try again later.`,
            action: 'wait',
            actionText: 'OK'
        },
        'service_unavailable': {
            title: 'Service Unavailable',
            message: `${service} is currently unavailable. Please try again later.`,
            action: 'retry',
            actionText: 'Retry'
        }
    };

    const errorInfo = errorMap[error.error] || {
        title: 'Error',
        message: error.message || 'An unexpected error occurred.',
        action: 'dismiss',
        actionText: 'OK'
    };

    showErrorDialog(errorInfo);
}
```

---

### Automatic Recovery

**Token Expiration:**
- Backend automatically refreshes tokens before API calls
- If refresh fails, return clear error to frontend
- Frontend prompts user to reconnect

**Transient Failures:**
- Retry logic with exponential backoff
- Max 3 retries for network errors
- Fail gracefully and inform user

**Partial Import Failures:**
- Continue processing remaining files
- Report which files succeeded vs failed
- Show summary: "5 of 7 files imported successfully"

---

## Implementation Phases

### Phase 5.1: Foundation (Week 1)

**Goals:**
- Database schema and migrations
- Token encryption utilities
- Base OAuth router structure
- Frontend Integrations tab UI

**Deliverables:**
- ✅ `integration_tokens` table created
- ✅ `integration_imports` table created
- ✅ `backend/routers/integrations.py` skeleton
- ✅ `backend/utils/encryption.py` for Fernet encryption
- ✅ Frontend Integrations tab with service cards
- ✅ Unit tests for encryption/decryption

---

### Phase 5.2: GitHub Integration (Week 2)

**Goals:**
- Complete GitHub OAuth flow
- Repository browsing UI
- File selection and import

**Deliverables:**
- ✅ GitHub OAuth authorize/callback endpoints
- ✅ Repository listing API
- ✅ File browsing API
- ✅ Celery task: `import_github_files`
- ✅ Frontend: GitHub browser modal
- ✅ End-to-end test: Connect → Browse → Import

---

### Phase 5.3: Google Drive Integration (Week 3)

**Goals:**
- Google OAuth flow with refresh tokens
- File/folder browsing
- Handle Google Workspace exports (Docs → PDF)

**Deliverables:**
- ✅ Google OAuth endpoints
- ✅ Token refresh implementation
- ✅ File listing API
- ✅ Celery task: `import_google_drive_files`
- ✅ Frontend: Google Drive picker
- ✅ Google Workspace file export handling

---

### Phase 5.4: Dropbox & Notion (Week 4)

**Goals:**
- Dropbox OAuth and file import
- Notion OAuth and page import

**Deliverables:**
- ✅ Dropbox OAuth endpoints
- ✅ Dropbox file browsing and import
- ✅ Notion OAuth endpoints
- ✅ Notion page listing and markdown export
- ✅ Frontend: Dropbox and Notion pickers
- ✅ End-to-end tests for both services

---

### Phase 5.5: Polish & Testing (Week 5)

**Goals:**
- Error handling refinement
- Import history view
- Performance optimization
- Comprehensive testing

**Deliverables:**
- ✅ Import history page in frontend
- ✅ Error recovery flows tested
- ✅ Rate limiting verified
- ✅ Security audit completed
- ✅ Documentation updated
- ✅ All integration tests passing

---

## Testing Strategy

### Unit Tests

**backend/tests/test_oauth.py:**
- Token encryption/decryption
- State token generation and validation
- Token refresh logic

**backend/tests/test_github_integration.py:**
- Repository listing
- File browsing
- Import task

**backend/tests/test_google_integration.py:**
- OAuth flow
- Token refresh
- Workspace file export

---

### Integration Tests

**End-to-End Flow:**
1. User clicks "Connect GitHub"
2. OAuth flow completes
3. Token stored encrypted in DB
4. User browses repositories
5. User selects files
6. Import queued as Celery task
7. Files processed and added to knowledge bank
8. User sees success notification

---

### Manual Testing Checklist

- [ ] GitHub OAuth flow works
- [ ] Google Drive OAuth with refresh works
- [ ] Dropbox OAuth works
- [ ] Notion OAuth works
- [ ] All file browsers load correctly
- [ ] Import progress shows real-time updates
- [ ] Error messages are user-friendly
- [ ] Disconnecting services revokes tokens
- [ ] Import history shows all past imports
- [ ] Rate limiting prevents abuse

---

## Success Criteria

✅ **All integrations implemented and tested**
✅ **OAuth flows secure and production-ready**
✅ **Beautiful, intuitive UI**
✅ **Comprehensive error handling**
✅ **Token encryption and refresh working**
✅ **Import jobs process in background via Celery**
✅ **Documentation complete**
✅ **All tests passing**

---

## Next Steps

1. **Review this architecture document** - Ensure all requirements captured
2. **Set up OAuth apps** - Register with GitHub, Google, Dropbox, Notion
3. **Begin Phase 5.1** - Database schema and foundation
4. **Iterative implementation** - Build one service at a time, test thoroughly

---

**Document Status:** ✅ Complete
**Ready for Implementation:** Yes
**Estimated Total Time:** 5 weeks (40 hours per week = 200 hours)

