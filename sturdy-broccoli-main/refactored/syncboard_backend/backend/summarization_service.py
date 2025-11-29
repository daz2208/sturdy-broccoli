"""
Hierarchical Summarization Service for SyncBoard 3.0 Knowledge Bank.

Generates multi-level summaries:
- Level 1: Chunk summaries (per-chunk)
- Level 2: Section summaries (groups of 3-5 chunks)
- Level 3: Document summaries (full document)

Uses OpenAI GPT models for summarization with structured output.
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
SUMMARY_MODEL = settings.summary_model
CHUNKS_PER_SECTION = 4  # Number of chunks to combine into a section


@dataclass
class SummaryResult:
    """Result from summarization."""
    short_summary: str
    long_summary: Optional[str] = None
    key_concepts: Optional[List[str]] = None
    tech_stack: Optional[List[str]] = None
    skill_profile: Optional[Dict[str, str]] = None


class SummarizationService:
    """Service for generating hierarchical document summaries."""

    def __init__(self):
        """Initialize the summarization service."""
        self.api_key = OPENAI_API_KEY
        self.model = SUMMARY_MODEL
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
        """Check if summarization service is available."""
        return bool(self.api_key)

    async def summarize_chunk(self, chunk_text: str, context: Optional[str] = None) -> SummaryResult:
        """
        Generate a summary for a single chunk.

        Args:
            chunk_text: The chunk content to summarize
            context: Optional context (e.g., document title, previous chunks)

        Returns:
            SummaryResult with short summary and extracted concepts
        """
        if not self.is_available():
            return SummaryResult(
                short_summary="Summarization unavailable - API key not configured",
                key_concepts=[]
            )

        system_prompt = """You are a technical documentation summarizer. Given a text chunk, provide:
1. A concise summary (2-3 sentences, max 100 words)
2. Key concepts mentioned (up to 5)
3. Technologies/tools mentioned (if any)

Respond in JSON format:
{
    "short_summary": "...",
    "key_concepts": ["concept1", "concept2"],
    "tech_stack": ["tech1", "tech2"]
}"""

        user_prompt = f"Summarize this text chunk:\n\n{chunk_text[:3000]}"  # Limit input size
        if context:
            user_prompt = f"Context: {context}\n\n{user_prompt}"

        try:
            # Build params based on model (prefer max_completion_tokens to satisfy new API requirements)
            params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"}
            }

            params["max_completion_tokens"] = 5000  # Increased from 300 for comprehensive chunk summaries

            # GPT-5 models only support temperature=1 (default), don't add for GPT-5
            if not self.model.startswith("gpt-5"):
                params["temperature"] = 0.3

            response = self.client.chat.completions.create(**params)

            result = json.loads(response.choices[0].message.content)

            return SummaryResult(
                short_summary=result.get("short_summary", ""),
                key_concepts=result.get("key_concepts", []),
                tech_stack=result.get("tech_stack", [])
            )

        except Exception as e:
            logger.error(f"Chunk summarization failed: {e}")
            return SummaryResult(
                short_summary=chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text,
                key_concepts=[]
            )

    async def summarize_section(
        self,
        chunk_summaries: List[SummaryResult],
        chunk_texts: Optional[List[str]] = None
    ) -> SummaryResult:
        """
        Generate a section summary from multiple chunk summaries.

        Args:
            chunk_summaries: List of chunk-level summaries
            chunk_texts: Optional original chunk texts for context

        Returns:
            SummaryResult with section summary
        """
        if not self.is_available():
            # Combine chunk summaries as fallback
            combined = " ".join([s.short_summary for s in chunk_summaries])
            return SummaryResult(short_summary=combined[:500])

        # Prepare chunk summaries for input
        summaries_text = "\n".join([
            f"- {s.short_summary}" for s in chunk_summaries
        ])

        # Collect all concepts
        all_concepts = []
        all_tech = []
        for s in chunk_summaries:
            if s.key_concepts:
                all_concepts.extend(s.key_concepts)
            if s.tech_stack:
                all_tech.extend(s.tech_stack)

        system_prompt = """You are a technical documentation summarizer. Given multiple chunk summaries from a section, provide:
1. A coherent section summary (3-5 sentences, max 200 words) that synthesizes the main points
2. The most important concepts from this section (up to 7)
3. Technologies mentioned (consolidated list)
4. A brief skill profile if applicable

