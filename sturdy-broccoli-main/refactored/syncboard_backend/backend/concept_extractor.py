"""
Concept extraction with LLM provider abstraction.
Analyzes content and extracts topics, concepts, skills, and metadata.

Improvement #5: Redis-based caching to save 20-40% on API costs.
"""

import os
import json
import logging
from typing import Dict, Optional

from .llm_providers import LLMProvider, OpenAIProvider
from .constants import (
    ENABLE_CONCEPT_CACHING,
    CONCEPT_CACHE_TTL_DAYS,
    CONCEPT_EXTRACTION_SAMPLE_SIZE,
    MIN_CONCEPT_CONFIDENCE,
    VALID_CONCEPT_CATEGORIES
)
from .cache import get_cached_concepts, cache_concepts

logger = logging.getLogger(__name__)


def filter_concepts_by_confidence(concepts: list, min_confidence: float = 0.7) -> list:
    """
    Filter concepts by confidence threshold and validate categories.

    Args:
        concepts: List of concept dicts with 'name', 'category', 'confidence'
        min_confidence: Minimum confidence threshold (default: 0.7)

    Returns:
        Filtered list of high-confidence concepts with valid categories
    """
    if not concepts:
        return []

    filtered = []
    removed_count = 0

    for concept in concepts:
        confidence = concept.get('confidence', 0.0)
        category = concept.get('category', 'concept')

        # Check confidence threshold
        if confidence < min_confidence:
            removed_count += 1
            logger.debug(
                f"Filtered out low-confidence concept: '{concept.get('name')}' "
                f"(confidence: {confidence:.2f} < {min_confidence})"
            )
            continue

        # Validate category (map old categories to new ones)
        if category not in VALID_CONCEPT_CATEGORIES:
            # Try to map old categories
            if category in ["tech", "technology"]:
                category = "tool"
            elif category in ["service", "api"]:
                category = "platform"
            else:
                category = "concept"  # Default fallback

        # Keep this concept
        filtered.append({
            'name': concept.get('name'),
            'category': category,
            'confidence': confidence
        })

    if removed_count > 0:
        logger.info(
            f"Filtered {removed_count} low-confidence concepts "
            f"(kept {len(filtered)}/{len(concepts)})"
        )

    return filtered


class ConceptExtractor:
    """Extract concepts from content using configurable LLM provider."""

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        """
        Initialize concept extractor.

        Args:
            llm_provider: LLM provider to use (defaults to OpenAIProvider)
        """
        if llm_provider is None:
            # Default to OpenAI provider
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable required")
            self.provider = OpenAIProvider(api_key=api_key)
        else:
            self.provider = llm_provider

    async def extract(self, content: str, source_type: str) -> Dict:
        """
        Extract concepts from content with Redis caching.

        Args:
            content: Full text content
            source_type: "youtube", "pdf", "text", "url", "audio", "image"

        Returns:
            {
                "concepts": [
                    {"name": "Docker", "relevance": 0.95},
                    {"name": "Python", "relevance": 0.88}
                ],
                "skill_level": "intermediate",
                "primary_topic": "containerization",
                "suggested_cluster": "Docker & Deployment"
            }
        """
        # Check cache first (if enabled)
        if ENABLE_CONCEPT_CACHING:
            cached_result = get_cached_concepts(
                content=content,
                source_type=source_type,
                sample_size=CONCEPT_EXTRACTION_SAMPLE_SIZE
            )

            if cached_result:
                logger.info(
                    f"Cache HIT: Concept extraction for {source_type} "
                    f"({len(cached_result.get('concepts', []))} concepts)"
                )
                return cached_result

        try:
            # Cache miss or caching disabled - call LLM provider
            result = await self.provider.extract_concepts(content, source_type)

            # Apply confidence filtering (Improvement #6)
            original_count = len(result.get('concepts', []))
            result['concepts'] = filter_concepts_by_confidence(
                result.get('concepts', []),
                min_confidence=MIN_CONCEPT_CONFIDENCE
            )
            filtered_count = len(result['concepts'])

            logger.info(
                f"Cache MISS: Extracted {original_count} concepts from {source_type} "
                f"(API call made, {filtered_count} passed confidence filter)"
            )

            # Store in cache for future use (after filtering)
            if ENABLE_CONCEPT_CACHING and result.get("concepts"):
                cache_success = cache_concepts(
                    content=content,
                    source_type=source_type,
                    sample_size=CONCEPT_EXTRACTION_SAMPLE_SIZE,
                    result=result,
                    ttl_days=CONCEPT_CACHE_TTL_DAYS
                )
                if cache_success:
                    logger.debug(f"Cached concept extraction result (TTL: {CONCEPT_CACHE_TTL_DAYS} days)")

            return result

        except Exception as e:
            logger.error(f"Concept extraction failed: {e}")
            return {
                "concepts": [],
                "skill_level": "unknown",
                "primary_topic": "uncategorized",
                "suggested_cluster": "General"
            }
