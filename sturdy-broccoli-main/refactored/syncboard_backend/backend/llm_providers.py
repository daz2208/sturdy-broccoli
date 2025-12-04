"""
Abstract LLM provider interface for decoupling from specific AI vendors.

This allows easy switching between OpenAI, Anthropic, local models, etc.
"""

import json
import logging
import string
from abc import ABC, abstractmethod
from typing import Dict, List

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import settings

logger = logging.getLogger(__name__)


def _is_code(content: str) -> bool:
    """
    Detect if content is source code.

    Checks for common programming patterns in the first 2000 characters.
    Returns True if at least 2 code indicators are found.
    """
    code_indicators = [
        # Python
        'def ', 'class ', 'import ', 'from ', '@dataclass', '@property',
        'async def', 'await ', 'self.', '__init__',
        # JavaScript/TypeScript
        'function ', 'const ', 'let ', 'var ', 'export ', '=>',
        'async function', 'module.exports',
        # Java/C#/C++
        'public ', 'private ', 'protected ', 'void ', 'static ',
        # Rust
        'fn ', 'impl ', 'pub ', 'mod ',
        # Go
        'func ', 'package ',
    ]

    # Check first 2000 chars for code patterns
    sample = content[:2000].lower()
    matches = sum(1 for ind in code_indicators if ind.lower() in sample)

    # Also check for common code structure patterns
    has_brackets = sample.count('{') > 2 or sample.count('(') > 5
    has_colons = sample.count(':') > 3  # Python function defs

    return matches >= 2 or (matches >= 1 and (has_brackets or has_colons))


def get_code_sample(content: str, file_size: int, max_chars: int = 6000) -> str:
    """
    Code-aware sampling that extracts semantically important parts.

    Instead of random position-based chunks, this extracts:
    1. Module docstring and imports (context)
    2. All class/function signatures with their docstrings (CAPABILITIES)
    3. Enum and dataclass definitions (domain models)

    Args:
        content: Full source code content
        file_size: Size of the file in bytes (for budget scaling)
        max_chars: Base maximum characters (will be scaled by file size)

    Returns:
        Sampled content focused on capability-revealing code structures
    """
    import re

    # 1. Scale budget by file size
    if file_size < 10000:  # < 10KB
        budget = max_chars  # Use default (6000)
    elif file_size < 50000:  # 10-50KB
        budget = max(max_chars, 12000)
    else:  # > 50KB
        budget = max(max_chars, 20000)

    parts = []

    # 2. Always get module docstring + imports (first 1500 chars for context)
    header = content[:1500]
    parts.append(header)

    # 3. Extract ALL class definitions with their docstrings
    # Pattern matches: class ClassName(Base): or class ClassName:
    class_pattern = r'(class\s+\w+[^:]*:)\s*("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')?'

    for match in re.finditer(class_pattern, content):
        signature = match.group(1).strip()
        docstring = (match.group(2) or "").strip()

        # Truncate long docstrings but keep the important first part
        if len(docstring) > 300:
            docstring = docstring[:300] + '..."""'

        parts.append(f"{signature}\n    {docstring}")

    # 4. Extract ALL function/method definitions with docstrings
    # Pattern matches: def function_name(args): or async def function_name(args):
    func_pattern = r'((?:async\s+)?def\s+\w+\s*\([^)]*\)[^:]*:)\s*("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')?'

    for match in re.finditer(func_pattern, content):
        signature = match.group(1).strip()
        docstring = (match.group(2) or "").strip()

        # Truncate long docstrings
        if len(docstring) > 250:
            docstring = docstring[:250] + '..."""'

        parts.append(f"{signature}\n    {docstring}")

    # 5. Get Enum definitions (domain models - often contain business categories)
    enum_pattern = r'(class\s+\w+\s*\(\s*Enum\s*\)\s*:[\s\S]*?)(?=\nclass\s|\ndef\s|\Z)'

    for match in re.finditer(enum_pattern, content):
        enum_block = match.group(1).strip()
        # Keep full enum if small, truncate if large
        if len(enum_block) > 600:
            enum_block = enum_block[:600] + "\n    # ... more values"
        parts.append(enum_block)

    # 6. Get dataclass definitions (data models)
    dataclass_pattern = r'(@dataclass[\s\S]*?class\s+\w+[^:]*:[\s\S]*?)(?=\n@|\nclass\s|\ndef\s|\Z)'

    for match in re.finditer(dataclass_pattern, content):
        dataclass_block = match.group(1).strip()
        if len(dataclass_block) > 500:
            dataclass_block = dataclass_block[:500] + "\n    # ... more fields"
        parts.append(dataclass_block)

    # 7. Look for TypedDict, NamedTuple, and Pydantic models
    typed_pattern = r'(class\s+\w+\s*\(\s*(?:TypedDict|NamedTuple|BaseModel)\s*\)\s*:[\s\S]*?)(?=\nclass\s|\ndef\s|\Z)'

    for match in re.finditer(typed_pattern, content):
        typed_block = match.group(1).strip()
        if len(typed_block) > 400:
            typed_block = typed_block[:400] + "\n    # ..."
        parts.append(typed_block)

    # 8. Combine, deduplicate, and truncate to budget
    combined = "\n\n".join(parts)

    # Remove duplicate sections (header might contain some class/func defs)
    # Simple dedup: if a signature appears twice, keep first occurrence
    seen_signatures = set()
    deduped_parts = []

    for part in parts:
        # Extract first line as signature key
        first_line = part.split('\n')[0].strip()
        if first_line not in seen_signatures:
            seen_signatures.add(first_line)
            deduped_parts.append(part)

    combined = "\n\n".join(deduped_parts)

    # Final truncation to budget
    if len(combined) > budget:
        combined = combined[:budget] + "\n\n# ... [truncated for length]"

    return combined