Respond in JSON format:
{
    "short_summary": "...",
    "long_summary": "...",
    "key_concepts": ["concept1", "concept2"],
    "tech_stack": ["tech1", "tech2"],
    "skill_profile": {"area": "level"}
}"""

        user_prompt = f"Synthesize these chunk summaries into a coherent section summary:\n\n{summaries_text}"

        try:
            # Build params based on model (prefer max_completion_tokens to satisfy new API requirements)
            params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"}
            }

            params["max_completion_tokens"] = 6000  # Increased from 500 for comprehensive section summaries

            # GPT-5 models only support temperature=1 (default), don't add for GPT-5
            if not self.model.startswith("gpt-5"):
                params["temperature"] = 0.3

            response = self.client.chat.completions.create(**params)

            result = json.loads(response.choices[0].message.content)

            return SummaryResult(
                short_summary=result.get("short_summary", ""),
                long_summary=result.get("long_summary"),
                key_concepts=result.get("key_concepts", list(set(all_concepts))[:7]),
                tech_stack=result.get("tech_stack", list(set(all_tech))),
                skill_profile=result.get("skill_profile")
            )

        except Exception as e:
            logger.error(f"Section summarization failed: {e}")
            return SummaryResult(
                short_summary=" ".join([s.short_summary for s in chunk_summaries])[:500],
                key_concepts=list(set(all_concepts))[:7],
                tech_stack=list(set(all_tech))
            )

    async def summarize_document(
        self,
        section_summaries: List[SummaryResult],
        document_title: Optional[str] = None,
        source_type: Optional[str] = None
    ) -> SummaryResult:
        """
        Generate a document-level summary from section summaries.

        Args:
            section_summaries: List of section-level summaries
            document_title: Optional document title for context
            source_type: Optional source type (pdf, url, etc.)

        Returns:
            SummaryResult with comprehensive document summary
        """
        if not self.is_available():
            combined = " ".join([s.short_summary for s in section_summaries])
            return SummaryResult(short_summary=combined[:800])

        # Prepare section summaries
        sections_text = "\n\n".join([
            f"Section {i+1}:\n{s.short_summary}" +
            (f"\nLong: {s.long_summary}" if s.long_summary else "")
            for i, s in enumerate(section_summaries)
        ])

        # Aggregate concepts and tech
        all_concepts = []
        all_tech = []
        all_skills = {}
        for s in section_summaries:
            if s.key_concepts:
                all_concepts.extend(s.key_concepts)
            if s.tech_stack:
                all_tech.extend(s.tech_stack)
            if s.skill_profile:
                all_skills.update(s.skill_profile)

        context = ""
        if document_title:
            context += f"Document: {document_title}\n"
        if source_type:
            context += f"Source type: {source_type}\n"

        system_prompt = """You are a technical documentation summarizer. Given section summaries from a complete document, provide:
1. A comprehensive document summary (5-8 sentences, max 300 words)
2. An executive short summary (1-2 sentences)
3. The core concepts covered in the document (up to 10)
4. Complete technology stack mentioned
5. Skill profile required to understand this content

