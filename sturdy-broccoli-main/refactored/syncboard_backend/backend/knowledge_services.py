"""
Advanced Knowledge Services for SyncBoard 3.0.

This module provides LLM-powered knowledge enhancement features:
1. Knowledge Gap Analysis - Identify missing knowledge areas
2. Flashcard Generator - Create study materials
3. Weekly Digest - Summarize recent learning
4. Learning Path Optimizer - Suggest optimal reading order
5. Document Quality Scorer - Rate document usefulness
6. Conversation RAG - Multi-turn knowledge Q&A
7. Code Generator - Generate code from concepts
8. Document Comparison - Compare documents
9. ELI5 Explainer - Simplify complex topics
10. Interview Prep Generator - Create interview questions
11. Debugging Assistant - Help debug errors using KB context

Usage:
    from backend.knowledge_services import KnowledgeServices

    services = KnowledgeServices(db_session)
    gaps = await services.analyze_knowledge_gaps(user_id, kb_id)
"""

import logging
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json

from sqlalchemy.orm import Session
from sqlalchemy import text, func
from openai import AsyncOpenAI
from .config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class KnowledgeGap:
    """Represents an identified knowledge gap."""
    area: str
    severity: str  # critical, moderate, minor
    description: str
    suggested_topics: List[str]
    related_existing_docs: List[int]
    learning_priority: int  # 1-10


@dataclass
class GapAnalysisResult:
    """Result of knowledge gap analysis."""
    total_documents: int
    total_concepts: int
    coverage_areas: List[str]
    gaps: List[KnowledgeGap]
    shallow_areas: List[Dict]
    recommended_learning_path: List[str]
    inferred_goal: str
    strongest_areas: List[str]


@dataclass
class Flashcard:
    """A single flashcard for study."""
    front: str
    back: str
    difficulty: str  # easy, medium, hard
    concept: str
    source_doc_id: int
    source_section: str


@dataclass
class WeeklyDigest:
    """Weekly learning digest."""
    period_start: datetime
    period_end: datetime
    documents_added: int
    executive_summary: str
    new_concepts: List[str]
    skills_improved: List[str]
    focus_suggestions: List[str]
    connections_to_existing: List[str]
    quick_wins: List[str]


@dataclass
class LearningPath:
    """Optimized learning path."""
    goal: str
    total_documents: int
    estimated_hours: float
    ordered_docs: List[Dict]  # {doc_id, title, time_estimate, checkpoint}
    skip_list: List[int]
    external_resources: List[str]


@dataclass
class DocumentQuality:
    """Document quality assessment."""
    doc_id: int
    information_density: int  # 1-10
    actionability: int  # 1-10
    currency: int  # 1-10
    uniqueness: int  # 1-10
    overall_score: float
    key_excerpts: List[str]
    sections_to_skip: List[str]
    missing_context: List[str]


@dataclass
class DocumentComparison:
    """Comparison between two documents."""
    doc_a_id: int
    doc_b_id: int
    overlapping_concepts: List[str]
    contradictions: List[Dict]
    complementary_info: List[Dict]
    more_authoritative: int  # doc_id
    recommended_order: List[int]
    synthesis: str


@dataclass
class InterviewPrep:
    """Interview preparation materials."""
    topics: List[str]
    behavioral_questions: List[Dict]
    technical_questions: List[Dict]
    system_design_questions: List[Dict]
    gotcha_questions: List[Dict]
    study_recommendations: List[str]


@dataclass
class DebugAssistantResult:
    """Result from debugging assistant."""
    error_message: str
    likely_cause: str
    step_by_step_fix: List[str]
    explanation: str
    prevention_tips: List[str]
    related_docs: List[Dict]  # {doc_id, title, relevance}
    code_suggestion: Optional[str] = None
    confidence: float = 0.0


# =============================================================================
# Main Knowledge Services Class
# =============================================================================

