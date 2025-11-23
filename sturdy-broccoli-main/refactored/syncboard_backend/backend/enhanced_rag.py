"""
Enhanced RAG (Retrieval-Augmented Generation) System for SyncBoard 3.0.

This module implements production-grade RAG with:
1. pgvector - Native PostgreSQL vector storage and search
2. Hybrid Search - Combines TF-IDF lexical + embedding semantic search
3. Cross-Encoder Reranking - Uses sentence-transformers for precise reranking
4. Parent-Child Chunking - Small chunks for retrieval, larger for context
5. Query Expansion - LLM-powered query enhancement before retrieval

Usage:
    from backend.enhanced_rag import EnhancedRAGService

    rag = EnhancedRAGService(db_session)
    response = await rag.generate(
        query="How do I implement authentication?",
        user_id="username",
        kb_id="knowledge-base-id"
    )
"""

import os
import logging
import asyncio
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np

from sqlalchemy import text, func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

@dataclass
class RAGConfig:
    """Configuration for the enhanced RAG system."""
    # Retrieval settings
    initial_retrieval_k: int = 50  # How many to fetch initially
    rerank_top_k: int = 10  # How many to keep after reranking
    min_similarity_threshold: float = 0.3

    # Hybrid search weights (must sum to 1.0)
    embedding_weight: float = 0.7
    tfidf_weight: float = 0.3

    # Parent-child chunking
    child_chunk_tokens: int = 256  # Small chunks for precise retrieval
    parent_chunk_tokens: int = 1024  # Larger chunks for context
    chunk_overlap_tokens: int = 50

    # Query expansion
    enable_query_expansion: bool = True
    max_expanded_queries: int = 3

    # Reranking
    enable_reranking: bool = True
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Generation
    max_context_tokens: int = 100000
    generation_model: str = "gpt-4o-mini"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class RetrievedChunk:
    """A chunk retrieved from the knowledge base."""
    chunk_id: int
    document_id: int
    content: str

    # Scores
    embedding_score: float = 0.0
    tfidf_score: float = 0.0
    hybrid_score: float = 0.0
    rerank_score: float = 0.0
    final_score: float = 0.0

    # Metadata
    filename: Optional[str] = None
    source_url: Optional[str] = None
    source_type: str = "unknown"
    chunk_index: int = 0

    # Parent chunk for expanded context
    parent_content: Optional[str] = None
    parent_chunk_id: Optional[int] = None


@dataclass
class RAGResponse:
    """Response from the RAG system."""
    answer: str
    chunks_used: List[RetrievedChunk]
    query_expanded: Optional[List[str]] = None
    retrieval_time_ms: float = 0.0
    rerank_time_ms: float = 0.0
    generation_time_ms: float = 0.0
    total_time_ms: float = 0.0
    model_used: str = ""


@dataclass
class Citation:
    """Structured citation for RAG response."""
    doc_id: int
    chunk_id: Optional[int]
    filename: Optional[str]
    source_url: Optional[str]
    source_type: str
    relevance: float
    snippet: str


# =============================================================================
# pgvector Integration
# =============================================================================

class PgVectorStore:
    """
    Native PostgreSQL vector storage using pgvector extension.

    Provides efficient similarity search directly in the database,
    eliminating the need for in-memory vector stores.
    """

    def __init__(self, db: Session):
        self.db = db
        self._extension_enabled = None

    def ensure_extension(self) -> bool:
        """Enable pgvector extension if not already enabled."""
        if self._extension_enabled is not None:
            return self._extension_enabled

        try:
            self.db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            self.db.commit()
            self._extension_enabled = True
            logger.info("pgvector extension enabled")
        except Exception as e:
            logger.warning(f"Could not enable pgvector: {e}")
            self._extension_enabled = False

        return self._extension_enabled

    def search_similar(
        self,
        query_embedding: List[float],
        kb_id: str,
        top_k: int = 50,
        min_similarity: float = 0.3
    ) -> List[Tuple[int, int, str, float]]:
        """
        Search for similar chunks using pgvector's cosine similarity.

        Returns:
            List of (chunk_id, document_id, content, similarity_score)
        """
        if not self.ensure_extension():
            return []

        # Convert embedding to PostgreSQL vector format
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        query = text("""
            SELECT
                dc.id as chunk_id,
                dc.document_id,
                dc.content,
                1 - (dc.embedding_vector <=> :query_vec::vector) as similarity
            FROM document_chunks dc
            WHERE dc.knowledge_base_id = :kb_id
              AND dc.embedding_vector IS NOT NULL
              AND 1 - (dc.embedding_vector <=> :query_vec::vector) >= :min_sim
            ORDER BY dc.embedding_vector <=> :query_vec::vector
            LIMIT :top_k
        """)

        try:
            result = self.db.execute(query, {
                "query_vec": embedding_str,
                "kb_id": kb_id,
                "min_sim": min_similarity,
                "top_k": top_k
            })

            return [(row.chunk_id, row.document_id, row.content, row.similarity)
                    for row in result]
        except Exception as e:
            logger.error(f"pgvector search failed: {e}")
            return []


