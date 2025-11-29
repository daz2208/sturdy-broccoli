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

        system_prompt = """You are a creative software project ideation assistant.
Given a document summary and its key concepts, generate 2-4 practical project ideas
that someone could build after learning from this document.

For each idea, provide:
1. title: A catchy, descriptive project name
2. description: 2-3 sentences explaining the project and its value
3. difficulty: "beginner", "intermediate", or "advanced"
4. dependencies: List of concepts/skills needed (from the document)
5. feasibility: "high" (can start immediately), "medium" (needs some prep), "low" (requires additional learning)
6. effort_estimate: Time estimate like "2-3 hours", "1 day", "1 week"

Respond in JSON format:
{
    "ideas": [
        {
            "title": "...",
            "description": "...",
            "difficulty": "...",
            "dependencies": ["concept1", "concept2"],
            "feasibility": "...",
            "effort_estimate": "..."
        }
    ]
}"""

        user_prompt = f"""Based on this document summary, generate practical project ideas:

SUMMARY:
{document_summary[:2000]}

KEY CONCEPTS: {concepts_str}
TECHNOLOGIES: {tech_str}
SKILL LEVEL: {skill_str}

Generate 2-4 project ideas that apply the knowledge from this document."""

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
                for idea in ideas
            ]

        except Exception as e:
            logger.error(f"Idea generation failed for model {self.model}: {e}", exc_info=True)
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

        system_prompt = """You are a creative software project ideation assistant.
Given summaries from multiple documents in a knowledge bank, generate project ideas
that COMBINE knowledge from two or more documents.

Focus on ideas that wouldn't be possible with just one document - projects that
synthesize different technologies or concepts together.

Respond in JSON format:
{
    "ideas": [
        {
            "title": "...",
            "description": "...",
            "difficulty": "...",
            "dependencies": ["concept1", "concept2"],
            "feasibility": "...",
            "effort_estimate": "...",
            "combines_from": ["doc concept 1", "doc concept 2"]
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

    service = IdeaSeedsService()

    if not service.is_available():
        return {"status": "skipped", "reason": "API key not configured"}

    # Manage our own database session to avoid transaction warnings
    with get_db_context() as db:
        # Get document summary (level 3 = document level)
        doc_summary = db.query(DBDocumentSummary).filter(
            DBDocumentSummary.document_id == document_id,
            DBDocumentSummary.summary_level == 3
        ).first()

        if not doc_summary:
            return {"status": "skipped", "reason": "No document summary found"}

        # Extract data we need before exiting context
        summary_text = doc_summary.long_summary or doc_summary.short_summary
        key_concepts = doc_summary.key_concepts or []
        tech_stack = doc_summary.tech_stack or []
        skill_profile = doc_summary.skill_profile

    # Generate ideas (outside of db session context)
    ideas = await service.generate_ideas_from_summary(
        document_summary=summary_text,
        key_concepts=key_concepts,
        tech_stack=tech_stack,
        skill_profile=skill_profile
    )

    if not ideas:
        return {"status": "skipped", "reason": "No ideas generated"}

    # Store ideas in a new database session
    with get_db_context() as db:
        # Delete existing ideas for this document
        db.query(DBBuildIdeaSeed).filter(
            DBBuildIdeaSeed.document_id == document_id
        ).delete()

        # Store new ideas
        for idea in ideas:
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

        db.commit()

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
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Get stored idea seeds for a knowledge base.

    Args:
        db: Database session
        knowledge_base_id: Knowledge base ID
        difficulty: Optional difficulty filter
        limit: Maximum results

    Returns:
        List of idea dicts
    """
    from .db_models import DBBuildIdeaSeed, DBDocument

    query = db.query(DBBuildIdeaSeed).filter(
        DBBuildIdeaSeed.knowledge_base_id == knowledge_base_id
    )

    if difficulty:
        query = query.filter(DBBuildIdeaSeed.difficulty == difficulty)

    ideas = query.order_by(DBBuildIdeaSeed.created_at.desc()).limit(limit).all()

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