class KnowledgeServices:
    """
    Comprehensive knowledge enhancement services powered by LLMs.
    """

    def __init__(self, db: Session):
        self.db = db
        self._client = None

    def _get_client(self) -> AsyncOpenAI:
        """Lazy-load OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    async def _call_llm(
        self,
        system_message: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        model: str = "gpt-5-mini"
    ) -> str:
        """Generic LLM call helper."""
        client = self._get_client()
        try:
            # GPT-5 models use different parameters
            params = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ]
            }

            if model.startswith("gpt-5"):
                # GPT-5 models use max_completion_tokens and ignore temperature
                params["max_completion_tokens"] = max_tokens
            else:
                # GPT-4 and earlier use max_tokens and temperature
                params["max_tokens"] = max_tokens
                params["temperature"] = temperature

            response = await client.chat.completions.create(**params)
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def _get_kb_summary(self, kb_id: str) -> Dict:
        """Get knowledge base summary for prompts."""
        # Get document count and concepts
        doc_query = text("""
            SELECT COUNT(*) as doc_count,
                   COUNT(DISTINCT c.name) as concept_count
            FROM documents d
            LEFT JOIN concepts c ON c.document_id = d.id
            WHERE d.knowledge_base_id = :kb_id
        """)
        result = self.db.execute(doc_query, {"kb_id": kb_id}).fetchone()

        # Get top concepts
        concept_query = text("""
            SELECT c.name, c.category, COUNT(*) as freq
            FROM concepts c
            JOIN documents d ON c.document_id = d.id
            WHERE d.knowledge_base_id = :kb_id
            GROUP BY c.name, c.category
            ORDER BY freq DESC
            LIMIT 50
        """)
        concepts = self.db.execute(concept_query, {"kb_id": kb_id}).fetchall()

        # Get clusters
        cluster_query = text("""
            SELECT name, primary_concepts
            FROM clusters
            WHERE knowledge_base_id = :kb_id
        """)
        clusters = self.db.execute(cluster_query, {"kb_id": kb_id}).fetchall()

        # Get source types distribution
        source_query = text("""
            SELECT source_type, COUNT(*) as count
            FROM documents
            WHERE knowledge_base_id = :kb_id
            GROUP BY source_type
        """)
        sources = self.db.execute(source_query, {"kb_id": kb_id}).fetchall()

        return {
            "document_count": result.doc_count if result else 0,
            "concept_count": result.concept_count if result else 0,
            "top_concepts": [{"name": c.name, "category": c.category, "freq": c.freq} for c in concepts],
            "clusters": [{"name": cl.name, "concepts": cl.primary_concepts} for cl in clusters],
            "source_distribution": {s.source_type: s.count for s in sources}
        }

    # =========================================================================
    # 1. Knowledge Gap Analysis
    # =========================================================================

    async def analyze_knowledge_gaps(
        self,
        user_id: str,
        kb_id: str
    ) -> GapAnalysisResult:
        """
        Analyze the knowledge base to identify gaps and missing areas.

        Returns critical gaps, shallow coverage areas, and learning recommendations.
        """
        summary = self._get_kb_summary(kb_id)

        if summary["document_count"] < 3:
            return GapAnalysisResult(
                total_documents=summary["document_count"],
                total_concepts=summary["concept_count"],
                coverage_areas=[],
                gaps=[],
                shallow_areas=[],
                recommended_learning_path=["Add more documents to enable gap analysis"],
                inferred_goal="Unknown - insufficient data",
                strongest_areas=[]
            )

        system_message = """You are an expert learning analyst and curriculum designer.
Analyze knowledge bases to identify gaps, shallow areas, and learning opportunities.
Return ONLY valid JSON with no markdown formatting."""

        user_message = f"""Analyze this knowledge base for gaps and opportunities:

KNOWLEDGE BASE SUMMARY:
- Total Documents: {summary['document_count']}
- Total Concepts: {summary['concept_count']}
- Source Types: {json.dumps(summary['source_distribution'])}

TOP CONCEPTS (by frequency):
{json.dumps(summary['top_concepts'][:30], indent=2)}

CLUSTERS/TOPICS:
{json.dumps(summary['clusters'], indent=2)}

ANALYSIS REQUIRED:
1. Infer the user's likely learning goal based on content
2. Identify their strongest areas (well-covered topics)
3. Find CRITICAL knowledge gaps (obviously missing for their goal)
4. Find SHALLOW areas (topics with only surface coverage)
5. Suggest a prioritized learning path to fill gaps

Return JSON:
{{
    "inferred_goal": "What the user is likely trying to learn/achieve",
    "strongest_areas": ["area1", "area2", ...],
    "coverage_areas": ["All topics currently covered"],
    "gaps": [
        {{
            "area": "Missing topic name",
            "severity": "critical|moderate|minor",
            "description": "Why this is important",
            "suggested_topics": ["Specific things to learn"],
            "learning_priority": 1-10
        }}
    ],
    "shallow_areas": [
        {{
            "area": "Topic name",
            "current_depth": "What's covered now",
            "missing_depth": "What's missing",
            "suggested_resources": ["Types of content to add"]
        }}
    ],
    "recommended_learning_path": ["Step 1", "Step 2", ...]
}}"""

        response = await self._call_llm(
            system_message, user_message,
            temperature=0.3, max_tokens=4000
        )

        try:
            # Clean response if needed
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            data = json.loads(response)

            gaps = [
                KnowledgeGap(
                    area=g["area"],
                    severity=g.get("severity", "moderate"),
                    description=g.get("description", ""),
                    suggested_topics=g.get("suggested_topics", []),
                    related_existing_docs=[],
                    learning_priority=g.get("learning_priority", 5)
                )
                for g in data.get("gaps", [])
            ]

            return GapAnalysisResult(
                total_documents=summary["document_count"],
                total_concepts=summary["concept_count"],
                coverage_areas=data.get("coverage_areas", []),
                gaps=gaps,
                shallow_areas=data.get("shallow_areas", []),
                recommended_learning_path=data.get("recommended_learning_path", []),
                inferred_goal=data.get("inferred_goal", "Unknown"),
                strongest_areas=data.get("strongest_areas", [])
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse gap analysis: {e}")
            return GapAnalysisResult(
                total_documents=summary["document_count"],
                total_concepts=summary["concept_count"],
                coverage_areas=[],
                gaps=[],
                shallow_areas=[],
                recommended_learning_path=["Error analyzing knowledge base"],
                inferred_goal="Analysis failed",
                strongest_areas=[]
            )

    # =========================================================================
    # 2. Flashcard Generator
    # =========================================================================

    async def generate_flashcards(
        self,
        doc_id: int,
        num_cards: int = 10,
        difficulty_mix: str = "balanced"  # easy, balanced, hard
    ) -> List[Flashcard]:
        """
        Generate study flashcards from a document.

        Args:
            doc_id: Document to generate cards from
            num_cards: Number of cards to generate
            difficulty_mix: Distribution of difficulty levels
        """
        # Get document content
        doc_query = text("""
            SELECT d.doc_id, d.filename, d.source_type, vd.content
            FROM documents d
            JOIN vector_documents vd ON vd.doc_id = d.doc_id
            WHERE d.doc_id = :doc_id
        """)
        doc = self.db.execute(doc_query, {"doc_id": doc_id}).fetchone()

        if not doc:
            return []

        # Truncate content if too long
        content = doc.content[:15000] if doc.content else ""

        system_message = """You are an expert educator creating flashcards for spaced repetition learning.
