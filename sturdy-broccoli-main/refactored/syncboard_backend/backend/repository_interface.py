"""
Abstract Repository Interface for Knowledge Bank (Proposal #1).

Defines the contract that all repository implementations must follow.
This allows for clean separation between business logic and data access.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from .models import DocumentMetadata, Cluster, Concept
from .vector_store import VectorStore


class KnowledgeBankRepository(ABC):
    """
    Abstract base class for Knowledge Bank data access.

    All repository implementations must implement these methods.
    This interface supports both file-based and database-backed storage.
    """

    # =============================================================================
    # ABSTRACT PROPERTIES
    # =============================================================================

    @property
    @abstractmethod
    def vector_store(self) -> VectorStore:
        """Get the vector store instance for semantic search."""
        pass

    # =============================================================================
    # DOCUMENT OPERATIONS
    # =============================================================================

    @abstractmethod
    async def add_document(
        self,
        content: str,
        metadata: DocumentMetadata
    ) -> int:
        """
        Add a document to the repository.

        Args:
            content: Full document text
            metadata: Document metadata

        Returns:
            Document ID
        """
        pass

    @abstractmethod
    async def get_document(self, doc_id: int) -> Optional[str]:
        """
        Get document content by ID.

        Args:
            doc_id: Document ID

        Returns:
            Document content or None if not found
        """
        pass

    @abstractmethod
    async def get_document_metadata(self, doc_id: int) -> Optional[DocumentMetadata]:
        """
        Get document metadata by ID.

        Args:
            doc_id: Document ID

        Returns:
            DocumentMetadata or None if not found
        """
        pass

    @abstractmethod
    async def get_all_documents(self) -> Dict[int, str]:
        """
        Get all documents.

        Returns:
            Dictionary mapping doc_id to content
        """
        pass

    @abstractmethod
    async def get_all_metadata(self) -> Dict[int, DocumentMetadata]:
        """
        Get all document metadata.

        Returns:
            Dictionary mapping doc_id to metadata
        """
        pass

    @abstractmethod
    async def delete_document(self, doc_id: int) -> bool:
        """
        Delete a document.

        Args:
            doc_id: Document ID

        Returns:
            True if deleted, False if not found
        """
        pass

    # =============================================================================
    # CLUSTER OPERATIONS
    # =============================================================================

    @abstractmethod
    async def add_cluster(self, cluster: Cluster) -> int:
        """
        Add a cluster.

        Args:
            cluster: Cluster object

        Returns:
            Cluster ID
        """
        pass

    @abstractmethod
    async def get_cluster(self, cluster_id: int) -> Optional[Cluster]:
        """
        Get cluster by ID.

        Args:
            cluster_id: Cluster ID

        Returns:
            Cluster or None if not found
        """
        pass

    @abstractmethod
    async def get_all_clusters(self) -> Dict[int, Cluster]:
        """
        Get all clusters.

        Returns:
            Dictionary mapping cluster_id to Cluster
        """
        pass

    @abstractmethod
    async def update_cluster(self, cluster: Cluster) -> bool:
        """
        Update an existing cluster.

        Args:
            cluster: Updated cluster object

        Returns:
            True if updated, False if not found
        """
        pass

    @abstractmethod
    async def delete_cluster(self, cluster_id: int) -> bool:
        """
        Delete a cluster.

        Args:
            cluster_id: Cluster ID

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def add_document_to_cluster(self, doc_id: int, cluster_id: int) -> bool:
        """
        Add a document to a cluster.

        Args:
            doc_id: Document ID
            cluster_id: Cluster ID

        Returns:
            True if successful
        """
        pass

    # =============================================================================
    # USER OPERATIONS
    # =============================================================================

    @abstractmethod
    async def add_user(self, username: str, hashed_password: str) -> None:
        """
        Add a user.

        Args:
            username: Username
            hashed_password: Bcrypt hashed password
        """
        pass

    @abstractmethod
    async def get_user(self, username: str) -> Optional[str]:
        """
        Get user's hashed password.

        Args:
            username: Username

        Returns:
            Hashed password or None if not found
        """
        pass

    # =============================================================================
    # SEARCH OPERATIONS
    # =============================================================================

    @abstractmethod
    async def search_documents(
        self,
        query: str,
        top_k: int = 10,
        cluster_filter: Optional[int] = None
    ) -> List[Tuple[int, float]]:
        """
        Search documents using semantic similarity.

        Args:
            query: Search query
            top_k: Number of results to return
            cluster_filter: Optional cluster ID to filter by

        Returns:
            List of (doc_id, score) tuples
        """
        pass


__all__ = ["KnowledgeBankRepository"]
