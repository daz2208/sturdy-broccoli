"""
Centralized Configuration for SyncBoard 3.0 Knowledge Bank.

All environment variables are managed here using Pydantic Settings.
This provides:
- Type validation
- Default values
- Clear documentation
- Single source of truth

Usage:
    from backend.config import settings

    # Access configuration
    db_url = settings.database_url
    api_key = settings.openai_api_key
"""

import os
from typing import Optional, Literal
from pydantic import Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Environment variables are prefixed with SYNCBOARD_ where applicable.
    See .env.example for all available options.
    """

    # =============================================================================
    # Application Environment
    # =============================================================================

    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Application environment",
        validation_alias="SYNCBOARD_ENVIRONMENT"
    )

    testing: bool = Field(
        default=False,
        description="Enable testing mode",
        validation_alias="TESTING"
    )

    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
        validation_alias="SYNCBOARD_LOG_LEVEL"
    )

    allowed_origins: str = Field(
        default="*",
        description="CORS allowed origins (comma-separated or '*')",
        validation_alias="SYNCBOARD_ALLOWED_ORIGINS"
    )

    # =============================================================================
    # Database
    # =============================================================================

    database_url: str = Field(
        default="sqlite:///./syncboard.db",
        description="Database connection URL (PostgreSQL or SQLite)",
        validation_alias="DATABASE_URL"
    )

    # =============================================================================
    # Authentication & Security
    # =============================================================================

    secret_key: str = Field(
        ...,  # Required field
        description="Secret key for JWT token signing (generate with: openssl rand -hex 32)",
        validation_alias="SYNCBOARD_SECRET_KEY"
    )

    token_expire_minutes: int = Field(
        default=1440,  # 24 hours
        description="JWT token expiration time in minutes",
        validation_alias="SYNCBOARD_TOKEN_EXPIRE_MINUTES"
    )

    encryption_key: Optional[str] = Field(
        default=None,
        description="Encryption key for sensitive data",
        validation_alias="ENCRYPTION_KEY"
    )

    # =============================================================================
    # Redis & Caching
    # =============================================================================

    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
        validation_alias="REDIS_URL"
    )

    celery_broker_url: Optional[str] = Field(
        default=None,
        description="Celery broker URL (defaults to redis_url)",
        validation_alias="CELERY_BROKER_URL"
    )

    celery_result_backend: Optional[str] = Field(
        default=None,
        description="Celery result backend URL (defaults to redis_url)",
        validation_alias="CELERY_RESULT_BACKEND"
    )

    enable_concept_caching: bool = Field(
        default=True,
        description="Enable Redis caching for concept extraction",
        validation_alias="ENABLE_CONCEPT_CACHING"
    )

    concept_cache_ttl_days: int = Field(
        default=7,
        description="Concept cache TTL in days",
        validation_alias="CONCEPT_CACHE_TTL_DAYS"
    )

    similarity_cache_ttl_days: int = Field(
        default=30,
        description="Similarity computation cache TTL in days",
        validation_alias="SIMILARITY_CACHE_TTL_DAYS"
    )

    # =============================================================================
    # LLM Providers
    # =============================================================================

    llm_provider: Literal["openai", "ollama"] = Field(
        default="openai",
        description="LLM provider to use",
        validation_alias="LLM_PROVIDER"
    )

    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key",
        validation_alias="OPENAI_API_KEY"
    )

    openai_concept_model: str = Field(
        default="gpt-5-nano",
        description="OpenAI model for concept extraction",
        validation_alias="OPENAI_CONCEPT_MODEL"
    )

    openai_suggestion_model: str = Field(
        default="gpt-5-mini",
        description="OpenAI model for build suggestions",
        validation_alias="OPENAI_SUGGESTION_MODEL"
    )

    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL",
        validation_alias="OLLAMA_BASE_URL"
    )

    ollama_concept_model: str = Field(
        default="llama2",
        description="Ollama model for concept extraction",
        validation_alias="OLLAMA_CONCEPT_MODEL"
    )

    ollama_suggestion_model: str = Field(
        default="llama2",
        description="Ollama model for build suggestions",
        validation_alias="OLLAMA_SUGGESTION_MODEL"
    )

    transcription_model: str = Field(
        default="gpt-4o-mini-transcribe",
        description="Model for audio/video transcription",
        validation_alias="TRANSCRIPTION_MODEL"
    )

    summary_model: str = Field(
        default="gpt-5-nano",
        description="Model for content summarization",
        validation_alias="SUMMARY_MODEL"
    )

    # =============================================================================
    # AI/ML Configuration
    # =============================================================================

    concept_sample_size: int = Field(
        default=6000,
        description="Maximum characters to analyze for concept extraction",
        validation_alias="CONCEPT_SAMPLE_SIZE"
    )

    concept_sample_method: Literal["smart", "truncate"] = Field(
        default="smart",
        description="Sampling method for concept extraction",
        validation_alias="CONCEPT_SAMPLE_METHOD"
    )

    enable_dual_pass: bool = Field(
        default=True,
        description="Enable dual-pass extraction with self-critique",
        validation_alias="ENABLE_DUAL_PASS"
    )

    dual_pass_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Confidence threshold below which dual-pass is triggered",
        validation_alias="DUAL_PASS_THRESHOLD"
    )

    min_concept_confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for concept extraction",
        validation_alias="MIN_CONCEPT_CONFIDENCE"
    )

    vector_dim: int = Field(
        default=256,
        description="Vector store dimensionality",
        validation_alias="SYNCBOARD_VECTOR_DIM"
    )

    # =============================================================================
    # Storage & Files
    # =============================================================================

    storage_path: str = Field(
        default="storage.json",
        description="Path to file-based storage (legacy)",
        validation_alias="SYNCBOARD_STORAGE_PATH"
    )

    max_batch_files: int = Field(
        default=20,
        description="Maximum number of files in batch upload",
        validation_alias="MAX_BATCH_FILES"
    )

    # =============================================================================
    # Transcription & OCR
    # =============================================================================

    transcription_chunk_duration_seconds: int = Field(
        default=300,
        description="Audio chunk duration for transcription (seconds)",
        validation_alias="TRANSCRIPTION_CHUNK_DURATION_SECONDS"
    )

    transcription_chunk_threshold_seconds: int = Field(
        default=600,
        description="Audio duration threshold for chunking (seconds)",
        validation_alias="TRANSCRIPTION_CHUNK_THRESHOLD_SECONDS"
    )

    tesseract_cmd: Optional[str] = Field(
        default=None,
        description="Path to Tesseract OCR binary",
        validation_alias="TESSERACT_CMD"
    )

    # =============================================================================
    # OAuth Integrations
    # =============================================================================

    google_client_id: Optional[str] = Field(
        default=None,
        description="Google OAuth client ID",
        validation_alias="GOOGLE_CLIENT_ID"
    )

    google_client_secret: Optional[str] = Field(
        default=None,
        description="Google OAuth client secret",
        validation_alias="GOOGLE_CLIENT_SECRET"
    )

    github_client_id: Optional[str] = Field(
        default=None,
        description="GitHub OAuth client ID",
        validation_alias="GITHUB_CLIENT_ID"
    )

    github_client_secret: Optional[str] = Field(
        default=None,
        description="GitHub OAuth client secret",
        validation_alias="GITHUB_CLIENT_SECRET"
    )

    oauth_google_redirect_uri: str = Field(
        default="http://localhost:8000/auth/google/callback",
        description="Google OAuth redirect URI",
        validation_alias="OAUTH_GOOGLE_REDIRECT_URI"
    )

    oauth_github_redirect_uri: str = Field(
        default="http://localhost:8000/auth/github/callback",
        description="GitHub OAuth redirect URI",
        validation_alias="OAUTH_GITHUB_REDIRECT_URI"
    )

    github_redirect_uri: str = Field(
        default="http://localhost:8000/integrations/github/callback",
        description="GitHub integration redirect URI",
        validation_alias="GITHUB_REDIRECT_URI"
    )

    google_redirect_uri: str = Field(
        default="http://localhost:8000/integrations/google/callback",
        description="Google integration redirect URI",
        validation_alias="GOOGLE_REDIRECT_URI"
    )

    dropbox_app_key: Optional[str] = Field(
        default=None,
        description="Dropbox app key",
        validation_alias="DROPBOX_APP_KEY"
    )

    dropbox_app_secret: Optional[str] = Field(
        default=None,
        description="Dropbox app secret",
        validation_alias="DROPBOX_APP_SECRET"
    )

    dropbox_redirect_uri: str = Field(
        default="http://localhost:8000/integrations/dropbox/callback",
        description="Dropbox redirect URI",
        validation_alias="DROPBOX_REDIRECT_URI"
    )

    notion_client_id: Optional[str] = Field(
        default=None,
        description="Notion client ID",
        validation_alias="NOTION_CLIENT_ID"
    )

    notion_client_secret: Optional[str] = Field(
        default=None,
        description="Notion client secret",
        validation_alias="NOTION_CLIENT_SECRET"
    )

    notion_redirect_uri: str = Field(
        default="http://localhost:8000/integrations/notion/callback",
        description="Notion redirect URI",
        validation_alias="NOTION_REDIRECT_URI"
    )

    frontend_url: str = Field(
        default="http://localhost:3000",
        description="Frontend application URL",
        validation_alias="FRONTEND_URL"
    )

    # =============================================================================
    # Computed Properties
    # =============================================================================

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @property
    def is_testing(self) -> bool:
        """Check if running in test mode."""
        return self.testing

    @property
    def effective_celery_broker_url(self) -> str:
        """Get Celery broker URL (falls back to redis_url)."""
        return self.celery_broker_url or self.redis_url

    @property
    def effective_celery_result_backend(self) -> str:
        """Get Celery result backend URL (falls back to redis_url)."""
        return self.celery_result_backend or self.redis_url

    # =============================================================================
    # Pydantic Model Configuration
    # =============================================================================

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Allow extra fields for forward compatibility
    )

    # =============================================================================
    # Field Validators
    # =============================================================================

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v):
        """Convert postgres:// to postgresql:// for SQLAlchemy compatibility."""
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Ensure log level is uppercase and valid."""
        v = v.upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        """Ensure environment is lowercase."""
        return v.lower()


# =============================================================================
# Global Settings Instance
# =============================================================================

# Create settings instance - will raise validation error if required fields missing
try:
    settings = Settings()
except Exception as e:
    # In testing mode, create minimal settings
    if os.getenv("TESTING") == "true":
        # Provide minimal test settings
        os.environ.setdefault("SYNCBOARD_SECRET_KEY", "test-secret-key-for-testing-only")
        settings = Settings()
    else:
        raise RuntimeError(
            f"Failed to load application settings: {e}\n\n"
            "Required environment variables:\n"
            "- SYNCBOARD_SECRET_KEY (generate with: openssl rand -hex 32)\n\n"
            "See .env.example for all available configuration options."
        ) from e


# =============================================================================
# Helper Functions
# =============================================================================

def get_settings() -> Settings:
    """
    Get settings instance (for dependency injection).

    Usage:
        @app.get("/endpoint")
        def endpoint(settings: Settings = Depends(get_settings)):
            ...
    """
    return settings


# =============================================================================
# Backwards Compatibility Helpers
# =============================================================================

def get_env(key: str, default: str = "") -> str:
    """
    Legacy helper for gradual migration from os.getenv.

    Deprecated: Use settings object directly instead.
    """
    import warnings
    warnings.warn(
        f"get_env('{key}') is deprecated. Use 'from backend.config import settings' instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return getattr(settings, key.lower().replace("syncboard_", ""), default)


__all__ = ["settings", "get_settings", "Settings"]