Create cards that test understanding, not just memorization.
Return ONLY valid JSON array with no markdown formatting."""

        difficulty_instruction = {
            "easy": "Focus on fundamental concepts and definitions.",
            "balanced": "Mix of basic concepts, applications, and deeper understanding.",
            "hard": "Focus on edge cases, comparisons, and application scenarios."
        }.get(difficulty_mix, "balanced")

        user_message = f"""Create {num_cards} flashcards from this document.

DOCUMENT: {doc.filename or 'Untitled'} (Type: {doc.source_type})

CONTENT:
{content}

INSTRUCTIONS:
- {difficulty_instruction}
- Focus on testable facts, not opinions
- Include practical application questions
- Cover common gotchas and mistakes
- Vary question types (what, why, how, compare)

Return JSON array:
[
    {{
        "front": "Question testing a key concept",
        "back": "Concise, accurate answer",
        "difficulty": "easy|medium|hard",
        "concept": "Main concept being tested",
        "source_section": "Which part of doc this relates to"
    }}
]"""

        response = await self._call_llm(
            system_message, user_message,
            temperature=0.7, max_tokens=3000
        )

        try:
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            cards_data = json.loads(response)

            return [
                Flashcard(
                    front=c["front"],
                    back=c["back"],
                    difficulty=c.get("difficulty", "medium"),
                    concept=c.get("concept", ""),
                    source_doc_id=doc_id,
                    source_section=c.get("source_section", "")
                )
                for c in cards_data
            ]

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse flashcards: {e}")
            return []

    # =========================================================================
    # 3. Weekly Digest Generator
    # =========================================================================

    async def generate_weekly_digest(
        self,
        user_id: str,
        kb_id: str,
        days: int = 7
    ) -> WeeklyDigest:
        """
        Generate a digest of recent learning activity.

        Summarizes new documents, concepts learned, and suggests focus areas.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Get recent documents
        doc_query = text("""
            SELECT d.doc_id, d.filename, d.source_type, d.skill_level,
                   vd.content, d.ingested_at
            FROM documents d
            LEFT JOIN vector_documents vd ON vd.doc_id = d.doc_id
            WHERE d.knowledge_base_id = :kb_id
              AND d.ingested_at >= :cutoff
            ORDER BY d.ingested_at DESC
        """)
        recent_docs = self.db.execute(doc_query, {"kb_id": kb_id, "cutoff": cutoff}).fetchall()

        if not recent_docs:
            return WeeklyDigest(
                period_start=cutoff,
                period_end=datetime.utcnow(),
                documents_added=0,
                executive_summary="No new documents added this period.",
                new_concepts=[],
                skills_improved=[],
                focus_suggestions=["Add some new content to your knowledge base!"],
                connections_to_existing=[],
                quick_wins=[]
            )

        # Get new concepts from these docs
        doc_ids = [d.doc_id for d in recent_docs]
        concept_query = text("""
            SELECT DISTINCT c.name, c.category
            FROM concepts c
            JOIN documents d ON c.document_id = d.id
            WHERE d.doc_id = ANY(:doc_ids)
        """)
        new_concepts = self.db.execute(concept_query, {"doc_ids": doc_ids}).fetchall()

        # Build summary for LLM
        docs_summary = "\n".join([
            f"- {d.filename or 'Untitled'} ({d.source_type}, {d.skill_level or 'unknown'} level)"
            for d in recent_docs[:20]
        ])

        concepts_list = [c.name for c in new_concepts[:30]]

        system_message = """You are a personal learning coach creating motivating weekly digests.
Be encouraging but honest. Focus on actionable insights.
Return ONLY valid JSON with no markdown formatting."""

        user_message = f"""Create a weekly learning digest for this user.

PERIOD: Last {days} days
DOCUMENTS ADDED: {len(recent_docs)}

NEW DOCUMENTS:
{docs_summary}

NEW CONCEPTS ENCOUNTERED:
{', '.join(concepts_list)}

Create a digest with:
1. Executive summary (2-3 sentences on what was learned)
2. Key skills that improved based on content types
3. Suggested focus for next week
4. Connections between new and existing knowledge
5. Quick wins (things they can apply immediately)

Return JSON:
{{
    "executive_summary": "Motivating summary of the week's learning",
    "skills_improved": ["skill1", "skill2"],
    "focus_suggestions": ["What to focus on next"],
    "connections_to_existing": ["How new knowledge connects to what they knew"],
    "quick_wins": ["Immediately actionable items"]
}}"""

        response = await self._call_llm(
            system_message, user_message,
            temperature=0.7, max_tokens=2000
        )

        try:
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            data = json.loads(response)

            return WeeklyDigest(
                period_start=cutoff,
                period_end=datetime.utcnow(),
                documents_added=len(recent_docs),
                executive_summary=data.get("executive_summary", ""),
                new_concepts=concepts_list,
                skills_improved=data.get("skills_improved", []),
                focus_suggestions=data.get("focus_suggestions", []),
                connections_to_existing=data.get("connections_to_existing", []),
                quick_wins=data.get("quick_wins", [])
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse digest: {e}")
            return WeeklyDigest(
                period_start=cutoff,
                period_end=datetime.utcnow(),
                documents_added=len(recent_docs),
                executive_summary="Error generating digest",
                new_concepts=concepts_list,
                skills_improved=[],
                focus_suggestions=[],
                connections_to_existing=[],
                quick_wins=[]
            )

    # =========================================================================
    # 4. Learning Path Optimizer
    # =========================================================================

    async def optimize_learning_path(
        self,
        user_id: str,
        kb_id: str,
        goal: str
    ) -> LearningPath:
        """
        Create an optimized learning path for a specific goal.

        Analyzes documents and suggests optimal reading order with time estimates.
        """
        # Get all documents with summaries
        doc_query = text("""
            SELECT d.doc_id, d.filename, d.source_type, d.skill_level,
                   d.content_length, ds.short_summary
            FROM documents d
            LEFT JOIN document_summaries ds ON ds.document_id = d.id AND ds.summary_type = 'document'
            WHERE d.knowledge_base_id = :kb_id
            ORDER BY d.skill_level, d.ingested_at
        """)
        docs = self.db.execute(doc_query, {"kb_id": kb_id}).fetchall()

        if not docs:
            return LearningPath(
                goal=goal,
                total_documents=0,
                estimated_hours=0,
                ordered_docs=[],
                skip_list=[],
                external_resources=["Add documents to your knowledge base first"]
            )

        docs_info = "\n".join([
            f"- ID:{d.doc_id} | {d.filename or 'Untitled'} | {d.skill_level or '?'} | {d.content_length or 0} chars | {d.short_summary or 'No summary'})"[:200]
            for d in docs[:50]
        ])

        system_message = """You are an expert curriculum designer optimizing learning paths.
Consider prerequisites, difficulty progression, and learning efficiency.
Return ONLY valid JSON with no markdown formatting."""

        user_message = f"""Create an optimal learning path for this goal.

GOAL: {goal}

AVAILABLE DOCUMENTS ({len(docs)} total):
{docs_info}

Create a learning path that:
1. Orders documents by prerequisites (what to read first)
2. Estimates time per document (based on length/complexity)
3. Includes checkpoint activities after sections
4. Identifies documents that can be skipped
5. Suggests external resources to fill gaps

Return JSON:
{{
    "estimated_total_hours": 10.5,
    "ordered_docs": [
        {{
            "doc_id": 123,
            "order": 1,
            "title": "Document name",
            "time_estimate_minutes": 30,
            "why_this_order": "Reason for this position",
            "checkpoint": "Mini-project or exercise after this"
        }}
    ],
    "skip_list": [
        {{
            "doc_id": 456,
            "reason": "Why this can be skipped"
        }}
    ],
    "external_resources": [
        "Specific resource to supplement gaps"
    ]
}}"""

        response = await self._call_llm(
            system_message, user_message,
            temperature=0.5, max_tokens=4000
        )

        try:
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            data = json.loads(response)

            return LearningPath(
                goal=goal,
                total_documents=len(data.get("ordered_docs", [])),
                estimated_hours=data.get("estimated_total_hours", 0),
                ordered_docs=data.get("ordered_docs", []),
                skip_list=[s["doc_id"] for s in data.get("skip_list", [])],
                external_resources=data.get("external_resources", [])
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse learning path: {e}")
            return LearningPath(
                goal=goal,
                total_documents=len(docs),
                estimated_hours=0,
                ordered_docs=[],
                skip_list=[],
                external_resources=["Error generating learning path"]
            )

    # =========================================================================
    # 5. Document Quality Scorer
    # =========================================================================

    async def score_document_quality(
        self,
        doc_id: int
    ) -> DocumentQuality:
        """
        Rate a document's quality and usefulness for learning.

        Returns scores for density, actionability, currency, and uniqueness.
        """
        # Get document content
        doc_query = text("""
            SELECT d.doc_id, d.filename, d.source_type, d.source_url,
                   d.ingested_at, vd.content
            FROM documents d
            JOIN vector_documents vd ON vd.doc_id = d.doc_id
            WHERE d.doc_id = :doc_id
        """)
        doc = self.db.execute(doc_query, {"doc_id": doc_id}).fetchone()

        if not doc:
            return DocumentQuality(
                doc_id=doc_id,
                information_density=0,
                actionability=0,
                currency=0,
                uniqueness=0,
                overall_score=0,
                key_excerpts=[],
                sections_to_skip=[],
                missing_context=["Document not found"]
            )

        content = doc.content[:12000] if doc.content else ""

        system_message = """You are a content quality analyst evaluating documents for a knowledge base.
Be objective and specific in your assessments.
Return ONLY valid JSON with no markdown formatting."""

        user_message = f"""Rate this document's quality for learning purposes.

DOCUMENT: {doc.filename or 'Untitled'}
SOURCE: {doc.source_type} | {doc.source_url or 'No URL'}
ADDED: {doc.ingested_at}

CONTENT:
{content}

Rate each criterion 1-10:
1. Information Density: How much valuable info per paragraph?
2. Actionability: Can reader DO something with this knowledge?
3. Currency: Is the information still relevant/up-to-date?
4. Uniqueness: Does this add new value vs typical content?

Also identify:
- Key excerpts worth highlighting (most valuable parts)
- Sections to skip (filler, outdated, irrelevant)
- Missing context that would help understanding

Return JSON:
{{
    "information_density": 7,
    "actionability": 8,
    "currency": 6,
    "uniqueness": 5,
    "key_excerpts": ["Quote or paraphrase of valuable sections"],
    "sections_to_skip": ["Description of sections to skip"],
    "missing_context": ["What's missing that would help"]
}}"""

        response = await self._call_llm(
            system_message, user_message,
            temperature=0.3, max_tokens=2000
        )

        try:
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            data = json.loads(response)

            density = data.get("information_density", 5)
            action = data.get("actionability", 5)
            currency = data.get("currency", 5)
            unique = data.get("uniqueness", 5)
            overall = (density + action + currency + unique) / 4

            return DocumentQuality(
                doc_id=doc_id,
                information_density=density,
                actionability=action,
                currency=currency,
                uniqueness=unique,
                overall_score=round(overall, 1),
                key_excerpts=data.get("key_excerpts", []),
                sections_to_skip=data.get("sections_to_skip", []),
                missing_context=data.get("missing_context", [])
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse quality score: {e}")
            return DocumentQuality(
                doc_id=doc_id,
                information_density=5,
                actionability=5,
                currency=5,
                uniqueness=5,
                overall_score=5.0,
                key_excerpts=[],
                sections_to_skip=[],
                missing_context=["Error analyzing document"]
            )

    # =========================================================================
    # 6. Conversation-Style RAG
    # =========================================================================

    async def conversation_rag(
        self,
        query: str,
        kb_id: str,
        conversation_history: List[Dict] = None,
        max_history: int = 5
    ) -> Dict:
        """
        Multi-turn conversation with knowledge base context.

        Maintains conversation history for follow-up questions.
        """
        history = conversation_history or []

        # Get relevant documents
        summary = self._get_kb_summary(kb_id)

        # Build conversation context
        history_text = ""
        if history:
            recent_history = history[-max_history:]
            cleaned_history = []
            for h in recent_history:
                user_turn = h.get("user") if isinstance(h, dict) else None
                assistant_turn = h.get("assistant") if isinstance(h, dict) else None
                if user_turn or assistant_turn:
                    cleaned_history.append(
                        f"User: {user_turn or ''}\nAssistant: {assistant_turn or ''}".strip()
                    )
            history_text = "\n".join(cleaned_history)

        system_message = """You are a knowledgeable tutor helping users understand their knowledge base.

IMPORTANT RULES:
1. Reference previous conversation when relevant
2. Build on established context
3. Ask clarifying questions if the query is ambiguous
4. Suggest related topics to explore
5. Cite sources when possible
6. Be conversational but informative"""

        user_message = f"""KNOWLEDGE BASE CONTEXT:
- {summary['document_count']} documents
- Top topics: {', '.join([c['name'] for c in summary['top_concepts'][:10]])}

PREVIOUS CONVERSATION:
{history_text if history_text else "(No previous conversation)"}

CURRENT QUESTION: {query}

Provide a helpful, contextual response."""

        response = await self._call_llm(
            system_message, user_message,
            temperature=0.7, max_tokens=2000
        )

        # Extract any follow-up suggestions
        follow_ups = []
        if "you might also" in response.lower() or "related" in response.lower():
            # Simple extraction - could be enhanced
            follow_ups = ["Explore related topics", "Ask for more details"]

        return {
            "response": response,
            "query": query,
            "follow_ups": follow_ups,  # Frontend expects 'follow_ups' not 'suggested_follow_ups'
            "context_used": {
                "documents": summary['document_count'],
                "history_turns": len(history)
            }
        }

    # =========================================================================
    # 7. Code Generator from Concepts
    # =========================================================================

    async def generate_code_from_concepts(
        self,
        kb_id: str,
        project_type: str = "starter",
        language: str = "python"
    ) -> Dict:
        """
        Generate starter code based on concepts in the knowledge base.

        Creates runnable code with comments linking to KB concepts.
        """
        summary = self._get_kb_summary(kb_id)

        concepts = [c['name'] for c in summary['top_concepts'][:20]]
        categories = list(set(c['category'] for c in summary['top_concepts'][:20]))

        system_message = f"""You are an expert {language} developer creating educational starter projects.
Generate complete, runnable code with extensive comments explaining how it connects to concepts.
Return ONLY valid JSON with no markdown formatting."""

        user_message = f"""Generate a {project_type} project based on these concepts from the user's knowledge base.

CONCEPTS: {', '.join(concepts)}
CATEGORIES: {', '.join(categories)}
LANGUAGE: {language}

Create a project that:
1. Demonstrates practical use of their known concepts
2. Includes extensive comments linking to concepts
3. Has TODO markers for customization
4. Includes basic tests
5. Is immediately runnable

Return JSON:
{{
    "project_name": "descriptive-name",
    "description": "What this project does",
    "concepts_demonstrated": ["concept1", "concept2"],
    "files": [
        {{
            "filename": "main.py",
            "content": "# Full file content with comments",
            "purpose": "What this file does"
        }}
    ],
    "setup_instructions": ["Step 1", "Step 2"],
    "run_command": "python main.py",
    "next_steps": ["How to extend this"]
}}"""

        response = await self._call_llm(
            system_message, user_message,
            temperature=0.7, max_tokens=8000,
            model="gpt-5-mini"
        )

        try:
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            return json.loads(response)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse generated code: {e}")
            return {
                "error": "Failed to generate code",
                "concepts_available": concepts
            }

    # =========================================================================
    # 8. Document Comparison
    # =========================================================================

    async def compare_documents(
        self,
        doc_a_id: int,
        doc_b_id: int
    ) -> DocumentComparison:
        """
        Compare two documents for overlaps, contradictions, and complementary info.
        """
        # Get both documents
        doc_query = text("""
            SELECT d.doc_id, d.filename, d.source_type, vd.content
            FROM documents d
            JOIN vector_documents vd ON vd.doc_id = d.doc_id
            WHERE d.doc_id = ANY(:doc_ids)
        """)
        docs = self.db.execute(doc_query, {"doc_ids": [doc_a_id, doc_b_id]}).fetchall()

        if len(docs) < 2:
            return DocumentComparison(
                doc_a_id=doc_a_id,
                doc_b_id=doc_b_id,
                overlapping_concepts=[],
                contradictions=[],
                complementary_info=[],
                more_authoritative=0,
                recommended_order=[],
                synthesis="Could not find both documents"
            )

        doc_a = next((d for d in docs if d.doc_id == doc_a_id), None)
        doc_b = next((d for d in docs if d.doc_id == doc_b_id), None)

        content_a = doc_a.content[:8000] if doc_a else ""
        content_b = doc_b.content[:8000] if doc_b else ""

        system_message = """You are an expert analyst comparing documents for knowledge synthesis.
Identify agreements, contradictions, and complementary information.
Return ONLY valid JSON with no markdown formatting."""

        user_message = f"""Compare these two documents from a knowledge base.

DOCUMENT A: {doc_a.filename if doc_a else 'Unknown'}
{content_a}

---

DOCUMENT B: {doc_b.filename if doc_b else 'Unknown'}
{content_b}

---

Analyze:
1. Overlapping concepts (where they agree)
2. Contradictions or different approaches
3. Complementary information (A has X, B has Y)
4. Which is more authoritative/current
5. Recommended reading order
6. Synthesis (how to use both together)

Return JSON:
{{
    "overlapping_concepts": ["concept1", "concept2"],
    "contradictions": [
        {{"topic": "X", "doc_a_says": "...", "doc_b_says": "...", "resolution": "..."}}
    ],
    "complementary_info": [
        {{"doc_a_has": "...", "doc_b_has": "...", "combined_value": "..."}}
    ],
    "more_authoritative": "A or B",
    "authority_reason": "Why",
    "recommended_order": ["A", "B"],
    "order_reason": "Why this order",
    "synthesis": "How to best use both documents together"
}}"""

        response = await self._call_llm(
            system_message, user_message,
            temperature=0.3, max_tokens=3000
        )

        try:
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            data = json.loads(response)

            auth = data.get("more_authoritative", "A")
            auth_id = doc_a_id if auth == "A" else doc_b_id

            order = data.get("recommended_order", ["A", "B"])
            order_ids = [doc_a_id if x == "A" else doc_b_id for x in order]

            return DocumentComparison(
                doc_a_id=doc_a_id,
                doc_b_id=doc_b_id,
                overlapping_concepts=data.get("overlapping_concepts", []),
                contradictions=data.get("contradictions", []),
                complementary_info=data.get("complementary_info", []),
                more_authoritative=auth_id,
                recommended_order=order_ids,
                synthesis=data.get("synthesis", "")
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse comparison: {e}")
            return DocumentComparison(
                doc_a_id=doc_a_id,
                doc_b_id=doc_b_id,
                overlapping_concepts=[],
                contradictions=[],
                complementary_info=[],
                more_authoritative=0,
                recommended_order=[],
                synthesis="Error comparing documents"
            )

    # =========================================================================
    # 9. ELI5 Explainer
    # =========================================================================

    async def explain_eli5(
        self,
        topic: str,
        kb_id: str
    ) -> Dict:
        """
        Explain a topic from the knowledge base in simple terms.

        Uses ELI5 (Explain Like I'm 5) style for accessibility.
        """
        summary = self._get_kb_summary(kb_id)

        # Check if topic exists in KB
        relevant_concepts = [c for c in summary['top_concepts'] if topic.lower() in c['name'].lower()]

        system_message = """You are a patient teacher explaining complex topics simply.
Use analogies, avoid jargon, and make concepts accessible to beginners.
Return ONLY valid JSON with no markdown formatting."""

        user_message = f"""Explain "{topic}" in simple terms for someone new to the field.

CONTEXT FROM KNOWLEDGE BASE:
Related concepts found: {[c['name'] for c in relevant_concepts[:5]]}
Categories covered: {list(set(c['category'] for c in summary['top_concepts'][:20]))}

Create an ELI5 explanation with:
1. Core concept in 2-3 simple sentences
2. Real-world analogy anyone can understand
3. Why it matters (practical benefit)
4. One simple example
5. What to learn next

Avoid: jargon, assumed knowledge, theoretical depth

Return JSON:
{{
    "topic": "{topic}",
    "simple_explanation": "2-3 sentence explanation",
    "analogy": "Real-world comparison",
    "why_it_matters": "Practical benefit",
    "simple_example": "Easy to understand example",
    "learn_next": ["Next topic 1", "Next topic 2"],
    "common_misconceptions": ["Misconception to avoid"]
}}"""

        response = await self._call_llm(
            system_message, user_message,
            temperature=0.7, max_tokens=2000
        )

        try:
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            return json.loads(response)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ELI5: {e}")
            return {
                "topic": topic,
                "simple_explanation": "Error generating explanation",
                "analogy": "",
                "why_it_matters": "",
                "simple_example": "",
                "learn_next": [],
                "common_misconceptions": []
            }

    # =========================================================================
    # 10. Interview Prep Generator
    # =========================================================================

    async def generate_interview_prep(
        self,
        kb_id: str,
        role: str = None,
        level: str = "mid"  # junior, mid, senior
    ) -> InterviewPrep:
        """
        Generate interview preparation materials based on knowledge base.

        Creates behavioral, technical, and system design questions.
        """
        summary = self._get_kb_summary(kb_id)

        topics = [c['name'] for c in summary['top_concepts'][:20]]
        categories = list(set(c['category'] for c in summary['top_concepts'][:20]))

        inferred_role = role or f"Software Engineer with {', '.join(categories[:3])} focus"

        system_message = """You are an expert technical interviewer creating comprehensive prep materials.
Generate realistic questions that would be asked in actual interviews.
Return ONLY valid JSON with no markdown formatting."""

        user_message = f"""Generate interview prep materials for this candidate.

INFERRED ROLE: {inferred_role}
EXPERIENCE LEVEL: {level}
TOPICS IN KNOWLEDGE BASE: {', '.join(topics)}
SKILL CATEGORIES: {', '.join(categories)}

Generate:
1. 5 behavioral questions (expect STAR format answers)
2. 5 technical questions with ideal answers
3. 3 system design questions (appropriate for {level} level)
4. 3 "gotcha" questions interviewers commonly ask
5. Topics they should study more before interviewing

Return JSON:
{{
    "role": "{inferred_role}",
    "level": "{level}",
    "behavioral_questions": [
        {{"question": "...", "what_they_test": "...", "good_answer_elements": ["..."]}}
    ],
    "technical_questions": [
        {{"question": "...", "ideal_answer": "...", "follow_ups": ["..."]}}
    ],
    "system_design_questions": [
        {{"question": "...", "key_points": ["..."], "common_mistakes": ["..."]}}
    ],
    "gotcha_questions": [
        {{"question": "...", "why_tricky": "...", "how_to_handle": "..."}}
    ],
    "study_recommendations": ["Topic 1", "Topic 2"]
}}"""

        response = await self._call_llm(
            system_message, user_message,
            temperature=0.7, max_tokens=5000
        )

        try:
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            data = json.loads(response)

            return InterviewPrep(
                topics=topics,
                behavioral_questions=data.get("behavioral_questions", []),
                technical_questions=data.get("technical_questions", []),
                system_design_questions=data.get("system_design_questions", []),
                gotcha_questions=data.get("gotcha_questions", []),
                study_recommendations=data.get("study_recommendations", [])
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse interview prep: {e}")
            return InterviewPrep(
                topics=topics,
                behavioral_questions=[],
                technical_questions=[],
                system_design_questions=[],
                gotcha_questions=[],
                study_recommendations=["Error generating interview prep"]
            )

    # =========================================================================
    # 11. Debugging Assistant
    # =========================================================================

    async def debug_error(
        self,
        error_message: str,
        kb_id: str,
        code_context: Optional[str] = None,
        stack_trace: Optional[str] = None,
        language: str = "python"
    ) -> DebugAssistantResult:
        """
        Help debug an error using knowledge base context.

        Uses the user's KB to provide personalized debugging help
        based on their specific frameworks, libraries, and code patterns.

        Args:
            error_message: The error message or exception
            kb_id: Knowledge base ID for context
            code_context: Optional code snippet where error occurred
            stack_trace: Optional full stack trace
            language: Programming language (default: python)

        Returns:
            DebugAssistantResult with cause, fix steps, and related docs
        """
        summary = self._get_kb_summary(kb_id)

        # Search for relevant documents based on error
        relevant_docs = await self._search_relevant_docs_for_error(
            error_message, kb_id
        )

        # Build context from KB
        kb_context = f"""
USER'S KNOWLEDGE BASE:
- Technologies: {', '.join([c['name'] for c in summary['top_concepts'][:15]])}
- Frameworks/Tools: {', '.join([c['name'] for c in summary['top_concepts'] if c['category'] in ['framework', 'tool', 'library']][:10])}
"""

        relevant_docs_text = ""
        if relevant_docs:
            relevant_docs_text = "\nRELEVANT DOCUMENTS FROM KB:\n"
            for doc in relevant_docs[:5]:
                relevant_docs_text += f"- {doc.get('filename', 'Untitled')} (ID: {doc.get('doc_id')}): {doc.get('snippet', '')[:200]}\n"

        system_message = f"""You are an expert {language} debugger and mentor.
Help the user fix their error using context from their knowledge base.
Be specific and actionable. Reference their known technologies.
Return ONLY valid JSON with no markdown formatting."""

        user_message = f"""Debug this error for me:

ERROR MESSAGE:
{error_message}

{f"STACK TRACE:{chr(10)}{stack_trace}" if stack_trace else ""}

{f"CODE CONTEXT:{chr(10)}{code_context}" if code_context else ""}

{kb_context}
{relevant_docs_text}

Provide debugging help that:
1. Identifies the likely cause (connecting to their known concepts)
2. Gives step-by-step fix instructions
3. Explains WHY this happened (educational)
4. Suggests how to prevent it in future
5. References relevant docs from their KB if applicable
6. Provides a code fix suggestion if possible

Return JSON:
{{
    "likely_cause": "Clear explanation of what caused this error",
    "step_by_step_fix": [
        "Step 1: Do this...",
        "Step 2: Then do this..."
    ],
    "explanation": "Why this happened (connecting to concepts they know)",
    "prevention_tips": [
        "Tip 1: To prevent this in future...",
        "Tip 2: Also consider..."
    ],
    "related_doc_ids": [123, 456],
    "code_suggestion": "Fixed code snippet if applicable (or null)",
    "confidence": 0.85
}}"""

        response = await self._call_llm(
            system_message, user_message,
            temperature=0.3, max_tokens=3000
        )

        try:
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            data = json.loads(response)

            # Match related_doc_ids to actual docs
            related_doc_ids = data.get("related_doc_ids", [])
            related_docs_result = [
                {"doc_id": doc.get("doc_id"), "title": doc.get("filename"), "relevance": "high"}
                for doc in relevant_docs
                if doc.get("doc_id") in related_doc_ids
            ][:5]

            return DebugAssistantResult(
                error_message=error_message,
                likely_cause=data.get("likely_cause", "Unknown"),
                step_by_step_fix=data.get("step_by_step_fix", []),
                explanation=data.get("explanation", ""),
                prevention_tips=data.get("prevention_tips", []),
                related_docs=related_docs_result,
                code_suggestion=data.get("code_suggestion"),
                confidence=data.get("confidence", 0.5)
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse debug response: {e}")
            return DebugAssistantResult(
                error_message=error_message,
                likely_cause="Error analyzing the problem",
                step_by_step_fix=["Please try rephrasing the error or providing more context"],
                explanation="The debugging assistant encountered an error",
                prevention_tips=[],
                related_docs=[],
                confidence=0.0
            )

    async def _search_relevant_docs_for_error(
        self,
        error_message: str,
        kb_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """Search for documents relevant to an error."""
        # Extract key terms from error message
        # Simple approach: look for known error patterns and technology names
        search_terms = error_message.lower()

        # Search in document content
        query = text("""
            SELECT d.doc_id, d.filename, d.source_type,
                   SUBSTRING(vd.content, 1, 500) as snippet
            FROM documents d
            JOIN vector_documents vd ON vd.doc_id = d.doc_id
            WHERE d.knowledge_base_id = :kb_id
              AND (
                  LOWER(vd.content) LIKE :search1
                  OR LOWER(vd.content) LIKE :search2
                  OR LOWER(d.filename) LIKE :search1
              )
            LIMIT :limit
        """)

        try:
            # Extract first significant word from error for search
            words = [w for w in error_message.split() if len(w) > 3][:3]
            search_pattern1 = f"%{words[0].lower()}%" if words else "%error%"
            search_pattern2 = f"%{words[1].lower()}%" if len(words) > 1 else search_pattern1

            result = self.db.execute(query, {
                "kb_id": kb_id,
                "search1": search_pattern1,
                "search2": search_pattern2,
                "limit": limit
            })

            return [
                {
                    "doc_id": row.doc_id,
                    "filename": row.filename,
                    "source_type": row.source_type,
                    "snippet": row.snippet
                }
                for row in result
            ]
        except Exception as e:
            logger.warning(f"Error searching for relevant docs: {e}")
            return []


# =============================================================================
# Convenience Functions
# =============================================================================

def get_knowledge_services(db: Session) -> KnowledgeServices:
    """Factory function to create KnowledgeServices instance."""
    return KnowledgeServices(db)
