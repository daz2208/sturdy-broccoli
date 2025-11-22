"""
Application Constants for SyncBoard 3.0 Knowledge Bank.

Centralizes configuration values, limits, and magic numbers.
"""

import os

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

# Maximum characters to analyze for concept extraction
CONCEPT_EXTRACTION_SAMPLE_SIZE = int(os.getenv("CONCEPT_SAMPLE_SIZE", "6000"))

# Sampling method: "smart" (beginning/middle/end) or "truncate" (first N chars)
CONCEPT_EXTRACTION_METHOD = os.getenv("CONCEPT_SAMPLE_METHOD", "smart")

# =============================================================================
# Redis Caching Configuration (Improvement #5)
# =============================================================================

# Enable/disable caching for concept extraction
ENABLE_CONCEPT_CACHING = os.getenv("ENABLE_CONCEPT_CACHING", "true").lower() == "true"

# Cache TTL in days for concept extraction results
CONCEPT_CACHE_TTL_DAYS = int(os.getenv("CONCEPT_CACHE_TTL_DAYS", "7"))

# Cache TTL in days for similarity computations
SIMILARITY_CACHE_TTL_DAYS = int(os.getenv("SIMILARITY_CACHE_TTL_DAYS", "30"))

# =============================================================================
# Concept Quality Filtering (Improvement #6)
# =============================================================================

# Minimum confidence threshold for concept extraction (0.0-1.0)
# Only concepts with confidence >= this value will be kept
MIN_CONCEPT_CONFIDENCE = float(os.getenv("MIN_CONCEPT_CONFIDENCE", "0.7"))

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