# =============================================================================
# Hybrid Search
# =============================================================================

class HybridSearcher:
    """
    Combines TF-IDF lexical search with embedding-based semantic search.

    Benefits:
    - TF-IDF catches exact keyword matches (good for technical terms)
    - Embeddings capture semantic meaning (good for paraphrases)
    - Combined scoring improves overall retrieval quality
    """

    def __init__(
        self,
        db: Session,
        embedding_weight: float = 0.7,
        tfidf_weight: float = 0.3
    ):
        self.db = db
        self.embedding_weight = embedding_weight
        self.tfidf_weight = tfidf_weight
        self.pgvector = PgVectorStore(db)

        # Lazy-load TF-IDF vectorizer
        self._tfidf_vectorizer = None
        self._tfidf_matrix = None
        self._chunk_ids = None

    def _build_tfidf_index(self, kb_id: str) -> None:
        """Build TF-IDF index for a knowledge base."""
        from sklearn.feature_extraction.text import TfidfVectorizer

        # Fetch all chunks for this KB
        query = text("""
            SELECT id, content FROM document_chunks
            WHERE knowledge_base_id = :kb_id
            ORDER BY id
        """)
        result = self.db.execute(query, {"kb_id": kb_id})
        rows = list(result)

        if not rows:
            return

        self._chunk_ids = [row.id for row in rows]
        texts = [row.content for row in rows]

        self._tfidf_vectorizer = TfidfVectorizer(
            max_features=10000,
            ngram_range=(1, 2),  # Unigrams and bigrams
            stop_words='english'
        )
        self._tfidf_matrix = self._tfidf_vectorizer.fit_transform(texts)
        logger.info(f"Built TF-IDF index with {len(texts)} chunks")

    def _tfidf_search(
        self,
        query: str,
        kb_id: str,
        top_k: int = 50
    ) -> Dict[int, float]:
        """Search using TF-IDF and return chunk_id -> score mapping."""
        from sklearn.metrics.pairwise import cosine_similarity

        if self._tfidf_vectorizer is None:
            self._build_tfidf_index(kb_id)

        if self._tfidf_vectorizer is None:
            return {}

        query_vec = self._tfidf_vectorizer.transform([query])
        scores = cosine_similarity(self._tfidf_matrix, query_vec).flatten()

        # Get top-k by score
        top_indices = np.argsort(scores)[-top_k:][::-1]

        return {
            self._chunk_ids[idx]: float(scores[idx])
            for idx in top_indices
            if scores[idx] > 0
        }

    async def search(
        self,
        query: str,
        query_embedding: List[float],
        kb_id: str,
        top_k: int = 50,
        min_similarity: float = 0.3
    ) -> List[RetrievedChunk]:
        """
        Perform hybrid search combining embeddings and TF-IDF.

        Returns chunks sorted by combined score.
        """
        # Get embedding-based results
        embedding_results = self.pgvector.search_similar(
            query_embedding, kb_id, top_k * 2, min_similarity
        )

        # Get TF-IDF results
        tfidf_scores = self._tfidf_search(query, kb_id, top_k * 2)

        # Normalize scores to [0, 1]
        max_embedding_score = max((r[3] for r in embedding_results), default=1.0)
        max_tfidf_score = max(tfidf_scores.values(), default=1.0)

        # Combine results
        chunks_map: Dict[int, RetrievedChunk] = {}

        # Add embedding results
        for chunk_id, doc_id, content, score in embedding_results:
            normalized_score = score / max_embedding_score if max_embedding_score > 0 else 0
            chunks_map[chunk_id] = RetrievedChunk(
                chunk_id=chunk_id,
                document_id=doc_id,
                content=content,
                embedding_score=normalized_score
            )

        # Add TF-IDF scores
        for chunk_id, score in tfidf_scores.items():
            normalized_score = score / max_tfidf_score if max_tfidf_score > 0 else 0
            if chunk_id in chunks_map:
                chunks_map[chunk_id].tfidf_score = normalized_score
            else:
                # Need to fetch content for TF-IDF-only results
                query = text("SELECT document_id, content FROM document_chunks WHERE id = :id")
                result = self.db.execute(query, {"id": chunk_id}).fetchone()
                if result:
                    chunks_map[chunk_id] = RetrievedChunk(
                        chunk_id=chunk_id,
                        document_id=result.document_id,
                        content=result.content,
                        tfidf_score=normalized_score
                    )

        # Calculate hybrid scores
        for chunk in chunks_map.values():
            chunk.hybrid_score = (
                self.embedding_weight * chunk.embedding_score +
                self.tfidf_weight * chunk.tfidf_score
            )
            chunk.final_score = chunk.hybrid_score

        # Sort by hybrid score and return top-k
        results = sorted(chunks_map.values(), key=lambda x: x.hybrid_score, reverse=True)
        return results[:top_k]