def get_document_sample(content: str, max_chars: int = 6000) -> str:
    """
    Get representative sample from beginning, middle, and end of documents.

    This is the ORIGINAL sampling logic - kept for non-code content like
    PDFs, articles, YouTube transcripts, etc.

    For content longer than max_chars, extracts three equal-sized chunks:
    - Beginning: First concepts and introduction
    - Middle: Core content and examples
    - End: Conclusions and advanced topics

    Args:
        content: Full document text
        max_chars: Maximum total characters to return

    Returns:
        Sampled content with section separators
    """
    if len(content) <= max_chars:
        return content

    chunk_size = max_chars // 3

    # Beginning - first chunk_size chars
    start = content[:chunk_size].strip()

    # Middle - centered chunk
    middle_pos = (len(content) // 2) - (chunk_size // 2)
    middle = content[middle_pos:middle_pos + chunk_size].strip()

    # End - last chunk_size chars
    end = content[-chunk_size:].strip()

    # Combine with clear separators
    return f"{start}\n\n[... content continued ...]\n\n{middle}\n\n[... content continued ...]\n\n{end}"


def get_representative_sample(content: str, max_chars: int = 6000, source_type: str = "") -> str:
    """
    Smart sampling that routes to the appropriate sampler based on content type.

    For source code: Uses code-aware sampling that extracts signatures + docstrings
    For documents: Uses position-based sampling (beginning/middle/end)

    Args:
        content: Full content text
        max_chars: Maximum characters for the sample
        source_type: Optional hint about content type ("code", "pdf", "youtube", etc.)

    Returns:
        Representative sample optimized for the content type
    """
    # Check if explicitly marked as code or auto-detect
    is_code = source_type in ("code", "python", "javascript", "java", "typescript")

    if not is_code:
        is_code = _is_code(content)

    if is_code:
        file_size = len(content)
        sample = get_code_sample(content, file_size, max_chars)
        return sample
    else:
        return get_document_sample(content, max_chars)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def extract_concepts(
        self,
        content: str,
        source_type: str
    ) -> Dict:
        """
        Extract concepts from content.

        Args:
            content: Content to analyze
            source_type: Type of content (text, pdf, etc.)

        Returns:
            Dict with concepts, skill_level, primary_topic, suggested_cluster
        """
        pass

    @abstractmethod
    async def generate_build_suggestions(
        self,
        knowledge_summary: str,
        max_suggestions: int
    ) -> List[Dict]:
        """
        Generate project build suggestions.

        Args:
            knowledge_summary: Summary of user's knowledge bank
            max_suggestions: Maximum number of suggestions

        Returns:
            List of build suggestion dictionaries
        """
        pass

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict],
        temperature: float = 0.7
    ) -> str:
        """
        Generic chat completion for various tasks.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)

        Returns:
            Response text
        """
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI implementation of LLM provider."""

    def __init__(
        self,
        api_key: str = None,
        concept_model: str = "gpt-5-nano",
        suggestion_model: str = "gpt-5-mini"
    ):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (defaults to settings.openai_api_key)
            concept_model: Model for concept extraction
            suggestion_model: Model for build suggestions
        """
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise ValueError("OpenAI API key required")

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            max_retries=0  # Disable OpenAI client retries (we handle retries ourselves)
        )
        self.concept_model = concept_model
        self.suggestion_model = suggestion_model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True
    )
    async def _call_openai(
        self,
        messages: List[Dict],
        model: str,
        max_tokens: int,
        temperature: float = 1.0
    ) -> str:
        """Call OpenAI API with retry logic."""
        logger.info(f"Calling OpenAI with model: {model}")

        # GPT-5 models use fixed sampling and different parameters
        # - No temperature support (uses fixed sampling)
        # - Use max_completion_tokens instead of max_tokens
        params = {
            "model": model,
            "messages": messages
        }

        if model.startswith("gpt-5"):
            # GPT-5 models use max_completion_tokens and no temperature
            params["max_completion_tokens"] = max_tokens
        else:
            # GPT-4 and earlier use max_tokens and temperature
            params["max_tokens"] = max_tokens
            params["temperature"] = temperature

        response = await self.client.chat.completions.create(**params)
        content = response.choices[0].message.content

        # Track usage and costs
        if hasattr(response, 'usage') and response.usage:
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens

            # Calculate cost (USD per 1K tokens)
            PRICING = {
                "gpt-4o": (0.00250, 0.01000),
                "gpt-4o-mini": (0.00015, 0.00060),
                "gpt-4o-mini-transcribe": (0.00015, 0.00060),
                "gpt-4-turbo": (0.01000, 0.03000),
                "gpt-3.5-turbo": (0.00050, 0.00150),
                # GPT-5 models (released August 2025)
                "gpt-5": (0.00125, 0.01000),  # $1.25/$10 per 1M tokens
                "gpt-5-mini": (0.00025, 0.00200),  # $0.25/$2 per 1M tokens
                "gpt-5-nano": (0.00005, 0.00040),  # $0.05/$0.40 per 1M tokens
            }
            input_price, output_price = PRICING.get(model, PRICING["gpt-4o-mini"])
            cost_usd = (prompt_tokens / 1000 * input_price) + (completion_tokens / 1000 * output_price)

            logger.info(
                f"📊 OpenAI usage: model={model}, tokens={prompt_tokens}+{completion_tokens}={total_tokens}, cost=${cost_usd:.6f}"
            )

        logger.info(f"API response - finish_reason: {response.choices[0].finish_reason}, content length: {len(content) if content else 0}")
        return content or ""  # Return empty string if None

    async def extract_concepts(
        self,
        content: str,
        source_type: str
    ) -> Dict:
        """Extract concepts using OpenAI."""
        from .config import settings

        # Smart sampling: extract from beginning, middle, and end
        if settings.concept_sample_method == "smart":
            sample = get_representative_sample(content, max_chars=settings.concept_sample_size)
            sampling_note = "\nNOTE: For long documents, this is a representative sample from beginning, middle, and end."
        else:
            # Fallback to simple truncation
            sample = content[:settings.concept_sample_size] if len(content) > settings.concept_sample_size else content
            sampling_note = ""

        # Detect YouTube transcripts
        is_youtube = "YOUTUBE VIDEO TRANSCRIPT" in content or source_type == "youtube"

        if is_youtube:
            prompt = self._build_youtube_prompt(sample, sampling_note)
        else:
            prompt = self._build_standard_prompt(sample, source_type, sampling_note)

        try:
            response = await self._call_openai(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a concept extraction system. Return only valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                model=self.concept_model,
                temperature=0.3,
                max_tokens=4000
            )

            # Parse JSON response
            logger.debug(f"OpenAI raw response: {response[:200]}")  # Log first 200 chars
            result = json.loads(response)
            logger.debug(f"Extracted {len(result.get('concepts', []))} concepts")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from OpenAI: {e}")
            logger.error(f"Raw response was: {response[:500]}")
            return {
                "concepts": [],
                "skill_level": "unknown",
                "primary_topic": "uncategorized",
                "suggested_cluster": "General"
            }
        except Exception as e:
            logger.error(f"Concept extraction failed: {e}")
            return {
                "concepts": [],
                "skill_level": "unknown",
                "primary_topic": "uncategorized",
                "suggested_cluster": "General"
            }

    def _build_youtube_prompt(self, sample: str, sampling_note: str = "") -> str:
        """Build specialized prompt for YouTube transcripts."""
        return f"""Analyze this YouTube video transcript and extract comprehensive information.{sampling_note}

TRANSCRIPT:
{sample}

Return ONLY valid JSON (no markdown, no explanation) with this structure:
{{
  "title": "Full video title",
  "creator": "Channel or creator name",
  "concepts": [
    {{"name": "concept name", "category": "language|framework|library|tool|platform|database|methodology|architecture|testing|devops|concept", "confidence": 0.9}}
  ],
  "skill_level": "beginner|intermediate|advanced",
  "primary_topic": "main topic in 2-4 words",
  "suggested_cluster": "cluster name for grouping similar content",
  "target_audience": "Who this video is for (e.g., 'Python beginners', 'DevOps engineers')",
  "key_takeaways": ["Main point 1", "Main point 2", "Main point 3"],
  "video_type": "tutorial|talk|demo|discussion|course|review",
  "estimated_watch_time": "Approximate length (e.g., '15 minutes', '1 hour')"
}}

CATEGORY DEFINITIONS:
- language: Programming languages (python, javascript, rust)
- framework: Web/app frameworks (react, django, spring)
- library: Code libraries (pandas, numpy, lodash)
- tool: Development tools (docker, git, webpack)
- platform: Cloud/hosting platforms (aws, azure, vercel)
- database: Databases (postgresql, mongodb, redis)
- methodology: Development practices (agile, tdd, ci/cd)
- architecture: System design patterns (microservices, mvc, rest)
- testing: Testing approaches (unit testing, e2e, jest)
- devops: Operations concepts (kubernetes, terraform, monitoring)
- concept: General programming concepts (async, orm, api)

Extract 3-10 concepts from the actual content discussed. Be specific. Use lowercase for concept names. Set confidence 0.7-1.0 based on how clearly the concept is discussed."""

    def _build_standard_prompt(self, sample: str, source_type: str, sampling_note: str = "") -> str:
        """Build standard prompt for non-YouTube content."""
        return f"""Analyze this {source_type} content and extract BOTH capabilities AND technologies.{sampling_note}

CONTENT:
{sample}

Return ONLY valid JSON (no markdown, no explanation) with this structure:
{{
  "concepts": [
    {{"name": "concept name", "category": "...", "confidence": 0.9}}
  ],
  "skill_level": "beginner|intermediate|advanced",
  "primary_topic": "main topic in 2-4 words",
  "suggested_cluster": "cluster name for grouping similar content"
}}

EXTRACTION PRIORITY:
1. CAPABILITIES FIRST - What problems does this solve? What can it DO?
   PRIORITIZE:   - Domain-specific engines (cost calculators, security analyzers, risk scorers)
   - Complex business logic (industry multipliers, compliance checks, audit trails)
   - Data processing algorithms (parsing, scoring, matching, detection)
   OVER:
   - Generic CRUD operations (create/read/update/delete)
   - Simple API scaffolds (basic REST endpoints)
   - Standard auth patterns (login/logout/token refresh)
2. TECHNOLOGIES SECOND - What tools/frameworks does it use?

CATEGORIES:
Technologies: language | framework | library | tool | platform | database | devops
Patterns: methodology | architecture | testing | concept
Capabilities: capability | problem_domain | business_logic | algorithm | integration_pattern

CATEGORY DEFINITIONS:
- language: Programming languages (python, javascript, rust)
- framework: Web/app frameworks (react, django, spring)
- library: Code libraries (pandas, numpy, lodash)
- tool: Development tools (docker, git, webpack)
- platform: Cloud/hosting platforms (aws, azure, vercel)
- database: Databases (postgresql, mongodb, redis)
- methodology: Development practices (agile, tdd, ci/cd)
- architecture: System design patterns (microservices, mvc, rest)
- testing: Testing approaches (unit testing, e2e, jest)
- devops: Operations concepts (kubernetes, terraform, monitoring)
- concept: General programming concepts (async, orm, api)
- capability: Functional abilities (cost estimation, vulnerability scanning, auth flows)
- problem_domain: Business domains (e-commerce, healthcare, fintech)
- business_logic: Logic patterns (tenant isolation, rate limiting, audit trails)
- algorithm: Computational approaches (risk scoring, similarity matching)
- integration_pattern: System connections (webhook handling, API orchestration)

Extract 5-15 concepts. Prioritize CAPABILITIES over technologies. Use lowercase for names. Set confidence 0.7-1.0 based on how clearly the concept is discussed."""

    async def generate_build_suggestions(
        self,
        knowledge_summary: str,
        max_suggestions: int
    ) -> List[Dict]:
        """Generate build suggestions using OpenAI."""
        prompt = f"""Based on this user's knowledge bank, suggest {max_suggestions} practical projects they could build RIGHT NOW.

KNOWLEDGE BANK:
{knowledge_summary}

Return ONLY a JSON array of suggestions (no markdown, no explanation):
[
  {{
    "title": "Project Name",
    "description": "What they'll build and why it's valuable",
    "feasibility": "high|medium|low",
    "effort_estimate": "2-3 days",
    "required_skills": ["skill1", "skill2"],
    "missing_knowledge": ["gap1", "gap2"],
    "relevant_clusters": [1, 2],
    "starter_steps": ["step 1", "step 2", "step 3"],
    "file_structure": "project/\\n  src/\\n  tests/\\n  README.md"
  }}
]

Be specific. Reference actual content from their knowledge. Prioritize projects they can START TODAY."""

        try:
            response = await self._call_openai(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a project advisor. Return only valid JSON arrays of build suggestions."
                    },
                    {"role": "user", "content": prompt}
                ],
                model=self.suggestion_model,
                temperature=0.7,
                max_tokens=2000
            )

            # Parse JSON response
            suggestions = json.loads(response)
            logger.info(f"Generated {len(suggestions)} build suggestions")
            return suggestions

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from OpenAI: {e}")
            return []
        except Exception as e:
            logger.error(f"Build suggestion generation failed: {e}")
            return []

    async def generate_build_suggestions_improved(
        self,
        knowledge_summary: str,
        knowledge_areas: List[Dict],
        validation_info: Dict,
        max_suggestions: int,
        enable_quality_filter: bool = True
    ) -> List[Dict]:
        """
        Generate IMPROVED build suggestions with depth analysis.

        Includes:
        - Actual content snippets (not just concept names)
        - Knowledge area detection
        - Minimum threshold validation
        - Feasibility checks
        - Optional quality filtering (can be disabled)

        Args:
            knowledge_summary: Rich summary of user's knowledge
            knowledge_areas: Detected knowledge areas
            validation_info: Knowledge depth validation info
            max_suggestions: Number of suggestions to generate
            enable_quality_filter: If True, filter out low-coverage suggestions

        Prompt optimization history:
        - 2025-12-03: Removed Flask code example from prompt (reduced ~650 tokens per request)
          Old version had full 50-line Flask auth example embedded in prompt.
          If quality degrades, revert this commit.
        """
        stats = validation_info["stats"]

        # Build areas summary
        areas_text = "\n".join([
            f"- {area['name']}: {area['document_count']} docs, {len(area['core_concepts'])} concepts ({area['skill_level']})"
            for area in knowledge_areas
        ])

        prompt_template = string.Template(
            """Based on this VALIDATED knowledge bank, analyze the ACTUAL CONTENT below and suggest ${max_suggestions} DETAILED practical projects.

KNOWLEDGE VALIDATION:
✅ ${stats_docs} documents analyzed
✅ ${stats_concepts} unique concepts extracted
✅ ${stats_clusters} knowledge areas identified
✅ Skill levels: ${stats_skill_levels}

KNOWLEDGE AREAS:
${areas_text}

DETAILED KNOWLEDGE CONTENT (analyze THIS to generate suggestions):
${knowledge_summary}

Return ONLY a JSON array with COMPREHENSIVE, ACTIONABLE project suggestions:
[
  {{
    "title": "Specific Project Name",
    "description": "What they'll build and WHY (reference their actual knowledge)",
    "feasibility": "high|medium|low",
    "effort_estimate": "X hours/days",
    "complexity_level": "beginner|intermediate|advanced",
    "required_skills": ["skill1", "skill2"],
    "missing_knowledge": ["specific gap 1", "specific gap 2"],
    "relevant_clusters": [0, 1],
    "starter_steps": [
      "Step 1: Set up project structure based on their tech stack",
      "Step 2: Create main entry point using frameworks from their knowledge",
      "Step 3: Define data models relevant to the project",
      "Step 4: Implement core functionality",
      "Step 5: Add error handling and validation",
      "Step 6: Write tests",
      "Step 7: Document and deploy"
    ],
    "file_structure": "Appropriate structure for the chosen tech stack",
    "starter_code": "Complete, working code using technologies from their knowledge base. Must be production-ready with proper error handling, validation, and best practices for their specific stack.",
    "learning_path": [
      "Resources tailored to concepts from their knowledge base",
      "Practical exercises building on what they already know",
      "Advanced topics that extend their current skills"
    ],
    "recommended_resources": [
      "Official documentation for technologies in their KB",
      "Tutorials relevant to their skill level",
      "Community resources for their stack"
    ],
    "expected_outcomes": [
      "Working implementation using their known technologies",
      "Skills reinforced through practical application",
      "Portfolio-ready project"
    ],
    "troubleshooting_tips": [
      "Common issues specific to their tech stack",
      "Configuration guidance for their tools",
      "Debugging strategies for their frameworks"
    ],
    "knowledge_coverage": "high|medium|low (how much of their knowledge applies)"
  }}
]

IMPORTANT:
- COMBINE CAPABILITIES to create novel solutions:
  • Find capability A + capability B → New use case they haven't built
  • Example: "cost estimation" + "vulnerability scoring" → "Security budget planner"
  • Example: "tech stack detection" + "industry multipliers" → "Repo cloud cost estimator"
- Do NOT just recombine the same tech stack with different nouns
- Reference ACTUAL capabilities from their knowledge, not just frameworks
- Provide 5-10 DETAILED starter steps
- Include WORKING starter code snippets
- Add SPECIFIC learning resources and timelines
- Give PRACTICAL troubleshooting tips
- Only suggest if they have ENOUGH depth (check knowledge_coverage)
- Be SPECIFIC - not generic
- Prioritize NOVEL combinations over rebuilding what they already have"""

        )

        try:
            prompt = prompt_template.substitute(
                max_suggestions=max_suggestions,
                stats_docs=stats["total_documents"],
                stats_concepts=stats["unique_concepts"],
                stats_clusters=stats["total_clusters"],
                stats_skill_levels=", ".join(f"{k}: {v}" for k, v in stats["skill_distribution"].items()),
                areas_text=areas_text,
                knowledge_summary=knowledge_summary
            )

            response = await self._call_openai(
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert project advisor and mentor who creates comprehensive, actionable project plans.

YOUR ROLE:
1. Analyze the user's knowledge depth from their documents
2. Suggest projects that MATCH their current skill level
3. Provide PRODUCTION-READY starter code (not Hello World examples)
4. Include realistic learning paths and timelines

STARTER CODE REQUIREMENTS:
- Include proper imports and dependencies
- Add error handling and input validation
- Use environment variables for configuration
- Include authentication where relevant
- Add database models with proper constraints
- Make it WORKING and DEPLOYABLE

QUALITY FILTER:
- Only suggest projects where knowledge_coverage is "high" or "medium"
- Don't suggest projects requiring skills not in their documents
- Match complexity to their demonstrated skill level

OUTPUT: Return ONLY valid JSON with no markdown formatting."""
                    },
                    {"role": "user", "content": prompt}
                ],
                model=self.suggestion_model,
                max_tokens=16000  # Note: temperature removed - GPT-5 models only support temperature=1 (default)
            )

            suggestions = json.loads(response)

            # Conditionally filter out low-coverage suggestions
            if enable_quality_filter:
                filtered = [
                    s for s in suggestions
                    if s.get("knowledge_coverage", "low") in ["high", "medium"]
                ]
                logger.info(f"Generated {len(filtered)} high-quality suggestions (filtered {len(suggestions) - len(filtered)})")
                return filtered
            else:
                logger.info(f"Generated {len(suggestions)} suggestions (quality filter disabled)")
                return suggestions

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return []
        except Exception as e:
            logger.error(f"Improved suggestion generation failed: {e}")
            return []

    async def chat_completion(
        self,
        messages: List[Dict],
        temperature: float = 0.7
    ) -> str:
        """
        Generic chat completion for various tasks.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)

        Returns:
            Response text
        """
        try:
            response = await self._call_openai(
                messages=messages,
                model=self.concept_model,  # Use faster model for generic tasks
                temperature=temperature,
                max_tokens=500
            )
            return response
        except Exception as e:
            logger.error(f"Chat completion failed: {e}")
            raise

    async def generate_goal_driven_suggestions(
        self,
        knowledge_summary: str,
        knowledge_areas: List[Dict],
        validation_info: Dict,
        user_goals: Dict,
        past_attempts: List[Dict],
        max_suggestions: int = 5
    ) -> List[Dict]:
        """
        Generate suggestions BASED ON USER'S GOALS and past experience.

        This is the enhanced version that considers:
        - User's primary goal (revenue, learning, portfolio, automation)
        - Constraints (time, budget, tech stack)
        - Past project attempts and learnings

        Args:
            knowledge_summary: Rich summary of knowledge
            knowledge_areas: Detected knowledge areas
            validation_info: Knowledge depth validation
            user_goals: {
                'primary_goal': 'revenue|learning|portfolio|automation',
                'constraints': {
                    'time_available': 'weekends|full-time|evenings',
                    'budget': 0,
                    'target_market': 'B2B SaaS|B2C|Internal tools',
                    'tech_stack_preference': 'Python/FastAPI|JavaScript/React|etc',
                    'deployment_preference': 'Docker|Heroku|Vercel|etc'
                }
            }
            past_attempts: List of past project attempts with learnings
            max_suggestions: Number of suggestions to generate

        Returns:
            List of comprehensive project suggestions with working code
        """

        # Build past learnings section
        past_learnings = ""
        if past_attempts:
            past_learnings = "\n\n## PAST PROJECT HISTORY:\n"
            for attempt in past_attempts:
                status = attempt.get('status', 'unknown')
                emoji = "✅" if status == "completed" else "❌" if status == "abandoned" else "🔄"
                past_learnings += f"\n{emoji} {attempt.get('title', 'Project')} ({status})\n"
                past_learnings += f"   Time spent: {attempt.get('time_spent_hours', 0)} hours\n"
                if attempt.get('learnings'):
                    past_learnings += f"   Learnings: {attempt['learnings']}\n"

            past_learnings += "\n**KEY PATTERNS:**\n"
            completed = [a for a in past_attempts if a.get('status') == 'completed']
            abandoned = [a for a in past_attempts if a.get('status') == 'abandoned']

            if completed:
                avg_time = sum(c.get('time_spent_hours', 0) for c in completed) / len(completed)
                past_learnings += f"- User completes projects in ~{avg_time:.0f} hours on average\n"

            if abandoned:
                past_learnings += f"- {len(abandoned)} projects abandoned - likely scope was too large\n"
                past_learnings += "- **RECOMMENDATION:** Suggest smaller, focused projects\n"

        # Build constraints section
        constraints = user_goals.get('constraints', {})
        constraints_text = f"""
