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
                    {"name": "Docker", "relevance": 0.95, "confidence": 0.92},
                    {"name": "Python", "relevance": 0.88, "confidence": 0.85}
                ],
                "skill_level": "intermediate",
                "primary_topic": "containerization",
                "suggested_cluster": "Docker & Deployment",
                "confidence_score": 0.88  # Overall confidence in this extraction
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
                # Ensure cached results have confidence_score (for backwards compatibility)
                if 'confidence_score' not in cached_result:
                    # Calculate from cached concepts
                    concepts = cached_result.get('concepts', [])
                    if concepts:
                        avg_conf = sum(c.get('confidence', 0.8) for c in concepts) / len(concepts)
                        cached_result['confidence_score'] = avg_conf
                    else:
                        cached_result['confidence_score'] = 0.5  # Neutral

                logger.info(
                    f"Cache HIT: Concept extraction for {source_type} "
                    f"({len(cached_result.get('concepts', []))} concepts, "
                    f"confidence: {cached_result.get('confidence_score', 0):.2f})"
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

            # Calculate overall confidence score for agentic learning
            # Based on: number of concepts, their confidence scores, and content quality signals
            if result['concepts']:
                # Average confidence of extracted concepts
                avg_confidence = sum(c.get('confidence', 0.0) for c in result['concepts']) / len(result['concepts'])

                # Adjust based on number of concepts (too few or too many reduces confidence)
                concept_count_factor = 1.0
                if filtered_count < 2:
                    concept_count_factor = 0.85  # Suspiciously few concepts
                elif filtered_count > 15:
                    concept_count_factor = 0.90  # Potentially noisy

                # Adjust based on content length
                content_length_factor = 1.0
                content_len = len(content)
                if content_len < 200:
                    content_length_factor = 0.80  # Very short content, less confidence
                elif content_len > 50000:
                    content_length_factor = 0.90  # Very long content, sampling may miss things

                # Calculate overall confidence
                result['confidence_score'] = avg_confidence * concept_count_factor * content_length_factor

                # Ensure it stays in 0.0-1.0 range
                result['confidence_score'] = max(0.0, min(1.0, result['confidence_score']))
            else:
                # No concepts extracted - low confidence
                result['confidence_score'] = 0.3

            logger.info(
                f"Cache MISS: Extracted {original_count} concepts from {source_type} "
                f"(API call made, {filtered_count} passed confidence filter, "
                f"overall confidence: {result.get('confidence_score', 0):.2f})"
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

    async def extract_with_critique(self, content: str, source_type: str) -> Dict:
        """
        Dual-pass concept extraction with self-critique (Phase C - Agentic Learning).

        Pass 1: Extract concepts normally
        Pass 2: AI critiques its own extraction
        Pass 3: Refine based on critique

        This is the core of "questioning every decision" - the AI examines its own work!

        Args:
            content: Full text content
            source_type: "youtube", "pdf", "text", "url", "audio", "image"

        Returns:
            {
                "concepts": [...],  # Refined concepts after critique
                "skill_level": "intermediate",
                "primary_topic": "...",
                "suggested_cluster": "...",
                "confidence_score": 0.88,
                "critique": {  # NEW: Self-critique metadata
                    "issues_found": [...],
                    "concepts_added": [...],
                    "concepts_removed": [...],
                    "confidence_adjustment": 0.05
                }
            }
        """
        logger.info(f"Starting dual-pass extraction with self-critique for {source_type}")

        # PASS 1: Initial extraction
        logger.debug("Pass 1: Initial concept extraction...")
        initial_result = await self.extract(content, source_type)
        initial_concepts = initial_result.get("concepts", [])
        initial_confidence = initial_result.get("confidence_score", 0.5)

        # If confidence is already high, skip critique
        if initial_confidence >= 0.9:
            logger.info(f"Initial confidence {initial_confidence:.2f} is high, skipping critique")
            return initial_result

        # PASS 2: Self-critique
        logger.debug("Pass 2: AI self-critique...")
        try:
            critique_prompt = self._build_critique_prompt(content, initial_result)
            critique_response = await self.provider._call_llm(
                prompt=critique_prompt,
                response_format={"type": "json_object"}
            )

            critique = json.loads(critique_response)

            # PASS 3: Refine based on critique
            logger.debug("Pass 3: Applying critique refinements...")
            refined_result = self._apply_critique(initial_result, critique)

            logger.info(
                f"Dual-pass complete: {len(initial_concepts)} → {len(refined_result['concepts'])} concepts, "
                f"confidence: {initial_confidence:.2f} → {refined_result['confidence_score']:.2f}"
            )

            return refined_result

        except Exception as e:
            logger.warning(f"Critique pass failed, returning initial extraction: {e}")
            return initial_result

    def _build_critique_prompt(self, content: str, initial_result: Dict) -> str:
        """Build prompt for AI to critique its own extraction."""
        concepts_list = [c.get('name') for c in initial_result.get('concepts', [])]

        prompt = f"""You are a critical AI reviewer. Analyze this concept extraction and identify issues.

ORIGINAL CONTENT (sample):
{content[:1000]}

EXTRACTED CONCEPTS:
{', '.join(concepts_list)}

SKILL LEVEL: {initial_result.get('skill_level', 'unknown')}
PRIMARY TOPIC: {initial_result.get('primary_topic', 'unknown')}
INITIAL CONFIDENCE: {initial_result.get('confidence_score', 0.5):.2f}

Your task: Critically review this extraction. Be harsh but fair.

Questions to ask:
1. Are any IMPORTANT concepts missing from the content?
2. Are any extracted concepts WRONG or too vague?
3. Is the skill level accurate?
4. Should confidence be adjusted up or down?

Return JSON with:
{{
    "issues_found": ["issue 1", "issue 2"],
    "missing_concepts": [
        {{"name": "Docker", "category": "tool", "confidence": 0.9, "reasoning": "Mentioned 5 times"}}
    ],
    "incorrect_concepts": [
        {{"name": "Web", "reasoning": "Too vague, should be 'REST API'"}}
    ],
    "skill_level_adjustment": "intermediate" or null,
    "confidence_adjustment": 0.05,  // -0.2 to +0.2
    "overall_assessment": "Brief assessment"
}}

Be critical but constructive. The goal is ACCURACY."""

        return prompt

    def _apply_critique(self, initial_result: Dict, critique: Dict) -> Dict:
        """Apply critique to refine the extraction."""
        refined = initial_result.copy()
        concepts = list(initial_result.get('concepts', []))

        changes = {
            "issues_found": critique.get("issues_found", []),
            "concepts_added": [],
            "concepts_removed": [],
            "confidence_adjustment": critique.get("confidence_adjustment", 0.0)
        }

        # Remove incorrect concepts
        incorrect_names = {c['name'] for c in critique.get("incorrect_concepts", [])}
        if incorrect_names:
            concepts = [c for c in concepts if c.get('name') not in incorrect_names]
            changes["concepts_removed"] = list(incorrect_names)
            logger.info(f"Removed incorrect concepts: {incorrect_names}")

        # Add missing concepts
        missing_concepts = critique.get("missing_concepts", [])
        if missing_concepts:
            for concept in missing_concepts:
                # Filter by confidence threshold
                if concept.get('confidence', 0.0) >= MIN_CONCEPT_CONFIDENCE:
                    concepts.append(concept)
                    changes["concepts_added"].append(concept['name'])
            logger.info(f"Added missing concepts: {changes['concepts_added']}")

        # Update skill level if suggested
        if critique.get("skill_level_adjustment"):
            refined["skill_level"] = critique["skill_level_adjustment"]
            logger.debug(f"Adjusted skill level to: {refined['skill_level']}")

        # Adjust confidence score
        confidence_adjustment = critique.get("confidence_adjustment", 0.0)
        new_confidence = initial_result.get('confidence_score', 0.5) + confidence_adjustment
        refined["confidence_score"] = max(0.0, min(1.0, new_confidence))

        # Update concepts
        refined["concepts"] = concepts

        # Add critique metadata
        refined["critique"] = changes

        logger.info(
            f"Refinement applied: +{len(changes['concepts_added'])} concepts, "
            f"-{len(changes['concepts_removed'])} concepts, "
            f"confidence Δ{confidence_adjustment:+.2f}"
        )

        return refined
