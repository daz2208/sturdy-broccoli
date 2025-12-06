"""
Build Idea Seeds Service for SyncBoard 3.0 Knowledge Bank.

Pre-generates project ideas from document summaries to power
faster and smarter "What Can I Build" suggestions.

Ideas are generated at document level and stored for quick retrieval.
"""

import json
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from sqlalchemy.orm import Session

from .config import settings

logger = logging.getLogger(__name__)

# Configuration
OPENAI_API_KEY = settings.openai_api_key
IDEA_MODEL = settings.idea_model


@dataclass
class IdeaSeed:
    """A pre-computed build idea from a document."""
    title: str
    description: str
    difficulty: str  # beginner, intermediate, advanced
    dependencies: List[str]
    feasibility: str  # high, medium, low
    effort_estimate: str
    referenced_sections: List[int]  # chunk/section IDs


class IdeaSeedsService:
    """Service for generating and managing build idea seeds."""

    def __init__(self):
        """Initialize the idea seeds service."""
        self.api_key = OPENAI_API_KEY
        self.model = IDEA_MODEL
        self._client = None

    @property
    def client(self):
        """Lazy-load OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                logger.error("OpenAI package not installed")
                raise
        return self._client

    def is_available(self) -> bool:
        """Check if idea generation service is available."""
        return bool(self.api_key)

    async def generate_ideas_from_summary(
        self,
        document_summary: str,
        key_concepts: List[str],
        tech_stack: List[str],
        skill_profile: Optional[Dict[str, str]] = None
    ) -> List[IdeaSeed]:
        """
        Generate build ideas from a document summary.

        Args:
            document_summary: Document-level summary text
            key_concepts: Key concepts from the document
            tech_stack: Technologies mentioned in the document
            skill_profile: Skill levels from the document

        Returns:
            List of IdeaSeed objects
        """
        if not self.is_available():
            return []

        concepts_str = ", ".join(key_concepts[:10]) if key_concepts else "general programming"
        tech_str = ", ".join(tech_stack[:10]) if tech_stack else "various technologies"
        skill_str = json.dumps(skill_profile) if skill_profile else "mixed levels"

        system_prompt = """You are a practical software project ideation assistant.

YOUR TASK: Suggest realistic projects someone could build after studying a document.

IDEATION PRINCIPLES:
1. Projects should APPLY what the document teaches, not require additional skills
2. Start simple - a working small project beats an abandoned ambitious one
3. Each project should have a clear, tangible outcome
4. Effort estimates should be realistic for a solo developer

FEASIBILITY CRITERIA:
- "high": Can start within 30 minutes, all skills covered in document
- "medium": Needs 1-2 hours of additional research/setup
- "low": Requires learning concepts not in the document

EFFORT ESTIMATION GUIDE:
- "2-4 hours": Simple CLI tool, basic script
- "1 day": Basic API, simple web app
- "2-3 days": Full-featured API with database
- "1 week": Full-stack application

Generate 2-4 project ideas. Return ONLY valid JSON:
{
    "ideas": [
        {
            "title": "Specific Project Name",
            "description": "2-3 sentences: what it does, why it's useful, what they'll learn",
            "difficulty": "beginner|intermediate|advanced",
            "dependencies": ["concept1", "concept2"],
            "feasibility": "high|medium|low",
            "effort_estimate": "realistic time"
        }
    ]
}"""

        user_prompt = f"""Generate practical project ideas based on this document.

DOCUMENT SUMMARY:
{document_summary[:2000]}

KEY CONCEPTS COVERED: {concepts_str}
TECHNOLOGIES USED: {tech_str}
SKILL LEVEL: {skill_str}

---

EXAMPLE OUTPUT for a Docker Basics document:
{{
  "ideas": [
    {{
      "title": "Dockerized Personal Blog",
      "description": "Create a blog using a static site generator, containerized with Docker. Practice Dockerfiles and container management. Deploy to a free hosting service.",
      "difficulty": "beginner",
      "dependencies": ["docker", "dockerfile", "containers"],
      "feasibility": "high",
      "effort_estimate": "3-4 hours"
    }},
    {{
      "title": "Multi-Container Dev Environment",
      "description": "Set up docker-compose for a web app with separate containers for app, database, and cache. Learn container networking and volumes.",
      "difficulty": "intermediate",
      "dependencies": ["docker", "docker-compose", "networking"],
      "feasibility": "medium",
      "effort_estimate": "1 day"
    }}
  ]
}}

---