## USER CONSTRAINTS:
- Time Available: {constraints.get('time_available', 'weekends')}
- Budget: £{constraints.get('budget', 0)}
- Target Market: {constraints.get('target_market', 'B2B SaaS')}
- Preferred Stack: {constraints.get('tech_stack_preference', 'Python/FastAPI')}
- Deployment: {constraints.get('deployment_preference', 'Docker')}
"""

        # Build goal-specific instructions
        goal = user_goals.get('primary_goal', 'revenue')
        goal_instructions = {
            'revenue': """
**PRIMARY GOAL: REVENUE GENERATION**
- Prioritize projects that can generate income within 1-3 months
- Focus on solving REAL problems people will pay for
- Suggest SaaS, automation tools, or productized services
- Include pricing strategy and revenue estimates
- Validate market demand exists
- Prefer B2B over B2C (faster sales cycles)
""",
            'learning': """
**PRIMARY GOAL: SKILL DEVELOPMENT**
- Prioritize projects that teach NEW technologies
- Include learning path with resources
- Suggest projects that are challenging but achievable
- Focus on portfolio-worthy outcomes
- Include skill progression (current → target)
""",
            'portfolio': """
**PRIMARY GOAL: PORTFOLIO BUILDING**
- Prioritize impressive, showcase-worthy projects
- Must have visual/demo-able components
- Include deployment instructions for live demos
- Suggest projects that demonstrate full-stack skills
- Focus on polish and user experience
""",
            'automation': """