# =============================================================================
# Cross-Encoder Reranker
# =============================================================================

class CrossEncoderReranker:
    """
    Reranks retrieval results using a cross-encoder model.

    Cross-encoders are more accurate than bi-encoders because they
    see the query and document together, allowing for better
    understanding of their relationship.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        """Lazy-load the cross-encoder model."""
        if self._model is not None:
            return

        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
            logger.info(f"Loaded cross-encoder model: {self.model_name}")
        except ImportError:
            logger.warning("sentence-transformers not installed, reranking disabled")
        except Exception as e:
            logger.error(f"Failed to load cross-encoder: {e}")

    def rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        top_k: int = 10
    ) -> List[RetrievedChunk]:
        """
        Rerank chunks using the cross-encoder.

        Args:
            query: The user's query
            chunks: Retrieved chunks to rerank
            top_k: Number of top results to return

        Returns:
            Reranked and filtered list of chunks
        """
        if not chunks:
            return []

        self._load_model()

        if self._model is None:
            # Fallback: return chunks sorted by hybrid score
            return sorted(chunks, key=lambda x: x.hybrid_score, reverse=True)[:top_k]

        # Prepare query-document pairs
        pairs = [(query, chunk.content) for chunk in chunks]

        try:
            # Get cross-encoder scores
            scores = self._model.predict(pairs)

            # Update chunk scores
            for chunk, score in zip(chunks, scores):
                chunk.rerank_score = float(score)
                # Final score is primarily rerank score, with small boost from hybrid
                chunk.final_score = chunk.rerank_score * 0.8 + chunk.hybrid_score * 0.2

            # Sort by final score
            reranked = sorted(chunks, key=lambda x: x.final_score, reverse=True)
            return reranked[:top_k]

        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return sorted(chunks, key=lambda x: x.hybrid_score, reverse=True)[:top_k]


# =============================================================================
# Query Expansion
# =============================================================================

class QueryExpander:
    """
    Expands user queries using LLM to improve retrieval.

    Techniques:
    - Synonym expansion
    - Hypothetical document generation (HyDE-lite)
    - Multi-perspective queries
    """

    def __init__(self):
        self._client = None

    def _get_client(self):
        """Lazy-load OpenAI client."""
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return self._client

    async def expand(
        self,
        query: str,
        max_expansions: int = 3
    ) -> List[str]:
        """
        Expand a query into multiple search queries.

        Args:
            query: Original user query
            max_expansions: Maximum number of expanded queries

        Returns:
            List of expanded queries (including original)
        """
        client = self._get_client()

        prompt = f"""Given the user's search query, generate {max_expansions - 1} alternative search queries that would help find relevant information.

The alternatives should:
1. Use synonyms and related terms
2. Rephrase the question differently
3. Be more specific or more general as appropriate

Original query: "{query}"