Generate 2-4 project ideas using ONLY concepts from this document:"""

        try:
            # Build API parameters
            api_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_completion_tokens": 5000,  # GPT-5 requires max_completion_tokens not max_tokens
                "response_format": {"type": "json_object"}
            }

            # GPT-5 models only support temperature=1 (default), don't add for GPT-5
            if not self.model.startswith("gpt-5"):
                api_params["temperature"] = 0.8  # Higher creativity

            logger.info(f"[SEED GEN] Calling OpenAI API with model={self.model}, max_tokens=5000")

            response = self.client.chat.completions.create(**api_params)

            logger.info(f"[SEED GEN] OpenAI API response received - finish_reason={response.choices[0].finish_reason}")

            result = json.loads(response.choices[0].message.content)
            ideas = result.get("ideas", [])

            logger.info(f"[SEED GEN] Parsed {len(ideas)} ideas from API response")

            return [
                IdeaSeed(
                    title=idea.get("title", "Untitled Project"),
                    description=idea.get("description", ""),
                    difficulty=idea.get("difficulty", "intermediate"),
                    dependencies=idea.get("dependencies", []),
                    feasibility=idea.get("feasibility", "medium"),
                    effort_estimate=idea.get("effort_estimate", "varies"),
                    referenced_sections=[]
                )
                for idea in ideas
            ]

        except json.JSONDecodeError as e:
            logger.error(f"[SEED GEN] JSON parsing failed for model {self.model}: {e}", exc_info=True)
            logger.error(f"[SEED GEN] Response content: {response.choices[0].message.content[:500]}...")
            return []
        except Exception as e:
            logger.error(f"[SEED GEN] API call failed for model {self.model}: {e}", exc_info=True)
            return []

    async def generate_combined_ideas(
        self,
        documents: List[Dict[str, Any]],
        max_ideas: int = 5
    ) -> List[IdeaSeed]:
        """
        Generate ideas that combine knowledge from multiple documents.

        Args:
            documents: List of document dicts with summaries and concepts
            max_ideas: Maximum number of combined ideas to generate

        Returns:
            List of IdeaSeed objects combining multiple documents
        """
        if not self.is_available() or len(documents) < 2:
            return []

        # Collect all concepts and tech
        all_concepts = set()
        all_tech = set()
        summaries = []

        for doc in documents[:5]:  # Limit to 5 documents
            if doc.get("key_concepts"):
                all_concepts.update(doc["key_concepts"])
            if doc.get("tech_stack"):
                all_tech.update(doc["tech_stack"])
            if doc.get("summary"):
                summaries.append(f"Doc {doc.get('doc_id', '?')}: {doc['summary'][:300]}")

        system_prompt = """You are a creative software project ideation assistant specializing in cross-document synthesis.

YOUR TASK: Generate project ideas that COMBINE knowledge from multiple documents.

SYNTHESIS PRINCIPLES:
1. Focus on ideas that wouldn't be possible with just ONE document
2. Look for complementary technologies (e.g., frontend + backend, API + database)
3. Identify "1+1=3" combinations where skills multiply each other's value
4. Projects should leverage the user's unique combination of knowledge

COMBINATION EXAMPLES:
- Docker + Python API docs → Containerized microservice
- React + FastAPI docs → Full-stack application
- PostgreSQL + Data Science docs → Analytics dashboard

FEASIBILITY:
- "high": All required skills covered across the documents
- "medium": Most skills covered, minor gaps
- "low": Significant additional learning needed

Generate ideas that make the user's knowledge MORE VALUABLE together than separately.

Return ONLY valid JSON:
{
    "ideas": [
        {
            "title": "Specific Project Name",
            "description": "What it does and WHY this combination is powerful",
            "difficulty": "beginner|intermediate|advanced",
            "dependencies": ["concept1", "concept2"],
            "feasibility": "high|medium|low",
            "effort_estimate": "realistic time",
            "combines_from": ["doc1 concept", "doc2 concept"]
        }
    ]
}"""

        combined_summaries = "\n\n".join(summaries)
        user_prompt = f"""Based on these document summaries, generate {max_ideas} project ideas
that COMBINE knowledge from multiple documents:

{combined_summaries}

AVAILABLE CONCEPTS: {', '.join(list(all_concepts)[:15])}
AVAILABLE TECHNOLOGIES: {', '.join(list(all_tech)[:15])}