Respond in JSON format:
{
    "short_summary": "1-2 sentence executive summary",
    "long_summary": "comprehensive 5-8 sentence summary",
    "key_concepts": ["concept1", "concept2", ...],
    "tech_stack": ["tech1", "tech2", ...],
    "skill_profile": {"area": "beginner|intermediate|advanced"}
}"""

        user_prompt = f"{context}\nSynthesize these section summaries into a complete document summary:\n\n{sections_text}"

        try:
            # Build params based on model (prefer max_completion_tokens to satisfy new API requirements)
            params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"}
            }

            params["max_completion_tokens"] = 10000  # Increased from 700 for full document summaries with complete analysis

            # GPT-5 models only support temperature=1 (default), don't add for GPT-5
            if not self.model.startswith("gpt-5"):
                params["temperature"] = 0.3

            response = self.client.chat.completions.create(**params)

            result = json.loads(response.choices[0].message.content)

            return SummaryResult(
                short_summary=result.get("short_summary", ""),
                long_summary=result.get("long_summary"),
                key_concepts=result.get("key_concepts", list(set(all_concepts))[:10]),
                tech_stack=result.get("tech_stack", list(set(all_tech))),
                skill_profile=result.get("skill_profile", all_skills)
            )

        except Exception as e:
            logger.error(f"Document summarization failed: {e}")
            return SummaryResult(
                short_summary=" ".join([s.short_summary for s in section_summaries])[:800],
                key_concepts=list(set(all_concepts))[:10],
                tech_stack=list(set(all_tech)),
                skill_profile=all_skills
            )


async def generate_hierarchical_summaries(
    db: Session,
    document_id: int,
    knowledge_base_id: str,
    chunks: List[Dict[str, Any]],
    generate_ideas: bool = False
) -> Dict[str, Any]:
    """
    Generate hierarchical summaries for a document's chunks.

    Args:
        db: Database session
        document_id: Document ID (internal)
        knowledge_base_id: Knowledge base ID
        chunks: List of chunk dicts with 'id', 'content', 'chunk_index'
        generate_ideas: Whether to also generate build idea seeds

    Returns:
        Dict with summary statistics
    """
    from .db_models import DBDocumentSummary

    service = SummarizationService()

    if not service.is_available():
        logger.warning("Summarization service not available - skipping")
        return {"status": "skipped", "reason": "API key not configured"}

    if not chunks:
        return {"status": "skipped", "reason": "No chunks to summarize"}

    # Sort chunks by index
    sorted_chunks = sorted(chunks, key=lambda c: c.get('chunk_index', 0))

    # Level 1: Generate chunk summaries
    chunk_summaries = []
    chunk_summary_records = []

    for chunk in sorted_chunks:
        result = await service.summarize_chunk(chunk['content'])
        chunk_summaries.append({
            'chunk_id': chunk['id'],
            'result': result
        })

        # Create DB record
        summary_record = DBDocumentSummary(
            document_id=document_id,
            knowledge_base_id=knowledge_base_id,
            summary_type='chunk',
            summary_level=1,
            chunk_id=chunk['id'],
            short_summary=result.short_summary,
            key_concepts=result.key_concepts,
            tech_stack=result.tech_stack
        )
        db.add(summary_record)
        chunk_summary_records.append(summary_record)

    db.flush()  # Get IDs for chunk summaries

    # Level 2: Generate section summaries (group chunks)
    section_summaries = []
    section_records = []

    for i in range(0, len(chunk_summaries), CHUNKS_PER_SECTION):
        section_chunks = chunk_summaries[i:i + CHUNKS_PER_SECTION]
        section_results = [c['result'] for c in section_chunks]

        section_result = await service.summarize_section(section_results)
        section_summaries.append(section_result)

        # Create DB record
        section_record = DBDocumentSummary(
            document_id=document_id,
            knowledge_base_id=knowledge_base_id,
            summary_type='section',
            summary_level=2,
            short_summary=section_result.short_summary,
            long_summary=section_result.long_summary,
            key_concepts=section_result.key_concepts,
            tech_stack=section_result.tech_stack,
            skill_profile=section_result.skill_profile
        )
        db.add(section_record)
        db.flush()
        section_records.append(section_record)

        # Link chunk summaries to section
        for j, chunk_rec in enumerate(chunk_summary_records[i:i + CHUNKS_PER_SECTION]):
            chunk_rec.parent_id = section_record.id

    # Level 3: Generate document summary
    if section_summaries:
        doc_result = await service.summarize_document(section_summaries)

        doc_summary = DBDocumentSummary(
            document_id=document_id,
            knowledge_base_id=knowledge_base_id,
            summary_type='document',
            summary_level=3,
            short_summary=doc_result.short_summary,
            long_summary=doc_result.long_summary,
            key_concepts=doc_result.key_concepts,
            tech_stack=doc_result.tech_stack,
            skill_profile=doc_result.skill_profile
        )
        db.add(doc_summary)
        db.flush()

        # Link section summaries to document
        for section_rec in section_records:
            section_rec.parent_id = doc_summary.id

    db.commit()

    logger.info(
        f"Generated summaries for document {document_id}: "
        f"{len(chunk_summaries)} chunks, {len(section_summaries)} sections, 1 document"
    )

    result = {
        "status": "success",
        "chunk_summaries": len(chunk_summaries),
        "section_summaries": len(section_summaries),
        "document_summary": 1
    }

    # Optionally generate build idea seeds
    if generate_ideas:
        try:
            from .idea_seeds_service import generate_document_idea_seeds
            ideas_result = await generate_document_idea_seeds(
                db=db,
                document_id=document_id,
                knowledge_base_id=knowledge_base_id
            )
            result["ideas_generated"] = ideas_result.get("ideas_generated", 0)
            logger.info(f"Generated {result['ideas_generated']} idea seeds for document {document_id}")
        except Exception as e:
            logger.warning(f"Idea generation failed for doc {document_id}: {e}")
            result["ideas_error"] = str(e)

    return result


async def get_document_summary(
    db: Session,
    document_id: int,
    level: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Get summaries for a document.

    Args:
        db: Database session
        document_id: Document ID (internal)
        level: Optional level filter (1=chunk, 2=section, 3=document)

    Returns:
        List of summary dicts
    """
    from .db_models import DBDocumentSummary

    query = db.query(DBDocumentSummary).filter(
        DBDocumentSummary.document_id == document_id
    )

    if level:
        query = query.filter(DBDocumentSummary.summary_level == level)

    summaries = query.order_by(
        DBDocumentSummary.summary_level.desc(),
        DBDocumentSummary.id
    ).all()

    return [
        {
            "id": s.id,
            "summary_type": s.summary_type,
            "summary_level": s.summary_level,
            "short_summary": s.short_summary,
            "long_summary": s.long_summary,
            "key_concepts": s.key_concepts,
            "tech_stack": s.tech_stack,
            "skill_profile": s.skill_profile,
            "parent_id": s.parent_id,
            "chunk_id": s.chunk_id
        }
        for s in summaries
    ]


# Singleton instance
_summarization_service: Optional[SummarizationService] = None


def get_summarization_service() -> SummarizationService:
    """Get or create the summarization service singleton."""
    global _summarization_service
    if _summarization_service is None:
        _summarization_service = SummarizationService()
    return _summarization_service