Return ONLY the alternative queries, one per line, no numbering or explanations."""

        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=200
            )

            expansions = response.choices[0].message.content.strip().split("\n")
            expansions = [q.strip() for q in expansions if q.strip()]

            # Always include original query first
            return [query] + expansions[:max_expansions - 1]

        except Exception as e:
            logger.error(f"Query expansion failed: {e}")
            return [query]


# =============================================================================
# Parent-Child Chunking
# =============================================================================

class ParentChildChunker:
    """
    Implements parent-child chunking strategy.

    - Small "child" chunks are used for precise retrieval
    - When a child chunk is retrieved, its larger "parent" chunk
      provides more context for generation
    """

    def __init__(
        self,
        child_tokens: int = 256,
        parent_tokens: int = 1024,
        overlap_tokens: int = 50
    ):
        self.child_tokens = child_tokens
        self.parent_tokens = parent_tokens
        self.overlap_tokens = overlap_tokens

        # Load tiktoken for accurate counting
        try:
            import tiktoken
            self._encoding = tiktoken.get_encoding("cl100k_base")
        except ImportError:
            self._encoding = None
            logger.warning("tiktoken not available, using character estimation")

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if self._encoding:
            return len(self._encoding.encode(text))
        return len(text) // 4

    def chunk_document(
        self,
        content: str,
        doc_id: int
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Split document into parent and child chunks.

        Returns:
            Tuple of (parent_chunks, child_chunks)
            Each chunk is a dict with 'content', 'index', 'token_count'
        """
        # First create parent chunks
        parent_chunks = self._create_chunks(content, self.parent_tokens)

        # Then create child chunks with parent references
        child_chunks = []
        for parent_idx, parent in enumerate(parent_chunks):
            children = self._create_chunks(
                parent['content'],
                self.child_tokens,
                base_index=len(child_chunks)
            )
            for child in children:
                child['parent_index'] = parent_idx
            child_chunks.extend(children)

        return parent_chunks, child_chunks

    def _create_chunks(
        self,
        content: str,
        target_tokens: int,
        base_index: int = 0
    ) -> List[Dict]:
        """Create chunks of approximately target_tokens size."""
        chunks = []

        # Split by paragraphs first
        paragraphs = content.split("\n\n")

        current_chunk = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = self.count_tokens(para)

            if current_tokens + para_tokens > target_tokens and current_chunk:
                # Save current chunk
                chunk_content = "\n\n".join(current_chunk)
                chunks.append({
                    'content': chunk_content,
                    'index': base_index + len(chunks),
                    'token_count': current_tokens
                })

                # Start new chunk with overlap
                overlap_text = current_chunk[-1] if current_chunk else ""
                current_chunk = [overlap_text] if overlap_text else []
                current_tokens = self.count_tokens(overlap_text) if overlap_text else 0

            current_chunk.append(para)
            current_tokens += para_tokens

        # Don't forget last chunk
        if current_chunk:
            chunk_content = "\n\n".join(current_chunk)
            chunks.append({
                'content': chunk_content,
                'index': base_index + len(chunks),
                'token_count': self.count_tokens(chunk_content)
            })

        return chunks

    def get_parent_context(
        self,
        chunks: List[RetrievedChunk],
        db: Session
    ) -> List[RetrievedChunk]:
        """
        Enrich retrieved child chunks with their parent content.

        This provides more context for generation without affecting
        retrieval precision.
        """
        for chunk in chunks:
            # Try to get parent chunk
            query = text("""
                SELECT pc.content, pc.id
                FROM document_chunks pc
                JOIN document_chunks cc ON cc.parent_chunk_id = pc.id
                WHERE cc.id = :chunk_id
            """)

            try:
                result = db.execute(query, {"chunk_id": chunk.chunk_id}).fetchone()
                if result:
                    chunk.parent_content = result.content
                    chunk.parent_chunk_id = result.id
            except Exception as e:
                logger.debug(f"Could not get parent chunk: {e}")

        return chunks


# =============================================================================
# Main Enhanced RAG Service
# =============================================================================