**PRIMARY GOAL: PERSONAL AUTOMATION**
- Prioritize time-saving tools for personal use
- Focus on practical, daily-use applications
- Include n8n workflows where applicable
- Suggest integration-heavy solutions
- Quick wins over complex builds
"""
        }

        stats = validation_info.get("stats", {})
        areas_text = "\n".join([
            f"- {area['name']}: {area['document_count']} docs, {len(area.get('core_concepts', []))} concepts ({area.get('skill_level', 'unknown')})"
            for area in knowledge_areas
        ])

        prompt = f"""You are an expert project advisor and startup mentor. Generate {max_suggestions} HIGHLY DETAILED, ACTIONABLE project suggestions.

{goal_instructions.get(goal, goal_instructions['revenue'])}

{constraints_text}

{past_learnings}

## KNOWLEDGE VALIDATION:
✅ {stats.get('total_documents', 0)} documents analyzed
✅ {stats.get('unique_concepts', 0)} unique concepts extracted
✅ {stats.get('total_clusters', 0)} knowledge areas identified
✅ Skill levels: {', '.join(f"{k}: {v}" for k, v in stats.get('skill_distribution', {}).items())}

## KNOWLEDGE AREAS:
{areas_text}

## DETAILED KNOWLEDGE CONTENT:
{knowledge_summary}

