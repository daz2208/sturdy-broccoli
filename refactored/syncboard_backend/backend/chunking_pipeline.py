"""
Chunking Pipeline for SyncBoard 3.0.

Orchestrates the document chunking and embedding process:
1. Split document into chunks
2. Generate embeddings for each chunk
3. Store chunks in database
4. Update document status
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from .document_chunker import DocumentChunker, Chunk, get_document_chunker
from .embedding_service import EmbeddingService, get_embedding_service
from .db_models import DBDocument, DBDocumentChunk, DBKnowledgeBase

logger = logging.getLogger(__name__)


class ChunkingPipeline:
    """
    Pipeline for processing documents into searchable chunks.

    Handles the full flow from raw content to indexed chunks with embeddings.
    """

    def __init__(
        self,
        chunker: Optional[DocumentChunker] = None,
        embedding_service: Optional[EmbeddingService] = None
    ):
        """
        Initialize pipeline with services.

        Args:
            chunker: Document chunker instance
            embedding_service: Embedding service instance
        """
        self.chunker = chunker or get_document_chunker()
        self.embedding_service = embedding_service or get_embedding_service()

    async def process_document(
        self,
        db: Session,
        document: DBDocument,
        content: str,
        generate_embeddings: bool = True
    ) -> Dict:
        """
        Process a document: chunk it, embed it, store it.

        Args:
            db: Database session
            document: DBDocument instance
            content: Full document text
            generate_embeddings: Whether to generate embeddings (costs API calls)

        Returns:
            Dict with processing results
        """
        doc_id = document.id
        kb_id = document.knowledge_base_id

        logger.info(f"Processing document {doc_id} for chunking")

        # Update status to processing
        document.chunking_status = "processing"
        db.commit()

        try:
            # Step 1: Chunk the document
            chunks = self.chunker.chunk_document(content, doc_id)

            if not chunks:
                document.chunking_status = "completed"
                document.chunk_count = 0
                db.commit()
                return {"doc_id": doc_id, "chunks": 0, "status": "empty"}

            # Step 2: Generate embeddings (if enabled)
            embeddings = []
            if generate_embeddings:
                chunk_texts = [c.content for c in chunks]
                embeddings = await self.embedding_service.embed_batch(
                    chunk_texts, show_progress=True
                )
            else:
                embeddings = [None] * len(chunks)

            # Step 3: Delete existing chunks for this document
            db.query(DBDocumentChunk).filter(
                DBDocumentChunk.document_id == doc_id
            ).delete()

            # Step 4: Store new chunks
            db_chunks = []
            for i, chunk in enumerate(chunks):
                db_chunk = DBDocumentChunk(
                    document_id=doc_id,
                    knowledge_base_id=kb_id,
                    chunk_index=chunk.index,
                    start_token=chunk.start_token,
                    end_token=chunk.end_token,
                    content=chunk.content,
                    embedding=embeddings[i] if embeddings[i] else None,
                    created_at=datetime.utcnow()
                )
                db.add(db_chunk)
                db_chunks.append(db_chunk)

            # Step 5: Update document status
            document.chunking_status = "completed"
            document.chunk_count = len(chunks)
            db.commit()

            logger.info(f"Document {doc_id}: created {len(chunks)} chunks")

            return {
                "doc_id": doc_id,
                "chunks": len(chunks),
                "embeddings": sum(1 for e in embeddings if e),
                "status": "completed"
            }

        except Exception as e:
            logger.error(f"Chunking failed for doc {doc_id}: {e}")
            document.chunking_status = "failed"
            db.commit()
            raise

    async def process_batch(
        self,
        db: Session,
        documents: List[DBDocument],
        contents: Dict[int, str],
        generate_embeddings: bool = True
    ) -> List[Dict]:
        """
        Process multiple documents.

        Args:
            db: Database session
            documents: List of DBDocument instances
            contents: Dict mapping doc_id to content
            generate_embeddings: Whether to generate embeddings

        Returns:
            List of processing results
        """
        results = []

        for doc in documents:
            content = contents.get(doc.id, "")
            if content:
                try:
                    result = await self.process_document(
                        db, doc, content, generate_embeddings
                    )
                    results.append(result)
                except Exception as e:
                    results.append({
                        "doc_id": doc.id,
                        "status": "failed",
                        "error": str(e)
                    })

        return results

    async def reprocess_document(
        self,
        db: Session,
        document: DBDocument,
        content: str
    ) -> Dict:
        """
        Reprocess a document (e.g., after content update).

        Clears existing chunks and creates new ones.
        """
        return await self.process_document(db, document, content)


async def chunk_document_on_upload(
    db: Session,
    document: DBDocument,
    content: str,
    generate_embeddings: bool = True
) -> Dict:
    """
    Convenience function to chunk a document after upload.

    Called from upload handlers to process new documents.

    Args:
        db: Database session
        document: The uploaded document
        content: Document content
        generate_embeddings: Whether to generate embeddings

    Returns:
        Processing result dict
    """
    pipeline = ChunkingPipeline()
    return await pipeline.process_document(
        db, document, content, generate_embeddings
    )


async def get_document_chunks(
    db: Session,
    document_id: int
) -> List[DBDocumentChunk]:
    """
    Get all chunks for a document.

    Args:
        db: Database session
        document_id: Document ID

    Returns:
        List of DBDocumentChunk instances ordered by index
    """
    return db.query(DBDocumentChunk).filter(
        DBDocumentChunk.document_id == document_id
    ).order_by(DBDocumentChunk.chunk_index).all()


async def search_chunks_by_embedding(
    db: Session,
    query_embedding: List[float],
    kb_id: str,
    top_k: int = 20,
    min_similarity: float = 0.5
) -> List[Dict]:
    """
    Search for similar chunks using embedding similarity.

    Args:
        db: Database session
        query_embedding: Query vector
        kb_id: Knowledge base ID to search within
        top_k: Number of results
        min_similarity: Minimum similarity threshold

    Returns:
        List of dicts with chunk info and similarity
    """
    import numpy as np

    # Get all chunks with embeddings in this KB
    chunks = db.query(DBDocumentChunk).filter(
        DBDocumentChunk.knowledge_base_id == kb_id,
        DBDocumentChunk.embedding.isnot(None)
    ).all()

    if not chunks:
        return []

    # Calculate similarities
    query_vec = np.array(query_embedding)
    query_norm = np.linalg.norm(query_vec)

    if query_norm == 0:
        return []

    results = []
    for chunk in chunks:
        if not chunk.embedding:
            continue

        chunk_vec = np.array(chunk.embedding)
        chunk_norm = np.linalg.norm(chunk_vec)

        if chunk_norm == 0:
            continue

        similarity = float(np.dot(query_vec, chunk_vec) / (query_norm * chunk_norm))

        if similarity >= min_similarity:
            results.append({
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "similarity": similarity,
                "token_count": chunk.end_token - chunk.start_token
            })

    # Sort by similarity
    results.sort(key=lambda x: x["similarity"], reverse=True)

    return results[:top_k]