Generate ideas that synthesize knowledge across these documents."""

        try:
            # Build API parameters
            api_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_completion_tokens": 8000,  # GPT-5 requires max_completion_tokens not max_tokens
                "response_format": {"type": "json_object"}
            }

            # GPT-5 models only support temperature=1 (default), don't add for GPT-5
            if not self.model.startswith("gpt-5"):
                api_params["temperature"] = 0.9  # Even higher creativity for combinations

            response = self.client.chat.completions.create(**api_params)

            result = json.loads(response.choices[0].message.content)
            ideas = result.get("ideas", [])

            return [
                IdeaSeed(
                    title=idea.get("title", "Untitled Project"),
                    description=idea.get("description", ""),
                    difficulty=idea.get("difficulty", "intermediate"),
                    dependencies=idea.get("dependencies", []),
                    feasibility=idea.get("feasibility", "medium"),
                    effort_estimate=idea.get("effort_estimate", "varies"),
                    referenced_sections=[]
                )
                for idea in ideas[:max_ideas]
            ]

        except Exception as e:
            logger.error(f"Combined idea generation failed for model {self.model}: {e}", exc_info=True)
            return []


async def generate_document_idea_seeds(
    document_id: int,
    knowledge_base_id: str
) -> Dict[str, Any]:
    """
    Generate and store idea seeds for a document.

    Args:
        document_id: Document ID (internal)
        knowledge_base_id: Knowledge base ID

    Returns:
        Dict with generation results
    """
    from .db_models import DBDocumentSummary, DBBuildIdeaSeed
    from .database import get_db_context

    logger.info(f"[SEED GEN] Starting seed generation for doc_id={document_id}, kb_id={knowledge_base_id}")

    service = IdeaSeedsService()

    if not service.is_available():
        logger.warning(f"[SEED GEN] SKIPPED - API key not configured")
        return {"status": "skipped", "reason": "API key not configured"}

    logger.info(f"[SEED GEN] API key available, model={service.model}")

    # Manage our own database session to avoid transaction warnings
    with get_db_context() as db:
        # Get document summary (level 3 = document level)
        doc_summary = db.query(DBDocumentSummary).filter(
            DBDocumentSummary.document_id == document_id,
            DBDocumentSummary.summary_level == 3
        ).first()

        if not doc_summary:
            logger.warning(f"[SEED GEN] SKIPPED - No document summary found for doc_id={document_id}, level=3")
            return {"status": "skipped", "reason": "No document summary found"}

        logger.info(f"[SEED GEN] Found document summary, extracting data...")

        # Extract data we need before exiting context
        summary_text = doc_summary.long_summary or doc_summary.short_summary
        key_concepts = doc_summary.key_concepts or []
        tech_stack = doc_summary.tech_stack or []
        skill_profile = doc_summary.skill_profile

    logger.info(f"[SEED GEN] Calling OpenAI API - concepts={len(key_concepts)}, tech={len(tech_stack)}, summary_len={len(summary_text) if summary_text else 0}")

    # Generate ideas (outside of db session context)
    ideas = await service.generate_ideas_from_summary(
        document_summary=summary_text,
        key_concepts=key_concepts,
        tech_stack=tech_stack,
        skill_profile=skill_profile
    )

    if not ideas:
        logger.warning(f"[SEED GEN] FAILED - OpenAI returned no ideas for doc_id={document_id}")
        return {"status": "skipped", "reason": "No ideas generated"}

    logger.info(f"[SEED GEN] SUCCESS - Generated {len(ideas)} ideas, now storing to database...")

    # Store ideas in a new database session
    try:
        with get_db_context() as db:
            # Delete existing ideas for this document
            db.query(DBBuildIdeaSeed).filter(
                DBBuildIdeaSeed.document_id == document_id
            ).delete()

            # Store new ideas
            for idx, idea in enumerate(ideas):
                db_idea = DBBuildIdeaSeed(
                    document_id=document_id,
                    knowledge_base_id=knowledge_base_id,
                    title=idea.title,
                    description=idea.description,
                    difficulty=idea.difficulty,
                    dependencies=idea.dependencies,
                    feasibility=idea.feasibility,
                    effort_estimate=idea.effort_estimate,
                    referenced_sections=idea.referenced_sections
                )
                db.add(db_idea)
                logger.debug(f"[SEED GEN] Added idea {idx+1}/{len(ideas)}: {idea.title}")

            db.commit()
            logger.info(f"[SEED GEN] COMPLETE - Stored {len(ideas)} ideas to database for doc_id={document_id}")

    except Exception as e:
        logger.error(f"[SEED GEN] DATABASE ERROR - Failed to store ideas: {e}", exc_info=True)
        return {"status": "error", "reason": f"Database error: {str(e)}"}

    logger.info(f"Generated {len(ideas)} idea seeds for document {document_id}")

    return {
        "status": "success",
        "ideas_generated": len(ideas),
        "ideas": [
            {
                "title": i.title,
                "difficulty": i.difficulty,
                "feasibility": i.feasibility
            }
            for i in ideas
        ]
    }


async def get_user_idea_seeds(
    db: Session,
    knowledge_base_id: str,
    difficulty: Optional[str] = None,
    limit: int = 20,
    username: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get stored idea seeds for a knowledge base.

    If no ideas found in the specified KB and username is provided,
    falls back to querying all user's KBs. This handles the case where
    the user's default KB changed after ideas were generated.

    Args:
        db: Database session
        knowledge_base_id: Knowledge base ID (primary)
        difficulty: Optional difficulty filter
        limit: Maximum results
        username: Optional username for cross-KB fallback query

    Returns:
        List of idea dicts
    """
    from .db_models import DBBuildIdeaSeed, DBDocument, DBKnowledgeBase

    # First, try the specified knowledge base
    query = db.query(DBBuildIdeaSeed).filter(
        DBBuildIdeaSeed.knowledge_base_id == knowledge_base_id
    )

    if difficulty:
        query = query.filter(DBBuildIdeaSeed.difficulty == difficulty)

    ideas = query.order_by(DBBuildIdeaSeed.created_at.desc()).limit(limit).all()

    # If no ideas found and username provided, try all user's KBs
    if not ideas and username:
        logger.info(f"No ideas in default KB {knowledge_base_id}, checking all KBs for user {username}")

        # Get all KB IDs for this user
        user_kb_ids = [
            kb.id for kb in db.query(DBKnowledgeBase).filter(
                DBKnowledgeBase.owner_username == username
            ).all()
        ]

        if user_kb_ids:
            query = db.query(DBBuildIdeaSeed).filter(
                DBBuildIdeaSeed.knowledge_base_id.in_(user_kb_ids)
            )

            if difficulty:
                query = query.filter(DBBuildIdeaSeed.difficulty == difficulty)

            ideas = query.order_by(DBBuildIdeaSeed.created_at.desc()).limit(limit).all()
            logger.info(f"Found {len(ideas)} ideas across all user KBs")

    results = []
    for idea in ideas:
        # Get document info
        doc = db.query(DBDocument).filter_by(id=idea.document_id).first()

        results.append({
            "id": idea.id,
            "title": idea.title,
            "description": idea.description,
            "difficulty": idea.difficulty,
            "feasibility": idea.feasibility,
            "effort_estimate": idea.effort_estimate,
            "dependencies": idea.dependencies,
            "source_document": {
                "id": doc.doc_id if doc else None,
                "filename": doc.filename if doc else None,
                "source_type": doc.source_type if doc else None
            },
            "created_at": idea.created_at.isoformat() if idea.created_at else None
        })

    return results