---

Return ONLY a valid JSON array with this structure:

[
  {{
    "title": "Specific Project Name",
    "description": "Detailed description of what they'll build and WHY it matters for their goal",
    "goal_alignment_score": 95,
    "feasibility": "high|medium|low",
    "effort_estimate_hours": 20,
    "complexity_level": "beginner|intermediate|advanced",

    "revenue_potential": {{
      "monthly_estimate": "$500-2000",
      "pricing_strategy": "Subscription $29/mo or one-time $199",
      "target_customer": "Small business owners",
      "time_to_first_sale": "2-4 weeks"
    }},

    "learning_outcomes": [
      "Master specific technology",
      "Understand key concept",
      "Build production skill"
    ],

    "required_skills": ["Python", "FastAPI", "PostgreSQL"],
    "missing_knowledge": ["Specific gaps to fill"],
    "knowledge_coverage_percent": 85,

    "market_validation": {{
      "competitors": ["Tool X", "Tool Y"],
      "unique_advantage": "Your advantage based on knowledge",
      "market_size": "5000-10000 potential customers",
      "demand_validation": "Evidence of demand"
    }},

    "starter_steps": [
      "1. Set up project: pip install fastapi uvicorn",
      "2. Create database models",
      "3. Implement core API endpoints",
      "4. Add authentication",
      "5. Deploy to production"
    ],

    "generated_code": {{
      "main.py": "from fastapi import FastAPI\\napp = FastAPI()\\n\\n@app.get('/')\\ndef root():\\n    return {{'message': 'API running'}}",
      "requirements.txt": "fastapi==0.104.1\\nuvicorn[standard]==0.24.0",
      "Dockerfile": "FROM python:3.11-slim\\nWORKDIR /app\\nCOPY . .\\nRUN pip install -r requirements.txt\\nCMD [\\"uvicorn\\", \\"main:app\\", \\"--host\\", \\"0.0.0.0\\"]"
    }},

    "learning_path": [
      {{
        "topic": "FastAPI Basics",
        "resources": ["https://fastapi.tiangolo.com/tutorial/"],
        "estimated_time": "4 hours"
      }}
    ],

    "deployment_guide": {{
      "steps": ["Build image", "Push to registry", "Deploy"],
      "estimated_cost": "£5-15/month",
      "recommended_services": ["Railway.app", "Render.com"]
    }},

    "success_metrics": [
      "10 beta users signed up",
      "5 paying customers",
      "90% uptime"
    ],

    "potential_challenges": [
      {{
        "challenge": "Integration complexity",
        "solution": "Use established library",
        "resources": ["Documentation link"]
      }}
    ],

    "next_steps_after_mvp": [
      "Add email notifications",
      "Create landing page",
      "Launch on Product Hunt"
    ]
  }}
]

