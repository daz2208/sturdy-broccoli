"""
Concept extraction with LLM provider abstraction.
Analyzes content and extracts topics, concepts, skills, and metadata.

Improvement #5: Redis-based caching to save 20-40% on API costs.
Improvement #7: Agentic Learning - extract_with_learning() closes the feedback loop.
"""

import json
import logging
from typing import Dict, Optional, Any

from .llm_providers import LLMProvider, OpenAIProvider, get_representative_sample
from .config import settings
from .constants import VALID_CONCEPT_CATEGORIES
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
            api_key = settings.openai_api_key
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
        if settings.enable_concept_caching:
            cached_result = get_cached_concepts(
                content=content,
                source_type=source_type,
                sample_size=settings.concept_sample_size
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
                min_confidence=settings.min_concept_confidence
            )
            filtered_count = len(result['concepts'])

            # Apply learned rules from agentic learning (vocabulary, reject/rename rules)
            if username:
                from backend.learning_engine import LearningEngine
                result['concepts'], applied_rules_log = LearningEngine.apply_learned_rules(
                    username=username,
                    concepts=result['concepts'],
                    content_sample=content[:500]  # First 500 chars for context
                )
                if applied_rules_log:
                    logger.info(f"🤖 Applied {len(applied_rules_log)} learned rules for {username}: {', '.join(applied_rules_log[:3])}")

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
            if settings.enable_concept_caching and result.get("concepts"):
                cache_success = cache_concepts(
                    content=content,
                    source_type=source_type,
                    sample_size=settings.concept_sample_size,
                    result=result,
                    ttl_days=settings.concept_cache_ttl_days
                )
                if cache_success:
                    logger.debug(f"Cached concept extraction result (TTL: {settings.concept_cache_ttl_days} days)")

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

        prompt = f"""You are a quality assurance reviewer for a concept extraction system.

Your role: Find errors and omissions in an AI's previous extraction.

ORIGINAL CONTENT:
{content[:1500]}

EXTRACTION TO REVIEW:
- Concepts: {', '.join(concepts_list)}
- Skill Level: {initial_result.get('skill_level', 'unknown')}
- Primary Topic: {initial_result.get('primary_topic', 'unknown')}
- Confidence Score: {initial_result.get('confidence_score', 0.5):.2f}

---

REVIEW CRITERIA:
1. MISSING CONCEPTS: Important technologies discussed but not extracted
2. WRONG CONCEPTS: Extracted concepts not actually in the content, or too vague
3. WRONG CATEGORIES: Concept exists but category is incorrect
4. CONFIDENCE ISSUES: Over-confident for minor mentions, under-confident for main topics
5. SKILL LEVEL: Does it match the content's actual complexity?

---

EXAMPLE CRITIQUE:
{{
  "issues_found": [
    "Missed 'kubernetes' which is mentioned 8 times",
    "'Web' is too vague - content specifically discusses REST APIs",
    "Skill level should be 'advanced' not 'intermediate' - assumes prior Docker knowledge"
  ],
  "missing_concepts": [
    {{"name": "kubernetes", "category": "platform", "confidence": 0.92, "reasoning": "Central topic, mentioned 8 times with examples"}}
  ],
  "incorrect_concepts": [
    {{"name": "web", "reasoning": "Too vague. Content specifically covers REST API design patterns."}}
  ],
  "skill_level_adjustment": "advanced",
  "confidence_adjustment": -0.1,
  "overall_assessment": "Extraction missed the main topic (Kubernetes) and included vague terms. Needs revision."
}}

---

Provide your critique. Be critical - it's better to catch errors now than serve bad data to users.
Return ONLY valid JSON:"""

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
                if concept.get('confidence', 0.0) >= settings.min_concept_confidence:
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

    # =============================================================================
    # AGENTIC LEARNING: Extract with Feedback Loop
    # =============================================================================

    async def extract_with_learning(
        self,
        content: str,
        source_type: str,
        username: str,
        knowledge_base_id: Optional[str] = None
    ) -> Dict:
        """
        Extract concepts with ACTUAL LEARNING from past feedback.

        THIS METHOD CLOSES THE AGENTIC LEARNING LOOP:
        1. Retrieves past corrections and user preferences
        2. Injects them into the extraction prompt
        3. Calibrates confidence based on historical accuracy
        4. Optionally runs dual-pass critique for low confidence

        Args:
            content: Full text content to analyze
            source_type: "youtube", "pdf", "text", "url", "audio", "image"
            username: User whose preferences to apply
            knowledge_base_id: Optional KB ID for scoped learning

        Returns:
            {
                "concepts": [...],
                "skill_level": "intermediate",
                "primary_topic": "...",
                "suggested_cluster": "...",
                "confidence_score": 0.88,
                "learning_applied": {  # NEW: Learning metadata
                    "corrections_used": 3,
                    "preferences_applied": ["prefers_specific_names"],
                    "confidence_calibrated": True,
                    "original_confidence": 0.75,
                    "calibration_adjustment": -0.05
                }
            }
        """
        from .feedback_service import FeedbackService

        logger.info(f"Starting learning-aware extraction for {username}")

        # Step 1: Get learning context
        learning_context = await FeedbackService.get_learning_context_for_extraction(
            username=username,
            content_sample=content[:500],
            decision_type="concept_extraction",
            max_corrections=5
        )

        learning_metadata = {
            "corrections_used": len(learning_context.get("recent_corrections", [])),
            "preferences_applied": [],
            "confidence_calibrated": False,
            "original_confidence": None,
            "calibration_adjustment": 0.0
        }

        # Step 2: Build enhanced prompt with learning context
        prompt_additions = learning_context.get("prompt_additions", "")

        if prompt_additions:
            logger.info(
                f"Injecting learning context: {learning_metadata['corrections_used']} corrections, "
                f"preferences={learning_context.get('user_preferences', {}).get('has_feedback', False)}"
            )

            # Track which preferences were applied
            prefs = learning_context.get("user_preferences", {})
            if prefs.get("prefers_specific_names") is True:
                learning_metadata["preferences_applied"].append("prefers_specific_names")
            if prefs.get("frequently_removed"):
                learning_metadata["preferences_applied"].append("avoid_removed_concepts")
            if prefs.get("avg_concepts_preferred"):
                learning_metadata["preferences_applied"].append("target_concept_count")

        # Step 3: Extract with enhanced prompt
        result = await self._extract_with_learning_prompt(
            content=content,
            source_type=source_type,
            learning_additions=prompt_additions
        )

        # Step 4: Calibrate confidence based on historical accuracy
        raw_confidence = result.get("confidence_score", 0.5)
        learning_metadata["original_confidence"] = raw_confidence

        calibration = learning_context.get("confidence_calibration", {})
        calibrated_confidence = self._calibrate_confidence(
            raw_confidence=raw_confidence,
            calibration_data=calibration
        )

        if calibrated_confidence != raw_confidence:
            learning_metadata["confidence_calibrated"] = True
            learning_metadata["calibration_adjustment"] = calibrated_confidence - raw_confidence
            result["confidence_score"] = calibrated_confidence
            logger.info(
                f"Confidence calibrated: {raw_confidence:.2f} → {calibrated_confidence:.2f} "
                f"(Δ{learning_metadata['calibration_adjustment']:+.2f})"
            )

        # Step 5: Optional dual-pass critique for low confidence
        if settings.enable_dual_pass and calibrated_confidence < settings.dual_pass_threshold:
            logger.info(
                f"Low confidence ({calibrated_confidence:.2f}), applying dual-pass critique"
            )
            # Run critique on the learning-enhanced result
            result = await self._apply_critique_to_result(result, content)

        # Add learning metadata to result
        result["learning_applied"] = learning_metadata

        logger.info(
            f"Learning-aware extraction complete: "
            f"{len(result.get('concepts', []))} concepts, "
            f"confidence={result.get('confidence_score', 0):.2f}, "
            f"corrections_used={learning_metadata['corrections_used']}"
        )

        return result

    async def _extract_with_learning_prompt(
        self,
        content: str,
        source_type: str,
        learning_additions: str
    ) -> Dict:
        """
        Extract concepts using a prompt enhanced with learning context.

        Args:
            content: Content to analyze
            source_type: Type of content
            learning_additions: Additional prompt text from learning context

        Returns:
            Extraction result with concepts and metadata
        """
        # Smart sampling: extract from beginning, middle, and end
        if settings.concept_sample_method == "smart":
            sample = get_representative_sample(content, max_chars=settings.concept_sample_size)
            sampling_note = "\nNOTE: For long documents, this is a representative sample from beginning, middle, and end."
        else:
            sample = content[:settings.concept_sample_size] if len(content) > settings.concept_sample_size else content
            sampling_note = ""

        # Detect YouTube transcripts
        is_youtube = "YOUTUBE VIDEO TRANSCRIPT" in content or source_type == "youtube"

        # Build the enhanced prompt
        if is_youtube:
            base_prompt = self._build_youtube_learning_prompt(sample, sampling_note, learning_additions)
        else:
            base_prompt = self._build_standard_learning_prompt(sample, source_type, sampling_note, learning_additions)

        try:
            # Call LLM directly via provider
            response = await self.provider._call_llm(
                prompt=base_prompt,
                response_format={"type": "json_object"}
            ) if hasattr(self.provider, '_call_llm') else await self._call_provider_extract(base_prompt)

            result = json.loads(response)

            # Apply confidence filtering
            original_count = len(result.get('concepts', []))
            result['concepts'] = filter_concepts_by_confidence(
                result.get('concepts', []),
                min_confidence=settings.min_concept_confidence
            )
            filtered_count = len(result['concepts'])

            # Calculate confidence score
            if result['concepts']:
                avg_confidence = sum(c.get('confidence', 0.0) for c in result['concepts']) / len(result['concepts'])

                concept_count_factor = 1.0
                if filtered_count < 2:
                    concept_count_factor = 0.85
                elif filtered_count > 15:
                    concept_count_factor = 0.90

                content_length_factor = 1.0
                content_len = len(content)
                if content_len < 200:
                    content_length_factor = 0.80
                elif content_len > 50000:
                    content_length_factor = 0.90

                result['confidence_score'] = max(0.0, min(1.0,
                    avg_confidence * concept_count_factor * content_length_factor
                ))
            else:
                result['confidence_score'] = 0.3

            logger.info(
                f"Learning-enhanced extraction: {original_count} → {filtered_count} concepts, "
                f"confidence={result.get('confidence_score', 0):.2f}"
            )

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from learning extraction: {e}")
            return {
                "concepts": [],
                "skill_level": "unknown",
                "primary_topic": "uncategorized",
                "suggested_cluster": "General",
                "confidence_score": 0.3
            }
        except Exception as e:
            logger.error(f"Learning extraction failed: {e}")
            return {
                "concepts": [],
                "skill_level": "unknown",
                "primary_topic": "uncategorized",
                "suggested_cluster": "General",
                "confidence_score": 0.3
            }

    async def _call_provider_extract(self, prompt: str) -> str:
        """Fallback method to call provider's extract via chat completion."""
        from openai import AsyncOpenAI
        api_key = settings.openai_api_key
        client = AsyncOpenAI(api_key=api_key)

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a concept extraction system. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=4000
        )

        return response.choices[0].message.content or ""

    def _build_standard_learning_prompt(
        self,
        sample: str,
        source_type: str,
        sampling_note: str,
        learning_additions: str
    ) -> str:
        """Build standard prompt enhanced with learning context."""
        learning_section = ""
        if learning_additions:
            learning_section = f"""
---
## LEARNING FROM PAST USER FEEDBACK
{learning_additions}

IMPORTANT: Apply these learnings to improve extraction accuracy. The user has corrected similar extractions before.
---
"""

        return f"""Analyze this {source_type} document and extract BOTH capabilities AND technologies.{sampling_note}
{learning_section}
DOCUMENT CONTENT:
{sample}

---

EXTRACTION RULES:
1. Extract 5-15 concepts in TWO types (prioritize CAPABILITIES):

   TYPE 1 - CAPABILITIES (extract these FIRST):
   What problems does this code/document solve? What can it DO?
   Examples: "cloud cost estimation", "CVE vulnerability scoring",
   "multi-tenant isolation", "real-time data sync", "payment processing"

   PRIORITIZE:   - Domain-specific engines (cost calculators, security analyzers, risk scorers)
   - Complex business logic (industry multipliers, compliance checks, audit trails)
   - Data processing algorithms (parsing, scoring, matching, detection)
   OVER:
   - Generic CRUD operations (create/read/update/delete)
   - Simple API scaffolds (basic REST endpoints)
   - Standard auth patterns (login/logout/token refresh)

   TYPE 2 - TECHNOLOGIES (extract these SECOND):
   What tools/frameworks does it use?
   Examples: "python", "django", "postgresql", "celery"

2. For versioned tools, use base name: "python" not "python 3.11"
3. Code blocks = HIGH confidence (0.9+), prose mentions = MEDIUM confidence (0.7-0.85)
4. Skip concepts only mentioned as alternatives or historical context

CONFIDENCE SCORING:
- 0.95-1.0: Main topic, extensively covered with examples
- 0.85-0.94: Clearly explained with code or detailed explanation
- 0.75-0.84: Mentioned and briefly explained
- 0.70-0.74: Mentioned but not explained in detail

CATEGORIES:
Technologies: language | framework | library | tool | platform | database | devops
Patterns: methodology | architecture | testing | concept
Capabilities: capability | problem_domain | business_logic | algorithm | integration_pattern

CATEGORY DEFINITIONS FOR CAPABILITIES:
- capability: Functional ability (e.g., "cost estimation", "vulnerability scanning", "text-to-speech")
- problem_domain: Business/domain area (e.g., "e-commerce", "healthcare compliance", "financial reporting")
- business_logic: Specific logic patterns (e.g., "tenant isolation", "rate limiting", "audit logging")
- algorithm: Computational approaches (e.g., "risk scoring", "similarity matching", "anomaly detection")
- integration_pattern: How systems connect (e.g., "webhook handling", "API orchestration", "event streaming")

Return ONLY valid JSON (no markdown backticks):
{{
  "concepts": [{{"name": "...", "category": "...", "confidence": 0.9}}],
  "skill_level": "beginner|intermediate|advanced",
  "primary_topic": "main topic in 2-4 words",
  "suggested_cluster": "cluster name for grouping"
}}"""

    def _build_youtube_learning_prompt(
        self,
        sample: str,
        sampling_note: str,
        learning_additions: str
    ) -> str:
        """Build YouTube prompt enhanced with learning context."""
        learning_section = ""
        if learning_additions:
            learning_section = f"""
---
## LEARNING FROM PAST USER FEEDBACK
{learning_additions}

IMPORTANT: Apply these learnings to improve extraction accuracy. The user has corrected similar extractions before.
---
"""

        return f"""Analyze this YouTube video transcript and extract learning content.{sampling_note}
{learning_section}
TRANSCRIPT CHALLENGES:
- Transcripts may lack punctuation - use context
- Ignore filler words ("um", "uh")
- Fix mistranscribed tech terms using context (e.g., "pie torch" = "PyTorch")

TRANSCRIPT:
{sample}

---

EXTRACTION GUIDELINES:
1. Title: Infer from intro if not explicit
2. Creator: Look for "Hey I'm..." or channel mentions
3. Concepts: What's being TAUGHT, not just mentioned (3-10 concepts)
4. Key Takeaways: 3 most actionable things a viewer would learn
5. Confidence: 0.9+ for main topics, 0.7-0.85 for supporting topics

VIDEO TYPES:
- tutorial: Step-by-step building
- talk: Conference/lecture
- demo: Showing features
- discussion: Multiple speakers
- course: Part of series
- review: Evaluating tools

Return ONLY valid JSON (no markdown backticks):
{{
  "title": "Video title",
  "creator": "Channel name",
  "concepts": [{{"name": "...", "category": "...", "confidence": 0.9}}],
  "skill_level": "beginner|intermediate|advanced",
  "primary_topic": "main topic",
  "suggested_cluster": "cluster name",
  "target_audience": "Who this is for",
  "key_takeaways": ["Point 1", "Point 2", "Point 3"],
  "video_type": "tutorial|talk|demo|discussion|course|review",
  "estimated_watch_time": "length"
}}"""

    def _calibrate_confidence(
        self,
        raw_confidence: float,
        calibration_data: Dict[str, Any]
    ) -> float:
        """
        Calibrate confidence based on historical accuracy.

        If the model has been overconfident at this confidence level historically,
        adjust the displayed confidence downward (and vice versa).

        Args:
            raw_confidence: Raw confidence score from extraction
            calibration_data: Historical accuracy by confidence range

        Returns:
            Calibrated confidence score
        """
        if not calibration_data:
            return raw_confidence

        # Determine which calibration bucket applies
        if raw_confidence < 0.7:
            bucket = calibration_data.get("low", {})
        elif raw_confidence < 0.9:
            bucket = calibration_data.get("medium", {})
        else:
            bucket = calibration_data.get("high", {})

        # Only calibrate if we have enough samples
        if bucket.get("sample_size", 0) < 5:
            return raw_confidence

        # Only calibrate if significant miscalibration detected
        if not bucket.get("calibration_needed", False):
            return raw_confidence

        # Apply calibration adjustment
        adjustment = bucket.get("suggested_adjustment", 0.0)

        # Limit adjustment to prevent extreme swings
        adjustment = max(-0.15, min(0.15, adjustment))

        calibrated = raw_confidence + adjustment

        # Ensure result stays in valid range
        return max(0.0, min(1.0, calibrated))

    async def _apply_critique_to_result(
        self,
        initial_result: Dict,
        content: str
    ) -> Dict:
        """
        Apply self-critique to an existing extraction result.

        This is used after learning-enhanced extraction when confidence is still low.

        Args:
            initial_result: Initial extraction result
            content: Original content for context

        Returns:
            Refined result after critique
        """
        initial_confidence = initial_result.get("confidence_score", 0.5)

        # Skip if already high confidence
        if initial_confidence >= 0.9:
            return initial_result

        try:
            critique_prompt = self._build_critique_prompt(content, initial_result)
            response = await self._call_provider_extract(critique_prompt)
            critique = json.loads(response)

            # Apply critique
            refined_result = self._apply_critique(initial_result, critique)

            logger.info(
                f"Post-learning critique: confidence {initial_confidence:.2f} → "
                f"{refined_result.get('confidence_score', 0):.2f}"
            )

            return refined_result

        except Exception as e:
            logger.warning(f"Post-learning critique failed, returning initial result: {e}")
            return initial_result
