"""
Document Chunker Service for SyncBoard 3.0.

Splits documents into semantically meaningful chunks for:
- Better RAG retrieval (precise context)
- Embedding generation
- Hierarchical summarization

Uses tiktoken for accurate token counting.
"""

import logging
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import tiktoken, fall back to character-based estimation
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
    # Use cl100k_base encoding (GPT-4, GPT-3.5-turbo)
    _encoding = tiktoken.get_encoding("cl100k_base")
    logger.info("tiktoken loaded for accurate token counting")
except ImportError:
    TIKTOKEN_AVAILABLE = False
    _encoding = None
    logger.warning("tiktoken not available, using character-based estimation")


@dataclass
class Chunk:
    """Represents a document chunk."""
    index: int
    content: str
    start_token: int
    end_token: int
    token_count: int

    # Optional metadata
    section_title: Optional[str] = None
    is_code_block: bool = False


class DocumentChunker:
    """
    Intelligent document chunker that respects semantic boundaries.

    Features:
    - Accurate token counting with tiktoken
    - Respects paragraph/section boundaries
    - Handles code blocks specially
    - Configurable chunk sizes with overlap
    """

    def __init__(
        self,
        target_chunk_tokens: int = 8192,
        max_chunk_tokens: int = 16384,
        min_chunk_tokens: int = 100,
        overlap_tokens: int = 50
    ):
        """
        Initialize chunker with configurable parameters.

        Args:
            target_chunk_tokens: Ideal chunk size (default 8192 ~ 32KB)
            max_chunk_tokens: Maximum chunk size before forced split (default 16384 ~ 65KB)
            min_chunk_tokens: Minimum chunk size (avoid tiny chunks)
            overlap_tokens: Token overlap between chunks for context
        """
        self.target_tokens = target_chunk_tokens
        self.max_tokens = max_chunk_tokens
        self.min_tokens = min_chunk_tokens
        self.overlap_tokens = overlap_tokens

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken or estimation."""
        if TIKTOKEN_AVAILABLE and _encoding:
            return len(_encoding.encode(text))
        else:
            # Rough estimation: ~4 chars per token
            return len(text) // 4

    def encode_tokens(self, text: str) -> List[int]:
        """Encode text to token IDs."""
        if TIKTOKEN_AVAILABLE and _encoding:
            return _encoding.encode(text)
        else:
            # Return character positions as pseudo-tokens
            return list(range(len(text) // 4))

    def decode_tokens(self, tokens: List[int]) -> str:
        """Decode token IDs back to text."""
        if TIKTOKEN_AVAILABLE and _encoding:
            return _encoding.decode(tokens)
        else:
            # Not supported without tiktoken
            return ""

    def chunk_document(self, content: str, doc_id: Optional[int] = None) -> List[Chunk]:
        """
        Split document into semantically meaningful chunks.

        Args:
            content: Full document text
            doc_id: Optional document ID for logging

        Returns:
            List of Chunk objects
        """
        if not content or not content.strip():
            logger.warning(f"Empty content for doc {doc_id}")
            return []

        total_tokens = self.count_tokens(content)

        # If document is small enough, return as single chunk
        if total_tokens <= self.max_tokens:
            return [Chunk(
                index=0,
                content=content,
                start_token=0,
                end_token=total_tokens,
                token_count=total_tokens
            )]

        # Split into semantic units first
        units = self._split_into_units(content)

        # Merge units into chunks respecting token limits
        chunks = self._merge_units_into_chunks(units)

        logger.info(f"Doc {doc_id}: {total_tokens} tokens -> {len(chunks)} chunks")
        return chunks

    def _split_into_units(self, content: str) -> List[Dict]:
        """
        Split content into semantic units (paragraphs, code blocks, headers).

        Returns list of dicts with 'text', 'type', 'tokens'
        """
        units = []

        # Pattern to identify different content types
        # Code blocks (fenced or indented)
        code_pattern = r'```[\s\S]*?```|`[^`]+`'
        # Headers (markdown style)
        header_pattern = r'^#{1,6}\s+.+$'
        # Paragraphs (double newline separated)

        # First, extract code blocks to protect them
        code_blocks = []
        def save_code(match):
            code_blocks.append(match.group(0))
            return f"__CODE_BLOCK_{len(code_blocks)-1}__"

        protected = re.sub(code_pattern, save_code, content)

        # Split by double newlines (paragraphs)
        paragraphs = re.split(r'\n\s*\n', protected)

        current_token_pos = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Restore code blocks
            for i, code in enumerate(code_blocks):
                para = para.replace(f"__CODE_BLOCK_{i}__", code)

            # Determine unit type
            is_code = '```' in para or para.startswith('    ')
            is_header = bool(re.match(header_pattern, para, re.MULTILINE))

            tokens = self.count_tokens(para)

            units.append({
                'text': para,
                'type': 'code' if is_code else ('header' if is_header else 'paragraph'),
                'tokens': tokens,
                'start_token': current_token_pos
            })

            current_token_pos += tokens

        return units

    def _merge_units_into_chunks(self, units: List[Dict]) -> List[Chunk]:
        """
        Merge semantic units into chunks respecting token limits.
        """
        chunks = []
        current_chunk_text = []
        current_chunk_tokens = 0
        chunk_start_token = 0
        chunk_index = 0

        for unit in units:
            unit_tokens = unit['tokens']

            # If single unit exceeds max, we need to force-split it
            if unit_tokens > self.max_tokens:
                # First, save current chunk if any
                if current_chunk_text:
                    chunks.append(self._create_chunk(
                        chunk_index, current_chunk_text,
                        chunk_start_token, current_chunk_tokens
                    ))
                    chunk_index += 1
                    chunk_start_token += current_chunk_tokens
                    current_chunk_text = []
                    current_chunk_tokens = 0

                # Force-split the large unit
                split_chunks = self._force_split_unit(unit, chunk_index, chunk_start_token)
                for sc in split_chunks:
                    chunks.append(sc)
                    chunk_index += 1
                    chunk_start_token += sc.token_count
                continue

            # Check if adding this unit would exceed target
            if current_chunk_tokens + unit_tokens > self.target_tokens:
                # If current chunk meets minimum, save it
                if current_chunk_tokens >= self.min_tokens:
                    chunks.append(self._create_chunk(
                        chunk_index, current_chunk_text,
                        chunk_start_token, current_chunk_tokens
                    ))
                    chunk_index += 1

                    # Add overlap from end of previous chunk
                    overlap_text = self._get_overlap_text(current_chunk_text)
                    overlap_tokens = self.count_tokens(overlap_text) if overlap_text else 0

                    chunk_start_token += current_chunk_tokens - overlap_tokens
                    current_chunk_text = [overlap_text] if overlap_text else []
                    current_chunk_tokens = overlap_tokens

            # Add unit to current chunk
            current_chunk_text.append(unit['text'])
            current_chunk_tokens += unit_tokens

        # Don't forget the last chunk
        if current_chunk_text and current_chunk_tokens >= self.min_tokens:
            chunks.append(self._create_chunk(
                chunk_index, current_chunk_text,
                chunk_start_token, current_chunk_tokens
            ))
        elif current_chunk_text and chunks:
            # Append to previous chunk if too small
            last_chunk = chunks[-1]
            combined_text = last_chunk.content + "\n\n" + "\n\n".join(current_chunk_text)
            chunks[-1] = Chunk(
                index=last_chunk.index,
                content=combined_text,
                start_token=last_chunk.start_token,
                end_token=last_chunk.end_token + current_chunk_tokens,
                token_count=last_chunk.token_count + current_chunk_tokens
            )

        return chunks

    def _create_chunk(
        self,
        index: int,
        text_parts: List[str],
        start_token: int,
        token_count: int
    ) -> Chunk:
        """Create a Chunk object from text parts."""
        content = "\n\n".join(text_parts)
        return Chunk(
            index=index,
            content=content,
            start_token=start_token,
            end_token=start_token + token_count,
            token_count=token_count,
            is_code_block='```' in content
        )

    def _force_split_unit(
        self,
        unit: Dict,
        start_index: int,
        start_token: int
    ) -> List[Chunk]:
        """Force-split a unit that exceeds max tokens."""
        text = unit['text']
        chunks = []

        # Split by sentences for cleaner breaks
        sentences = re.split(r'(?<=[.!?])\s+', text)

        current_text = []
        current_tokens = 0
        chunk_index = start_index
        chunk_start = start_token

        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)

            if current_tokens + sentence_tokens > self.max_tokens and current_text:
                # Save current chunk
                content = ' '.join(current_text)
                chunks.append(Chunk(
                    index=chunk_index,
                    content=content,
                    start_token=chunk_start,
                    end_token=chunk_start + current_tokens,
                    token_count=current_tokens
                ))
                chunk_index += 1
                chunk_start += current_tokens
                current_text = []
                current_tokens = 0

            current_text.append(sentence)
            current_tokens += sentence_tokens

        # Last chunk
        if current_text:
            content = ' '.join(current_text)
            chunks.append(Chunk(
                index=chunk_index,
                content=content,
                start_token=chunk_start,
                end_token=chunk_start + current_tokens,
                token_count=current_tokens
            ))

        return chunks

    def _get_overlap_text(self, text_parts: List[str]) -> str:
        """Get overlap text from end of chunk for context continuity."""
        if not text_parts:
            return ""

        # Take last paragraph or portion of it
        last_part = text_parts[-1]
        last_tokens = self.count_tokens(last_part)

        if last_tokens <= self.overlap_tokens:
            return last_part

        # Take last N tokens worth of text (approximate)
        # Split into sentences and take from end
        sentences = re.split(r'(?<=[.!?])\s+', last_part)
        overlap_sentences = []
        overlap_tokens = 0

        for sentence in reversed(sentences):
            sent_tokens = self.count_tokens(sentence)
            if overlap_tokens + sent_tokens > self.overlap_tokens:
                break
            overlap_sentences.insert(0, sentence)
            overlap_tokens += sent_tokens

        return ' '.join(overlap_sentences) if overlap_sentences else ""


# Singleton instance
_chunker = None

def get_document_chunker() -> DocumentChunker:
    """Get or create singleton DocumentChunker instance."""
    global _chunker
    if _chunker is None:
        _chunker = DocumentChunker()
    return _chunker