class EnhancedRAGService:
    """
    Production-grade RAG service combining all improvements.

    Usage:
        rag = EnhancedRAGService(db_session)
        response = await rag.generate(
            query="How do I implement auth?",
            user_id="john",
            kb_id="my-kb-id"
        )
    """

    def __init__(
        self,
        db: Session,
        config: Optional[RAGConfig] = None
    ):
        self.db = db
        self.config = config or RAGConfig()

        # Initialize components
        self.hybrid_searcher = HybridSearcher(
            db,
            embedding_weight=self.config.embedding_weight,
            tfidf_weight=self.config.tfidf_weight
        )
        self.reranker = CrossEncoderReranker(self.config.reranker_model)
        self.query_expander = QueryExpander()
        self.parent_child_chunker = ParentChildChunker(
            child_tokens=self.config.child_chunk_tokens,
            parent_tokens=self.config.parent_chunk_tokens,
            overlap_tokens=self.config.chunk_overlap_tokens
        )

        # Embedding service (lazy loaded)
        self._embedding_service = None

    async def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding for text using the embedding service."""
        if self._embedding_service is None:
            from .embedding_service import get_embedding_service
            self._embedding_service = get_embedding_service()

        return await self._embedding_service.embed_text(text)

    async def generate(
        self,
        query: str,
        user_id: str,
        kb_id: str,
        model: Optional[str] = None
    ) -> RAGResponse:
        """
        Generate a response using the enhanced RAG pipeline.

        Pipeline:
        1. Query Expansion (optional)
        2. Hybrid Search (embedding + TF-IDF)
        3. Cross-Encoder Reranking
        4. Parent Context Enrichment
        5. LLM Generation with Citations

        Args:
            query: User's question
            user_id: User identifier for access control
            kb_id: Knowledge base to search
            model: LLM model for generation (default from config)

        Returns:
            RAGResponse with answer, citations, and timing info
        """
        import time
        start_time = time.time()

        model = model or self.config.generation_model
        expanded_queries = [query]

        # Step 1: Query Expansion
        if self.config.enable_query_expansion:
            expanded_queries = await self.query_expander.expand(
                query, self.config.max_expanded_queries
            )
            logger.info(f"Expanded query to {len(expanded_queries)} variants")

        # Step 2: Hybrid Search with all query variants
        retrieval_start = time.time()
        all_chunks: Dict[int, RetrievedChunk] = {}

        for exp_query in expanded_queries:
            # Get embedding for this query variant
            query_embedding = await self._get_embedding(exp_query)
            if not query_embedding:
                continue

            # Search with this variant
            chunks = await self.hybrid_searcher.search(
                exp_query,
                query_embedding,
                kb_id,
                top_k=self.config.initial_retrieval_k,
                min_similarity=self.config.min_similarity_threshold
            )

            # Merge results (keep best score per chunk)
            for chunk in chunks:
                if chunk.chunk_id not in all_chunks:
                    all_chunks[chunk.chunk_id] = chunk
                elif chunk.hybrid_score > all_chunks[chunk.chunk_id].hybrid_score:
                    all_chunks[chunk.chunk_id] = chunk

        retrieval_time = (time.time() - retrieval_start) * 1000
        retrieved_chunks = list(all_chunks.values())
        logger.info(f"Retrieved {len(retrieved_chunks)} unique chunks")

        # Step 3: Cross-Encoder Reranking
        rerank_start = time.time()
        if self.config.enable_reranking and retrieved_chunks:
            retrieved_chunks = self.reranker.rerank(
                query,
                retrieved_chunks,
                top_k=self.config.rerank_top_k
            )
        rerank_time = (time.time() - rerank_start) * 1000
        logger.info(f"Reranked to {len(retrieved_chunks)} chunks")

        # Step 4: Enrich with parent context
        retrieved_chunks = self.parent_child_chunker.get_parent_context(
            retrieved_chunks, self.db
        )

        # Step 5: Enrich with document metadata
        retrieved_chunks = await self._enrich_metadata(retrieved_chunks)

        # Step 6: Generate response
        gen_start = time.time()
        answer = await self._generate_answer(query, retrieved_chunks, model)
        gen_time = (time.time() - gen_start) * 1000

        total_time = (time.time() - start_time) * 1000

        return RAGResponse(
            answer=answer,
            chunks_used=retrieved_chunks,
            query_expanded=expanded_queries if len(expanded_queries) > 1 else None,
            retrieval_time_ms=retrieval_time,
            rerank_time_ms=rerank_time,
            generation_time_ms=gen_time,
            total_time_ms=total_time,
            model_used=model
        )

    async def _enrich_metadata(
        self,
        chunks: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
        """Add document metadata to chunks."""
        if not chunks:
            return chunks

        doc_ids = list(set(c.document_id for c in chunks))

        query = text("""
            SELECT doc_id, filename, source_url, source_type
            FROM documents
            WHERE doc_id = ANY(:doc_ids)
        """)

        try:
            result = self.db.execute(query, {"doc_ids": doc_ids})
            metadata = {row.doc_id: row for row in result}

            for chunk in chunks:
                if chunk.document_id in metadata:
                    meta = metadata[chunk.document_id]
                    chunk.filename = meta.filename
                    chunk.source_url = meta.source_url
                    chunk.source_type = meta.source_type
        except Exception as e:
            logger.warning(f"Could not enrich metadata: {e}")

        return chunks

    async def _generate_answer(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        model: str
    ) -> str:
        """Generate answer using LLM with retrieved context."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Build context from chunks
        context_parts = []
        for i, chunk in enumerate(chunks):
            # Use parent content if available for richer context
            content = chunk.parent_content or chunk.content

            header = f"[Source {i+1}"
            if chunk.filename:
                header += f" | {chunk.filename}"
            elif chunk.source_url:
                url = chunk.source_url[:50] + "..." if len(chunk.source_url) > 50 else chunk.source_url
                header += f" | {url}"
            header += f" | Relevance: {chunk.final_score:.2f}]"

            context_parts.append(f"{header}\n{content}")

        context = "\n\n---\n\n".join(context_parts)

        system_message = """You are an AI assistant helping users with their knowledge bank.
You have access to relevant documents and must use them to provide accurate responses.

IMPORTANT RULES:
1. ALWAYS cite your sources using [Source N] format
2. If multiple sources support a point, cite all of them
3. If you cannot find relevant information, say so clearly
4. Synthesize information from multiple sources when appropriate
5. Be concise but thorough

The sources are sorted by relevance to the user's question."""

        user_message = f"""Based on these sources from my knowledge bank:

{context}

---

Question: {query}

Please provide a comprehensive answer with citations."""

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=4000
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return f"Error generating response: {str(e)}"