async def generate_kb_combined_ideas(
    db: Session,
    knowledge_base_id: str,
    max_ideas: int = 5
) -> List[Dict[str, Any]]:
    """
    Generate ideas that combine multiple documents in a knowledge base.

    Args:
        db: Database session
        knowledge_base_id: Knowledge base ID
        max_ideas: Maximum ideas to generate

    Returns:
        List of combined idea dicts
    """
    from .db_models import DBDocumentSummary, DBDocument

    service = IdeaSeedsService()

    if not service.is_available():
        return []

    # Get document summaries (level 3 = document level)
    summaries = db.query(DBDocumentSummary).filter(
        DBDocumentSummary.knowledge_base_id == knowledge_base_id,
        DBDocumentSummary.summary_level == 3
    ).limit(10).all()

    if len(summaries) < 2:
        return []

    # Prepare document data
    documents = []
    for summary in summaries:
        doc = db.query(DBDocument).filter_by(id=summary.document_id).first()
        documents.append({
            "doc_id": doc.doc_id if doc else None,
            "summary": summary.long_summary or summary.short_summary,
            "key_concepts": summary.key_concepts or [],
            "tech_stack": summary.tech_stack or []
        })

    # Generate combined ideas
    ideas = await service.generate_combined_ideas(documents, max_ideas)

    return [
        {
            "title": idea.title,
            "description": idea.description,
            "difficulty": idea.difficulty,
            "feasibility": idea.feasibility,
            "effort_estimate": idea.effort_estimate,
            "dependencies": idea.dependencies,
            "type": "combined"
        }
        for idea in ideas
    ]


# Singleton instance
_idea_seeds_service: Optional[IdeaSeedsService] = None


def get_idea_seeds_service() -> IdeaSeedsService:
    """Get or create the idea seeds service singleton."""
    global _idea_seeds_service
    if _idea_seeds_service is None:
        _idea_seeds_service = IdeaSeedsService()
    return _idea_seeds_service
