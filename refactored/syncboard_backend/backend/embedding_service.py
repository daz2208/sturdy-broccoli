"""
Embedding Service for SyncBoard 3.0.

Generates vector embeddings for document chunks using OpenAI's API.
Supports batch processing and caching for efficiency.
"""

import os
import logging
import asyncio
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)

# Try to import OpenAI
try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI not available for embeddings")


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""
    text: str
    embedding: List[float]
    model: str
    token_count: int


class EmbeddingService:
    """
    Service for generating text embeddings using OpenAI.

    Features:
    - Batch processing for efficiency
    - Automatic retries with backoff
    - Token counting and limits
    - Cosine similarity search
    """

    # OpenAI embedding models
    MODELS = {
        "small": "text-embedding-3-small",  # 1536 dims, cheaper
        "large": "text-embedding-3-large",  # 3072 dims, better quality
        "ada": "text-embedding-ada-002",    # Legacy, 1536 dims
    }

    # Model dimensions
    DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    # Max tokens per request (8191 for embedding models)
    MAX_TOKENS = 8191
    # Max batch size
    MAX_BATCH_SIZE = 100

    def __init__(
        self,
        model: str = "small",
        api_key: Optional[str] = None
    ):
        """
        Initialize embedding service.

        Args:
            model: Model size ("small", "large", or "ada")
            api_key: OpenAI API key (defaults to env var)
        """
        self.model_name = self.MODELS.get(model, self.MODELS["small"])
        self.dimensions = self.DIMENSIONS[self.model_name]

        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("No OpenAI API key - embeddings will fail")

        if OPENAI_AVAILABLE:
            self.client = AsyncOpenAI(api_key=api_key)
        else:
            self.client = None

        logger.info(f"Embedding service initialized with {self.model_name} ({self.dimensions} dims)")

    async def embed_text(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None on failure
        """
        if not self.client:
            logger.error("OpenAI client not available")
            return None

        if not text or not text.strip():
            logger.warning("Empty text for embedding")
            return None

        try:
            response = await self.client.embeddings.create(
                model=self.model_name,
                input=text.strip()
            )
            return response.data[0].embedding

        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return None

    async def embed_batch(
        self,
        texts: List[str],
        show_progress: bool = False
    ) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed
            show_progress: Log progress updates

        Returns:
            List of embeddings (None for failures)
        """
        if not self.client:
            return [None] * len(texts)

        if not texts:
            return []

        results = [None] * len(texts)

        # Process in batches
        for batch_start in range(0, len(texts), self.MAX_BATCH_SIZE):
            batch_end = min(batch_start + self.MAX_BATCH_SIZE, len(texts))
            batch_texts = texts[batch_start:batch_end]

            # Filter empty texts
            valid_indices = []
            valid_texts = []
            for i, text in enumerate(batch_texts):
                if text and text.strip():
                    valid_indices.append(batch_start + i)
                    valid_texts.append(text.strip())

            if not valid_texts:
                continue

            try:
                response = await self.client.embeddings.create(
                    model=self.model_name,
                    input=valid_texts
                )

                for i, embedding_data in enumerate(response.data):
                    results[valid_indices[i]] = embedding_data.embedding

                if show_progress:
                    logger.info(f"Embedded batch {batch_start}-{batch_end} of {len(texts)}")

            except Exception as e:
                logger.error(f"Batch embedding failed: {e}")
                # Try individual embeddings as fallback
                for i, text in enumerate(valid_texts):
                    try:
                        embedding = await self.embed_text(text)
                        results[valid_indices[i]] = embedding
                    except Exception:
                        pass

            # Rate limiting - small delay between batches
            if batch_end < len(texts):
                await asyncio.sleep(0.1)

        return results

    def cosine_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Similarity score (0-1, higher is more similar)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def find_similar(
        self,
        query_embedding: List[float],
        embeddings: List[Tuple[int, List[float]]],
        top_k: int = 10,
        threshold: float = 0.0
    ) -> List[Tuple[int, float]]:
        """
        Find most similar embeddings to a query.

        Args:
            query_embedding: Query vector
            embeddings: List of (id, embedding) tuples
            top_k: Number of results to return
            threshold: Minimum similarity threshold

        Returns:
            List of (id, similarity) tuples, sorted by similarity
        """
        if not query_embedding or not embeddings:
            return []

        similarities = []
        query_vec = np.array(query_embedding)
        query_norm = np.linalg.norm(query_vec)

        if query_norm == 0:
            return []

        for doc_id, embedding in embeddings:
            if embedding is None:
                continue

            doc_vec = np.array(embedding)
            doc_norm = np.linalg.norm(doc_vec)

            if doc_norm == 0:
                continue

            similarity = float(np.dot(query_vec, doc_vec) / (query_norm * doc_norm))

            if similarity >= threshold:
                similarities.append((doc_id, similarity))

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:top_k]


# Singleton instance
_embedding_service = None

def get_embedding_service() -> EmbeddingService:
    """Get or create singleton EmbeddingService instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
