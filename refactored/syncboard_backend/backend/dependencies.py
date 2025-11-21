"""
Shared Dependencies for SyncBoard 3.0 Knowledge Bank.

Provides:
- Global state access (documents, metadata, clusters, users)
- Authentication dependencies (get_current_user)
- Storage lock for thread safety
- Service instances
"""

import os
import asyncio
from typing import Dict
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from .models import User, DocumentMetadata, Cluster
from .vector_store import VectorStore
from .concept_extractor import ConceptExtractor
from .clustering_improved import ImprovedClusteringEngine
from .image_processor import ImageProcessor
from .build_suggester_improved import ImprovedBuildSuggester
from .semantic_dictionary import SemanticDictionaryManager
from .llm_providers import OpenAIProvider
from .auth import decode_access_token
from .constants import DEFAULT_VECTOR_DIM

# =============================================================================
# OAuth2 Scheme
# =============================================================================

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# =============================================================================
# Global State
# =============================================================================

# Vector store for semantic search (shared across all KBs, filtered by allowed_doc_ids)
vector_store = VectorStore(dim=int(os.environ.get('SYNCBOARD_VECTOR_DIM', str(DEFAULT_VECTOR_DIM))))

# Document storage (in-memory) - nested by knowledge_base_id
# Structure: {kb_id: {doc_id: content/metadata/cluster}}
documents: Dict[str, Dict[int, str]] = {}
metadata: Dict[str, Dict[int, DocumentMetadata]] = {}
clusters: Dict[str, Dict[int, Cluster]] = {}
users: Dict[str, str] = {}  # username -> hashed_password

# Storage lock for thread safety
storage_lock = asyncio.Lock()

# =============================================================================
# Service Instances
# =============================================================================

# LLM Provider (optional - only for semantic learning)
llm_provider = None
try:
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        llm_provider = OpenAIProvider(api_key=api_key)
except Exception:
    pass  # LLM provider is optional - system works without it

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
# State Access Functions
# =============================================================================

def get_documents() -> Dict[str, Dict[int, str]]:
    """Get all documents dictionary (nested by kb_id)."""
    return documents

def get_metadata() -> Dict[str, Dict[int, DocumentMetadata]]:
    """Get all metadata dictionary (nested by kb_id)."""
    return metadata

def get_clusters() -> Dict[str, Dict[int, Cluster]]:
    """Get all clusters dictionary (nested by kb_id)."""
    return clusters

def get_users() -> Dict[str, str]:
    """Get users dictionary."""
    return users

def get_vector_store() -> VectorStore:
    """Get vector store instance."""
    return vector_store

def get_storage_lock() -> asyncio.Lock:
    """Get storage lock for thread-safe operations."""
    return storage_lock

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

def get_kb_documents(kb_id: str) -> Dict[int, str]:
    """Get documents for a specific knowledge base."""
    if kb_id not in documents:
        documents[kb_id] = {}
    return documents[kb_id]

def get_kb_metadata(kb_id: str) -> Dict[int, DocumentMetadata]:
    """Get metadata for a specific knowledge base."""
    if kb_id not in metadata:
        metadata[kb_id] = {}
    return metadata[kb_id]

def get_kb_clusters(kb_id: str) -> Dict[int, Cluster]:
    """Get clusters for a specific knowledge base."""
    if kb_id not in clusters:
        clusters[kb_id] = {}
    return clusters[kb_id]

def get_kb_doc_ids(kb_id: str) -> list:
    """Get list of document IDs in a knowledge base (for vector store filtering)."""
    if kb_id not in documents:
        return []
    return list(documents[kb_id].keys())

def ensure_kb_exists(kb_id: str) -> None:
    """Ensure knowledge base exists in all dictionaries."""
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