**CRITICAL REQUIREMENTS:**
1. Generated code MUST be COMPLETE and RUNNABLE
2. Reference their ACTUAL knowledge from docs
3. Be SPECIFIC to their tech stack
4. Calculate knowledge_coverage_percent accurately
5. Only suggest if coverage >= 70%
6. Include market validation for revenue goals
7. Include learning path for learning goals
8. ALL code must follow best practices
9. Consider past project patterns"""

        try:
            response = await self._call_openai(
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert startup advisor, technical architect, and career mentor.

YOUR SPECIALTIES BY USER GOAL:

REVENUE GOAL:
- Focus on projects that can generate income within 1-3 months
- Suggest SaaS, automation tools, or productized services
- Include pricing strategy and realistic revenue estimates
- Prefer B2B over B2C (faster sales cycles)

LEARNING GOAL:
- Prioritize projects that teach NEW technologies
- Include skill progression (current → target)
- Focus on portfolio-worthy outcomes
- Suggest challenging but achievable projects

PORTFOLIO GOAL:
- Prioritize impressive, showcase-worthy projects
- Must have visual/demo-able components
- Include deployment instructions for live demos
- Focus on polish and user experience

AUTOMATION GOAL:
- Focus on time-saving tools for personal use
- Include n8n workflows where applicable
- Quick wins over complex builds
- Suggest integration-heavy solutions

CODE REQUIREMENTS:
- Generate COMPLETE, RUNNABLE code
- Include proper error handling
- Use environment variables for config
- Follow best practices for the tech stack

OUTPUT: Return ONLY valid JSON with no markdown formatting."""
                    },
                    {"role": "user", "content": prompt}
                ],
                model=self.suggestion_model,
                temperature=0.5,
                max_tokens=32000
            )

            suggestions = json.loads(response)
            logger.info(f"Generated {len(suggestions)} goal-driven suggestions")
            return suggestions

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Response was: {response[:500] if response else 'empty'}...")
            return []
        except Exception as e:
            logger.error(f"Goal-driven suggestion generation failed: {e}")
            return []

    async def generate_n8n_workflow(
        self,
        task_description: str,
        knowledge_summary: str,
        available_integrations: List[str],
        user_examples: List[Dict] = None
    ) -> Dict:
        """
        Generate a COMPLETE n8n workflow JSON from task description.

        Args:
            task_description: What the workflow should do
            knowledge_summary: User's knowledge (for context)
            available_integrations: List of services user has access to
            user_examples: Existing n8n workflows from user's docs for reference

        Returns:
            {
                'workflow': {...},  # Complete n8n JSON
                'setup_instructions': str,
                'required_credentials': [...],
                'testing_steps': [...]
            }
        """

        examples_text = ""
        if user_examples:
            examples_text = "\n\n## USER'S EXISTING WORKFLOWS (for reference):\n"
            for ex in user_examples[:3]:
                examples_text += f"\n{ex.get('name', 'Workflow')}: {ex.get('description', '')}\n"
                if ex.get('nodes'):
                    examples_text += f"Nodes: {', '.join(str(n) for n in ex['nodes'][:5])}\n"

        integrations_text = ", ".join(available_integrations) if available_integrations else "All standard n8n nodes"

        # Truncate knowledge summary for token budget
        truncated_knowledge = knowledge_summary[:3000] if knowledge_summary else ""

        prompt = f"""Generate a COMPLETE n8n workflow for this task:

**TASK:** {task_description}

**AVAILABLE INTEGRATIONS:** {integrations_text}

**USER'S KNOWLEDGE CONTEXT:**
{truncated_knowledge}

{examples_text}

Return a JSON object with this EXACT structure:

{{
  "workflow": {{
    "name": "Workflow Name",
    "nodes": [
      {{
        "parameters": {{}},
        "name": "Start",
        "type": "n8n-nodes-base.start",
        "typeVersion": 1,
        "position": [250, 300]
      }},
      {{
        "parameters": {{
          "httpMethod": "POST",
          "path": "webhook",
          "responseMode": "responseNode",
          "options": {{}}
        }},
        "name": "Webhook",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 1,
        "position": [450, 300],
        "webhookId": "unique-id-here"
      }}
    ],
    "connections": {{
      "Start": {{
        "main": [[{{ "node": "Webhook", "type": "main", "index": 0 }}]]
      }}
    }},
    "settings": {{
      "executionOrder": "v1"
    }},
    "staticData": null,
    "tags": [],
    "triggerCount": 1,
    "updatedAt": "2024-01-01T00:00:00.000Z",
    "versionId": "1"
  }},

  "setup_instructions": "1. Import this JSON into n8n\\n2. Configure credentials\\n3. Activate the workflow\\n4. Test with webhook URL",

  "required_credentials": [
    {{
      "service": "Gmail",
      "type": "gmailOAuth2",
      "setup_url": "https://docs.n8n.io/integrations/builtin/credentials/google/"
    }}
  ],

  "testing_steps": [
    "1. Send test POST request to webhook URL",
    "2. Check execution log in n8n",
    "3. Verify data in destination service"
  ],

  "workflow_description": "This workflow does X, Y, Z.",

  "trigger_type": "webhook|schedule|manual",
  "estimated_executions_per_day": 50,
  "complexity": "simple|medium|complex",

  "potential_improvements": [
    "Add error notification",
    "Implement retry logic",
    "Add logging"
  ]
}}

**REQUIREMENTS:**
1. Workflow MUST be complete and importable into n8n
2. Use only nodes from available_integrations
3. Include proper error handling nodes
4. Set realistic node positions for visual layout
5. All connections must be valid
6. Include webhook/trigger configuration"""

        try:
            response = await self._call_openai(
                messages=[
                    {
                        "role": "system",
                        "content": """You are an n8n workflow automation expert who creates production-ready workflows.

N8N SCHEMA REQUIREMENTS:
- Every workflow needs a trigger node (webhook, schedule, or manual)
- Nodes must have unique names
- Connections format: {"NodeName": {"main": [[{"node": "NextNode", "type": "main", "index": 0}]]}}
- Position coordinates should create a left-to-right visual flow
- Include error handling with IF nodes where appropriate

COMMON NODE TYPES:
- n8n-nodes-base.webhook (HTTP trigger)
- n8n-nodes-base.schedule (cron trigger)
- n8n-nodes-base.httpRequest (API calls)
- n8n-nodes-base.if (conditional logic)
- n8n-nodes-base.set (transform data)
- n8n-nodes-base.gmail / n8n-nodes-base.slack (integrations)

OUTPUT REQUIREMENTS:
1. workflow: Complete, importable n8n JSON
2. setup_instructions: Step-by-step setup guide
3. required_credentials: What API keys/auth needed
4. testing_steps: How to verify it works

Return ONLY valid JSON with no markdown formatting."""
                    },
                    {"role": "user", "content": prompt}
                ],
                model=self.suggestion_model,
                temperature=0.3,
                max_tokens=16000
            )

            result = json.loads(response)
            logger.info(f"Generated n8n workflow: {result.get('workflow', {}).get('name', 'Unknown')}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in n8n generation: {e}")
            return {
                "error": "Failed to generate valid workflow JSON",
                "workflow": None
            }
        except Exception as e:
            logger.error(f"n8n workflow generation failed: {e}")
            return {
                "error": str(e),
                "workflow": None
            }


