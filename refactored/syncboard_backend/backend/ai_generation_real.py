"""
Real AI generation with RAG (Retrieval Augmented Generation).
Uses OpenAI to generate content based on user's knowledge bank.
"""

import os
import logging
from typing import Dict, List, Optional, Any
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Available models
MODELS = {
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-4o": "gpt-4o",
    "gpt-4": "gpt-4-turbo-preview",
    "gpt-5-mini": "gpt-5-mini",
    "gpt-5": "gpt-5",
    "gpt-5-nano": "gpt-5-nano",
}

# Initialize OpenAI client
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def generate_with_rag(
    prompt: str,
    model: str,
    vector_store,
    allowed_doc_ids: List[int],
    documents: Dict[int, str],
    metadata: Optional[Dict[int, Any]] = None,
    top_k: int = 100
) -> str:
    """
    Generate AI content using Retrieval Augmented Generation.

    Args:
        prompt: User's prompt/question
        model: OpenAI model to use
        vector_store: Vector store for semantic search
        allowed_doc_ids: Document IDs the user has access to
        documents: All documents dict
        metadata: Optional document metadata dict for citations
        top_k: Number of relevant documents to retrieve

    Returns:
        Generated text response
    """
    # Get relevant documents using semantic search
    search_results = vector_store.search(prompt, top_k=top_k, allowed_doc_ids=allowed_doc_ids)

    # Filter to only user's documents with metadata
    relevant_docs = []
    for doc_id, score, snippet in search_results:  # FIX: Unpack all 3 values
        if doc_id in allowed_doc_ids and doc_id in documents:
            doc_info = {
                "doc_id": doc_id,
                "content": documents[doc_id],
                "relevance": score
            }
            # Add metadata if available
            if metadata and doc_id in metadata:
                meta = metadata[doc_id]
                doc_info["source_type"] = getattr(meta, 'source_type', 'unknown')
                doc_info["filename"] = getattr(meta, 'filename', None)
                doc_info["source_url"] = getattr(meta, 'source_url', None)
                # Get concept names
                concepts = getattr(meta, 'concepts', [])
                doc_info["concepts"] = [c.name for c in concepts[:5]] if concepts else []
            relevant_docs.append(doc_info)

    # Token budget management (GPT-5 has 272k input limit, leave room for prompt + response)
    MAX_CONTEXT_TOKENS = 200000  # Conservative limit for context
    CHARS_PER_TOKEN = 4  # Rough estimate

    # Truncate documents to fit within token budget
    total_chars = 0
    max_chars = MAX_CONTEXT_TOKENS * CHARS_PER_TOKEN
    truncated_docs = []

    for doc in relevant_docs[:top_k]:
        doc_content = doc['content']
        doc_chars = len(doc_content)

        if total_chars + doc_chars <= max_chars:
            # Document fits entirely
            truncated_docs.append(doc)
            total_chars += doc_chars
        elif total_chars < max_chars:
            # Partial document fits
            remaining_chars = max_chars - total_chars
            truncated_content = doc_content[:remaining_chars] + "\n\n[... content truncated ...]"
            truncated_docs.append({
                "content": truncated_content,
                "relevance": doc['relevance']
            })
            total_chars = max_chars
            logger.warning(f"Truncated document to fit within token budget")
            break
        else:
            # No more room
            logger.warning(f"Skipped {len(relevant_docs) - len(truncated_docs)} documents due to token limit")
            break

    logger.info(f"Using {len(truncated_docs)} documents (~{total_chars//CHARS_PER_TOKEN} tokens)")

    # Build context from truncated documents with metadata
    context_parts = []
    for i, doc in enumerate(truncated_docs):
        # Build document header with metadata
        header = f"[Document {i+1}"
        if doc.get('filename'):
            header += f" | {doc['filename']}"
        elif doc.get('source_url'):
            # Truncate long URLs
            url = doc['source_url']
            if len(url) > 60:
                url = url[:57] + "..."
            header += f" | {url}"
        header += f" | {doc.get('source_type', 'unknown')}"
        header += f" | Relevance: {doc['relevance']:.2f}]"

        # Add concepts if available
        if doc.get('concepts'):
            header += f"\nKey concepts: {', '.join(doc['concepts'])}"

        context_parts.append(f"{header}\n{doc['content']}")

    context = "\n\n---\n\n".join(context_parts)

    # Construct system message with citation guidance
    system_message = """You are an AI assistant helping users with their knowledge bank.
You have access to the user's documents and can use them to provide informed, accurate responses.

IMPORTANT: When answering, you MUST:
1. Cite your sources using document numbers (e.g., "According to Document 1..." or "[Document 3]")
2. Reference filenames or URLs when available for better traceability
3. If multiple documents support a point, cite all of them
4. If you cannot find relevant information, say so clearly

The documents are sorted by relevance to the user's question."""

    # Construct user message with context
    if context:
        user_message = f"""Based on the following documents from my knowledge bank:

{context}

---

Please answer this question: {prompt}"""
    else:
        user_message = f"""I don't have any relevant documents in my knowledge bank for this question, but please try to help anyway:

{prompt}"""

    # Call OpenAI API
    try:
        selected_model = MODELS.get(model, "gpt-5-mini")
        logger.info(f"Using model: {selected_model} (requested: {model})")

        # GPT-5 models use different parameters
        if selected_model.startswith("gpt-5"):
            response = await client.chat.completions.create(
                model=selected_model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                max_completion_tokens=16000
            )
        else:
            response = await client.chat.completions.create(
                model=selected_model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=16000
            )

        generated_text = response.choices[0].message.content
        logger.info(f"Generated response using {len(relevant_docs)} relevant documents")
        return generated_text

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise Exception(f"Failed to generate response: {str(e)}")
