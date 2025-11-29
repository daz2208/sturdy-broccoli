"""
Shared Dependencies for SyncBoard 3.0 Knowledge Bank.

Provides:
- Global state access (documents, metadata, clusters, users)
- Authentication dependencies (get_current_user)
- Storage lock for thread safety
- Service instances
"""

import asyncio
import logging
from typing import Dict
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .models import User, DocumentMetadata, Cluster
from .vector_store import VectorStore
from .concept_extractor import ConceptExtractor
from .clustering_improved import ImprovedClusteringEngine
from .image_processor import ImageProcessor
from .build_suggester_improved import ImprovedBuildSuggester
from .semantic_dictionary import SemanticDictionaryManager
from .llm_providers import OpenAIProvider
from .auth import decode_access_token
from .config import settings
from .repository_interface import KnowledgeBankRepository
from .db_repository import DatabaseKnowledgeBankRepository
from .database import get_db

# Logger
logger = logging.getLogger(__name__)

# =============================================================================
# OAuth2 Scheme
# =============================================================================

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# =============================================================================
# Global State
# =============================================================================

# Vector store for semantic search (shared across all KBs, filtered by allowed_doc_ids)
vector_store = VectorStore(dim=settings.vector_dim)

# Document storage (in-memory) - nested by knowledge_base_id
# Structure: {kb_id: {doc_id: content/metadata/cluster}}
documents: Dict[str, Dict[int, str]] = {}
metadata: Dict[str, Dict[int, DocumentMetadata]] = {}
clusters: Dict[str, Dict[int, Cluster]] = {}
users: Dict[str, str] = {}  # username -> hashed_password

# =============================================================================
# Service Instances
# =============================================================================

# LLM Provider (optional - only for semantic learning)
llm_provider = None
try:
    api_key = settings.openai_api_key
    if api_key and api_key != "sk-replace-with-your-actual-openai-key":
        llm_provider = OpenAIProvider(api_key=api_key)
        logger.info("OpenAI LLM provider initialized successfully")
    else:
        logger.info("OpenAI API key not configured - LLM features will use fallback")
except ValueError as e:
    logger.warning(f"Failed to initialize OpenAI provider (invalid config): {e}")
except Exception as e:
    logger.error(f"Unexpected error initializing LLM provider: {e}", exc_info=True)
# LLM provider is optional - system works without it, but logging helps debugging

# Semantic dictionary (with or without LLM learning)
semantic_dictionary = SemanticDictionaryManager(llm_provider=llm_provider)

# Core services
concept_extractor = ConceptExtractor()
clustering_engine = ImprovedClusteringEngine(semantic_dict=semantic_dictionary)
image_processor = ImageProcessor()
build_suggester = ImprovedBuildSuggester(llm_provider=llm_provider)

# =============================================================================
# Authentication Dependency
# =============================================================================

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    Get current user from JWT token.

    Args:
        token: JWT token from Authorization header

    Returns:
        User object with username

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        username = payload.get("sub")
        if not username or username not in users:
            raise credentials_exception
    except Exception:
        raise credentials_exception

    return User(username=username)

# =============================================================================
# Repository Dependency (Proposal #1 - New Pattern)
# =============================================================================

def get_repository(db: Session = Depends(get_db)) -> KnowledgeBankRepository:
    """
    Get repository instance for dependency injection.

    This is the NEW pattern for data access (Proposal #1).
    Routers should inject this instead of using global state.

    Usage:
        @router.post("/documents")
        async def create_document(
            content: str,
            repo: KnowledgeBankRepository = Depends(get_repository),
            user: User = Depends(get_current_user)
        ):
            doc_id = await repo.add_document(content, metadata)
            return {"doc_id": doc_id}

    Args:
        db: SQLAlchemy database session (injected)

    Returns:
        Repository instance
    """
    return DatabaseKnowledgeBankRepository(db_session=db, vector_dim=settings.vector_dim)

# =============================================================================
# State Access Functions (DEPRECATED - Use get_repository instead)
# =============================================================================
# Note: These global dictionaries are deprecated and will be removed after
# all routers are migrated to use the repository pattern.
# New code should use get_repository() dependency injection instead.

def get_documents() -> Dict[str, Dict[int, str]]:
    """Get all documents dictionary (nested by kb_id)."""
    return documents

def get_metadata() -> Dict[str, Dict[int, DocumentMetadata]]:
    """Get all metadata dictionary (nested by kb_id)."""
    return metadata

def get_clusters() -> Dict[str, Dict[int, Cluster]]:
    """Get all clusters dictionary (nested by kb_id)."""
    return clusters

def get_vector_store() -> VectorStore:
    """Get vector store instance."""
    return vector_store

def get_concept_extractor() -> ConceptExtractor:
    """Get concept extractor instance."""
    return concept_extractor

def get_clustering_engine() -> ImprovedClusteringEngine:
    """Get improved clustering engine instance."""
    return clustering_engine