class OllamaProvider(LLMProvider):
    """
    Ollama implementation of LLM provider for self-hosted models.

    Supports local models like llama2, codellama, mistral, mixtral, etc.
    Ollama API is compatible with OpenAI's API format.

    Setup:
        1. Install Ollama: https://ollama.ai/download
        2. Pull a model: ollama pull llama2
        3. Run Ollama server: ollama serve
        4. Set OLLAMA_BASE_URL (default: http://localhost:11434)
    """

    def __init__(
        self,
        base_url: str = None,
        concept_model: str = None,
        suggestion_model: str = None,
        timeout: int = 120
    ):
        """
        Initialize Ollama provider.

        Args:
            base_url: Ollama API URL (default: settings.ollama_base_url)
            concept_model: Model for concept extraction (default: settings.ollama_concept_model)
            suggestion_model: Model for build suggestions (default: settings.ollama_suggestion_model)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or settings.ollama_base_url
        self.concept_model = concept_model or settings.ollama_concept_model
        self.suggestion_model = suggestion_model or settings.ollama_suggestion_model
        self.timeout = timeout

        logger.info(f"Initialized OllamaProvider with base_url={self.base_url}, models={self.concept_model}/{self.suggestion_model}")

    async def _call_ollama(
        self,
        messages: List[Dict],
        model: str,
        temperature: float = 0.7
    ) -> str:
        """Call Ollama API with chat format."""
        import httpx

        url = f"{self.base_url}/api/chat"

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }

        logger.info(f"Calling Ollama model: {model}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()

                result = response.json()
                content = result.get("message", {}).get("content", "")
                logger.info(f"Ollama response length: {len(content)} chars")
                return content

        except httpx.TimeoutException:
            logger.error(f"Ollama request timed out after {self.timeout}s")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            raise

    def _extract_json_from_response(self, response: str) -> str:
        """
        Extract JSON from potentially wrapped LLM response.

        Ollama models sometimes add explanatory text around JSON.
        """
        import re

        # First, try to parse the entire response as JSON
        try:
            json.loads(response)
            return response
        except json.JSONDecodeError:
            pass

        # Try to find JSON in code blocks or raw - object patterns before array
        # to avoid matching nested arrays before the containing object
        json_patterns = [
            r'```json\s*([\s\S]*?)\s*```',  # Markdown code block
            r'```\s*([\s\S]*?)\s*```',       # Generic code block
            r'(\{[\s\S]*\})',                # JSON object (before array!)
            r'(\[[\s\S]*\])',                # JSON array
        ]

        for pattern in json_patterns:
            match = re.search(pattern, response)
            if match:
                candidate = match.group(1)
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    continue

        # Return original if no valid JSON found
        return response

    async def extract_concepts(
        self,
        content: str,
        source_type: str
    ) -> Dict:
        """Extract concepts using Ollama."""
        from .config import settings

        # Smart sampling
        if settings.concept_sample_method == "smart":
            sample = get_representative_sample(content, max_chars=settings.concept_sample_size)
        else:
            sample = content[:settings.concept_sample_size] if len(content) > settings.concept_sample_size else content

        prompt = f"""Analyze this {source_type} content and extract BOTH capabilities AND technologies.

CONTENT:
{sample}

EXTRACTION PRIORITY:
1. CAPABILITIES FIRST - What problems does this solve? What can it DO?
   Examples: "cloud cost estimation", "vulnerability scoring", "tenant isolation"
   PRIORITIZE: Domain-specific engines, complex business logic, data processing algorithms
   OVER: Generic CRUD, simple API scaffolds, standard auth patterns
2. TECHNOLOGIES SECOND - What tools/frameworks does it use?
   Examples: "python", "django", "postgresql"

Return ONLY valid JSON (no markdown, no explanation) with this exact structure:
{{
  "concepts": [
    {{"name": "concept name", "category": "capability|problem_domain|business_logic|algorithm|integration_pattern|language|framework|library|tool|platform|database|methodology|architecture|testing|devops|concept", "confidence": 0.9}}
  ],
  "skill_level": "beginner|intermediate|advanced",
  "primary_topic": "main topic in 2-4 words",
  "suggested_cluster": "cluster name for grouping similar content"
}}

