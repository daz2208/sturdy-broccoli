"""
Application Constants for SyncBoard 3.0 Knowledge Bank.

Centralizes configuration values, limits, and magic numbers.

Note: Dynamic configuration (from environment variables) has been moved to config.py.
This file now only contains true constants that don't change between environments.
"""

# =============================================================================
# File Upload Limits
# =============================================================================

MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50MB max file upload
MAX_TEXT_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB max text content
MAX_DESCRIPTION_LENGTH = 5000  # 5000 chars for descriptions

# =============================================================================
# Pagination & Search Defaults
# =============================================================================

DEFAULT_TOP_K = 10  # Default number of search results
MAX_TOP_K = 50  # Maximum search results allowed
MAX_SUGGESTIONS = 20  # Maximum build suggestions

# =============================================================================
# Vector Store Configuration
# =============================================================================

DEFAULT_VECTOR_DIM = 256  # Default vector dimension
SNIPPET_LENGTH = 500  # Character length for search result snippets

# =============================================================================
# User & Content Limits
# =============================================================================

MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 50
MAX_FILENAME_LENGTH = 255
MAX_CLUSTER_NAME_LENGTH = 100
MAX_URL_LENGTH = 2048

# =============================================================================
# ZIP Extraction Safety Limits
# =============================================================================

ZIP_MAX_RECURSION_DEPTH = 5  # Maximum nested ZIP levels
ZIP_MAX_FILE_COUNT = 1000  # Maximum files to extract
ZIP_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB max per file
ZIP_MAX_TOTAL_SIZE = 100 * 1024 * 1024  # 100MB total extracted size
ZIP_MAX_COMPRESSION_RATIO = 1500  # Max ratio of uncompressed/compressed size (text compresses ~1000x)

# =============================================================================
# Authentication Configuration
# =============================================================================

DEFAULT_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours
JWT_ALGORITHM = "HS256"

# =============================================================================
# Storage Configuration
# =============================================================================

DEFAULT_STORAGE_PATH = "storage.json"

# =============================================================================
# Skill Levels
# =============================================================================

SKILL_LEVELS = ["beginner", "intermediate", "advanced", "unknown"]

# =============================================================================
# AI Concept Extraction Configuration
# =============================================================================
# Note: These values have been moved to config.py and are now loaded from
# environment variables through the centralized settings object.
# Access them via: from backend.config import settings
#
# - settings.concept_sample_size (CONCEPT_SAMPLE_SIZE)
# - settings.concept_sample_method (CONCEPT_SAMPLE_METHOD)
# - settings.enable_concept_caching (ENABLE_CONCEPT_CACHING)
# - settings.concept_cache_ttl_days (CONCEPT_CACHE_TTL_DAYS)
# - settings.similarity_cache_ttl_days (SIMILARITY_CACHE_TTL_DAYS)
# - settings.enable_dual_pass (ENABLE_DUAL_PASS)
# - settings.dual_pass_threshold (DUAL_PASS_THRESHOLD)
# - settings.min_concept_confidence (MIN_CONCEPT_CONFIDENCE)

# Valid concept categories (expanded from 5 to 11)
VALID_CONCEPT_CATEGORIES = [
    "language",      # Programming languages
    "framework",     # Web/app frameworks
    "library",       # Code libraries
    "tool",          # Development tools
    "platform",      # Cloud/hosting platforms
    "database",      # Databases
    "methodology",   # Development practices
    "architecture",  # System design patterns
    "testing",       # Testing approaches
    "devops",        # Operations concepts
    "concept"        # General programming concepts
]

# =============================================================================
# Reserved Usernames
# =============================================================================

RESERVED_USERNAMES = ["admin", "root", "system", "test", "guest", "null", "undefined"]