def get_image_processor() -> ImageProcessor:
    """Get image processor instance."""
    return image_processor

def get_build_suggester() -> ImprovedBuildSuggester:
    """Get improved build suggester instance."""
    return build_suggester

# =============================================================================
# Knowledge Base Scoped Access Functions
# =============================================================================
#
# SECURITY NOTICE: KB-Scoping Architecture
# ========================================
# These functions implement tenant isolation by knowledge base (KB).
# Each user's data is stored in separate KB namespaces to prevent data leakage.
#
# IMPORTANT: Always use these KB-scoped functions when accessing user data.
# NEVER use the global get_documents(), get_metadata(), get_clusters() directly
# for user-facing operations - those are for system-level tasks only.
#
# Pattern for safe data access:
#   1. Get user's KB ID: kb_id = get_user_default_kb_id(username, db)
#   2. Get KB-scoped data: kb_docs = get_kb_documents(kb_id)
#   3. Filter further by ownership if needed: [d for d in kb_docs if meta.owner == username]
#
# This prevents:
#   - User A accessing User B's documents
#   - Data leakage between knowledge bases
#   - Cross-tenant information disclosure
# =============================================================================

def get_kb_documents(kb_id: str) -> Dict[int, str]:
    """
    Get documents for a specific knowledge base (KB-scoped access).

    SECURITY: Always use this for user-facing document operations.
    Never use global get_documents() directly - it bypasses KB isolation.

    Args:
        kb_id: Knowledge base ID from get_user_default_kb_id()

    Returns:
        Dict[doc_id, content] for documents in this KB only
    """
    if kb_id not in documents:
        documents[kb_id] = {}
    return documents[kb_id]

def get_kb_metadata(kb_id: str) -> Dict[int, DocumentMetadata]:
    """
    Get metadata for a specific knowledge base (KB-scoped access).

    SECURITY: Always use this for user-facing metadata operations.
    Never use global get_metadata() directly - it bypasses KB isolation.

    Args:
        kb_id: Knowledge base ID from get_user_default_kb_id()

    Returns:
        Dict[doc_id, DocumentMetadata] for documents in this KB only
    """
    if kb_id not in metadata:
        metadata[kb_id] = {}
    return metadata[kb_id]

def get_kb_clusters(kb_id: str) -> Dict[int, Cluster]:
    """
    Get clusters for a specific knowledge base (KB-scoped access).

    SECURITY: Always use this for user-facing cluster operations.
    Never use global get_clusters() directly - it bypasses KB isolation.

    Args:
        kb_id: Knowledge base ID from get_user_default_kb_id()

    Returns:
        Dict[cluster_id, Cluster] for clusters in this KB only
    """
    if kb_id not in clusters:
        clusters[kb_id] = {}
    return clusters[kb_id]

def get_kb_doc_ids(kb_id: str) -> list:
    """
    Get list of document IDs in a knowledge base (for vector store filtering).

    Used primarily for search operations to scope vector similarity searches.

    Args:
        kb_id: Knowledge base ID from get_user_default_kb_id()

    Returns:
        List of doc_ids in this KB
    """
    if kb_id not in documents:
        return []
    return list(documents[kb_id].keys())

def ensure_kb_exists(kb_id: str) -> None:
    """
    Ensure knowledge base exists in all in-memory dictionaries.

    Called during KB creation and on startup when loading from database.
    Creates empty containers if KB namespace doesn't exist.

    Args:
        kb_id: Knowledge base ID to initialize
    """
    if kb_id not in documents:
        documents[kb_id] = {}
    if kb_id not in metadata:
        metadata[kb_id] = {}
    if kb_id not in clusters:
        clusters[kb_id] = {}


# =============================================================================
# Database-dependent helpers (imported when needed)
# =============================================================================

def get_user_default_kb_id(username: str, db) -> str:
    """Get user's default knowledge base ID from database.

    Args:
        username: The username
        db: Database session

    Returns:
        KB ID string, or creates default KB if none exists
    """
    from .db_models import DBKnowledgeBase
    import uuid
    from datetime import datetime

    # Find user's default KB
    default_kb = db.query(DBKnowledgeBase).filter(
        DBKnowledgeBase.owner_username == username,
        DBKnowledgeBase.is_default == True
    ).first()

    if default_kb:
        return default_kb.id

    # No default KB - check if user has any KBs
    any_kb = db.query(DBKnowledgeBase).filter(
        DBKnowledgeBase.owner_username == username
    ).first()

    if any_kb:
        # Make the first one default
        any_kb.is_default = True
        db.commit()
        return any_kb.id

    # Create default KB for user
    kb_id = str(uuid.uuid4())
    new_kb = DBKnowledgeBase(
        id=kb_id,
        name="Main Knowledge Base",
        description="Default knowledge base for all your documents",
        owner_username=username,
        is_default=True,
        document_count=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(new_kb)
    db.commit()

    # Ensure in-memory structure exists
    ensure_kb_exists(kb_id)

    return kb_id