Extract 5-15 concepts. Prioritize CAPABILITIES over technologies. Use lowercase for names. Be specific."""

        try:
            response = await self._call_ollama(
                messages=[
                    {"role": "system", "content": """You are an expert technical concept extraction system.

Extract BOTH capabilities AND technologies from documents:
1. CAPABILITIES - What problems does this solve? (cost estimation, vulnerability scanning, etc.)
2. TECHNOLOGIES - What tools does it use? (python, django, etc.)

- Code examples = HIGH confidence (0.9+)
- Prose mentions = MEDIUM confidence (0.7-0.85)
- Use lowercase for concept names
- Never extract vague terms like "programming", "code", "web"
- Prioritize CAPABILITIES over technologies

Return ONLY valid JSON with no markdown formatting."""},
                    {"role": "user", "content": prompt}
                ],
                model=self.concept_model,
                temperature=0.3
            )

            # Extract JSON from potentially wrapped response
            json_str = self._extract_json_from_response(response)
            result = json.loads(json_str)
            logger.debug(f"Extracted {len(result.get('concepts', []))} concepts via Ollama")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Ollama: {e}")
            return {
                "concepts": [],
                "skill_level": "unknown",
                "primary_topic": "uncategorized",
                "suggested_cluster": "General"
            }
        except Exception as e:
            logger.error(f"Ollama concept extraction failed: {e}")
            return {
                "concepts": [],
                "skill_level": "unknown",
                "primary_topic": "uncategorized",
                "suggested_cluster": "General"
            }

    async def generate_build_suggestions(
        self,
        knowledge_summary: str,
        max_suggestions: int
    ) -> List[Dict]:
        """Generate build suggestions using Ollama."""
        prompt = f"""Based on this user's knowledge bank, suggest {max_suggestions} practical projects that COMBINE their capabilities in new ways.

KNOWLEDGE BANK:
{knowledge_summary[:4000]}

CRITICAL INSTRUCTION:
- Look for CAPABILITIES (what their code can DO), not just technologies
- COMBINE capabilities to create NOVEL solutions:
  • capability A + capability B → New use case
  • Example: "cost estimation" + "vulnerability scoring" → "Security budget planner"
- Do NOT suggest rebuilding what they already built with different names
- Do NOT just swap nouns on the same architecture

Return ONLY a JSON array of suggestions (no markdown, no explanation):
[
  {{
    "title": "Project Name",
    "description": "What they'll build - explain which CAPABILITIES are being combined",
    "capability_combination": "capability A + capability B → novel outcome",
    "feasibility": "high|medium|low",
    "effort_estimate": "2-3 days",
    "required_skills": ["skill1", "skill2"],
    "missing_knowledge": ["gap1", "gap2"],
    "relevant_clusters": [1, 2],
    "starter_steps": ["step 1", "step 2", "step 3"],
    "file_structure": "project/\\n  src/\\n  tests/"
  }}
]

Be specific. Combine CAPABILITIES not just tech stacks. Prioritize NOVEL projects over variations of existing work."""

        try:
            response = await self._call_ollama(
                messages=[
                    {"role": "system", "content": """You are an expert project advisor who suggests realistic software projects.

PRINCIPLES:
- Look for CAPABILITIES (what problems their code solves), not just tech stacks
- COMBINE capabilities to create novel solutions
- Do NOT just recombine the same technologies with different domain nouns
- Be specific - "Security budget planner combining cost estimation + vulnerability scoring" not "Task Manager API"
- Match complexity to their skill level
- "high" feasibility = can start immediately

Return ONLY a valid JSON array with no markdown formatting."""},
                    {"role": "user", "content": prompt}
                ],
                model=self.suggestion_model,
                temperature=0.5
            )

            json_str = self._extract_json_from_response(response)
            suggestions = json.loads(json_str)
            logger.info(f"Generated {len(suggestions)} build suggestions via Ollama")
            return suggestions

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Ollama: {e}")
            return []
        except Exception as e:
            logger.error(f"Ollama build suggestion generation failed: {e}")
            return []

    async def chat_completion(
        self,
        messages: List[Dict],
        temperature: float = 0.7
    ) -> str:
        """Generic chat completion using Ollama."""
        try:
            response = await self._call_ollama(
                messages=messages,
                model=self.concept_model,
                temperature=temperature
            )
            return response
        except Exception as e:
            logger.error(f"Ollama chat completion failed: {e}")
            raise


# =============================================================================
# Provider Factory
# =============================================================================

def get_llm_provider(provider_type: str = None) -> LLMProvider:
    """
    Factory function to get the configured LLM provider.

    Args:
        provider_type: Override provider type ("openai", "ollama", "mock")
                       If not specified, uses settings.llm_provider (default: "openai")

    Returns:
        Configured LLM provider instance

    Raises:
        ValueError: If provider type is invalid or not configured
    """
    provider = provider_type or settings.llm_provider

    if provider == "openai":
        return OpenAIProvider()
    elif provider == "ollama":
        return OllamaProvider()
    elif provider == "mock":
        return MockLLMProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Supported: openai, ollama, mock")


class MockLLMProvider(LLMProvider):
    """
    Mock LLM provider for testing.

    Returns dummy data without making API calls.
    """

    async def extract_concepts(
        self,
        content: str,
        source_type: str
    ) -> Dict:
        """Return mock concept extraction."""
        return {
            "concepts": [
                {"name": "test concept", "category": "concept", "confidence": 0.9},
                {"name": "mock data", "category": "concept", "confidence": 0.8}
            ],
            "skill_level": "intermediate",
            "primary_topic": "testing",
            "suggested_cluster": "Test Cluster"
        }

    async def generate_build_suggestions(
        self,
        knowledge_summary: str,
        max_suggestions: int
    ) -> List[Dict]:
        """Return mock build suggestions."""
        return [
            {
                "title": "Test Project",
                "description": "A mock project for testing",
                "feasibility": "high",
                "effort_estimate": "1 day",
                "required_skills": ["testing"],
                "missing_knowledge": [],
                "starter_steps": ["Step 1", "Step 2"],
                "file_structure": "test/\n  src/\n  tests/"
            }
        ]

    async def chat_completion(
        self,
        messages: List[Dict],
        temperature: float = 0.7
    ) -> str:
        """Return mock chat completion."""
        return '{"similar": true, "confidence": 0.8, "reason": "mock similarity"}'
