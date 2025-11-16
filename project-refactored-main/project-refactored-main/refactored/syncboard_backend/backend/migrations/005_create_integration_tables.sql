-- Migration 005: Create Integration Tables for Cloud Services
-- Purpose: Store encrypted OAuth tokens and track import jobs
-- Date: 2025-11-16

-- =============================================================================
-- Table: integration_tokens
-- Purpose: Store encrypted OAuth tokens for connected cloud services
-- =============================================================================

CREATE TABLE IF NOT EXISTS integration_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    service VARCHAR(50) NOT NULL,  -- 'github', 'google', 'dropbox', 'notion'
    access_token TEXT NOT NULL,     -- Encrypted with Fernet
    refresh_token TEXT,             -- Encrypted (if provider supports refresh)
    token_type VARCHAR(50) DEFAULT 'Bearer',
    expires_at TIMESTAMP,           -- Token expiration (for refresh logic)
    scope TEXT,                     -- Granted OAuth scopes
    provider_user_id VARCHAR(255),  -- User ID from OAuth provider
    provider_user_email VARCHAR(255),
    provider_user_name VARCHAR(255),
    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT unique_user_service UNIQUE(user_id, service),
    CONSTRAINT fk_integration_tokens_user FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
);

-- Indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_integration_tokens_user ON integration_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_integration_tokens_service ON integration_tokens(service);
CREATE INDEX IF NOT EXISTS idx_integration_tokens_expires ON integration_tokens(expires_at) WHERE expires_at IS NOT NULL;

-- =============================================================================
-- Table: integration_imports
-- Purpose: Track cloud service import jobs and history
-- =============================================================================

CREATE TABLE IF NOT EXISTS integration_imports (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    service VARCHAR(50) NOT NULL,  -- 'github', 'google', 'dropbox', 'notion'
    job_id VARCHAR(255) UNIQUE NOT NULL,  -- Celery task ID
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
    file_count INTEGER,
    files_processed INTEGER DEFAULT 0,
    files_failed INTEGER DEFAULT 0,
    total_size_bytes BIGINT,
    metadata JSONB,  -- Service-specific data (repo name, folder path, etc.)
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT fk_integration_imports_user FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE,
    CONSTRAINT chk_status CHECK (status IN ('pending', 'processing', 'completed', 'failed'))
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_integration_imports_user ON integration_imports(user_id);
CREATE INDEX IF NOT EXISTS idx_integration_imports_job ON integration_imports(job_id);
CREATE INDEX IF NOT EXISTS idx_integration_imports_service ON integration_imports(service);
CREATE INDEX IF NOT EXISTS idx_integration_imports_status ON integration_imports(status);
CREATE INDEX IF NOT EXISTS idx_integration_imports_created ON integration_imports(created_at DESC);

-- =============================================================================
-- Comments for documentation
-- =============================================================================

COMMENT ON TABLE integration_tokens IS 'Stores encrypted OAuth tokens for cloud service integrations';
COMMENT ON COLUMN integration_tokens.access_token IS 'Encrypted OAuth access token (Fernet encryption)';
COMMENT ON COLUMN integration_tokens.refresh_token IS 'Encrypted OAuth refresh token (Google, etc.)';
COMMENT ON COLUMN integration_tokens.expires_at IS 'Token expiration timestamp for automatic refresh';
COMMENT ON COLUMN integration_tokens.last_used IS 'Last time this token was used for an API call';

COMMENT ON TABLE integration_imports IS 'Tracks cloud service import jobs and provides audit history';
COMMENT ON COLUMN integration_imports.job_id IS 'Celery background task ID for tracking import progress';
COMMENT ON COLUMN integration_imports.metadata IS 'Service-specific metadata (e.g., {"repo": "owner/name", "branch": "main"})';
COMMENT ON COLUMN integration_imports.files_processed IS 'Number of files successfully imported';
COMMENT ON COLUMN integration_imports.files_failed IS 'Number of files that failed to import';