# =============================================================================
# Database Migration Helper
# =============================================================================

def get_pgvector_migration_sql() -> str:
    """
    Returns SQL to set up pgvector for the enhanced RAG system.

    Run this migration after enabling the pgvector extension:
    1. Execute 'CREATE EXTENSION IF NOT EXISTS vector'
    2. Run this migration SQL
    """
    return """
-- Add vector column to document_chunks table
ALTER TABLE document_chunks
ADD COLUMN IF NOT EXISTS embedding_vector vector(1536);

-- Add parent-child relationship column
ALTER TABLE document_chunks
ADD COLUMN IF NOT EXISTS parent_chunk_id INTEGER REFERENCES document_chunks(id);

-- Add chunk type column (parent vs child)
ALTER TABLE document_chunks
ADD COLUMN IF NOT EXISTS chunk_type VARCHAR(20) DEFAULT 'child';

-- Create index for vector similarity search (IVFFlat for large datasets)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_vector
ON document_chunks
USING ivfflat (embedding_vector vector_cosine_ops)
WITH (lists = 100);

-- Index for parent-child lookups
CREATE INDEX IF NOT EXISTS idx_chunks_parent
ON document_chunks(parent_chunk_id);

-- Index for chunk type filtering
CREATE INDEX IF NOT EXISTS idx_chunks_type
ON document_chunks(chunk_type);
"""


# =============================================================================
# Convenience Functions
# =============================================================================

def create_enhanced_rag_service(db: Session, config: Optional[RAGConfig] = None) -> EnhancedRAGService:
    """Factory function to create an EnhancedRAGService instance."""
    return EnhancedRAGService(db, config)


async def quick_rag_query(
    db: Session,
    query: str,
    user_id: str,
    kb_id: str
) -> str:
    """
    Quick helper for simple RAG queries.

    Returns just the answer text for simple use cases.
    """
    service = create_enhanced_rag_service(db)
    response = await service.generate(query, user_id, kb_id)
    return response.answer
