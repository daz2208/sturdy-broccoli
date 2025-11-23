"""
Knowledge Tools Router for SyncBoard 3.0.

Endpoints for advanced knowledge enhancement features:
- GET  /knowledge/gaps - Analyze knowledge gaps
- POST /knowledge/flashcards/{doc_id} - Generate flashcards
- GET  /knowledge/digest - Weekly learning digest
- POST /knowledge/learning-path - Optimize learning path
- GET  /knowledge/quality/{doc_id} - Score document quality
- POST /knowledge/chat - Conversation-style RAG
- POST /knowledge/generate-code - Generate code from concepts
- POST /knowledge/compare - Compare two documents
- POST /knowledge/eli5 - Explain topic simply
- POST /knowledge/interview-prep - Generate interview materials
- POST /knowledge/debug - Debug errors with KB context
"""

import logging
from typing import Optional, List
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from ..models import User
from ..dependencies import get_current_user, get_user_default_kb_id
from ..database import get_db

logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(
    prefix="/knowledge",
    tags=["knowledge-tools"],
    responses={401: {"description": "Unauthorized"}},
)

# Try to import knowledge services
try:
    from ..knowledge_services import (
        KnowledgeServices,
        get_knowledge_services,
        GapAnalysisResult,
        Flashcard,
        WeeklyDigest,
        LearningPath,
        DocumentQuality,
        DocumentComparison,
        InterviewPrep,
        DebugAssistantResult,
    )
    KNOWLEDGE_SERVICES_AVAILABLE = True
    logger.info("[SUCCESS] Knowledge services loaded")
except ImportError as e:
    KNOWLEDGE_SERVICES_AVAILABLE = False
    logger.warning(f"[WARNING] Knowledge services not available: {e}")


# =============================================================================
# Request/Response Models
# =============================================================================

class FlashcardRequest(BaseModel):
    num_cards: int = Field(default=10, ge=1, le=30)
    difficulty_mix: str = Field(default="balanced", pattern="^(easy|balanced|hard)$")


class LearningPathRequest(BaseModel):
    goal: str = Field(..., min_length=3, max_length=500)


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    conversation_history: Optional[List[dict]] = None


class CompareRequest(BaseModel):
    doc_a_id: int
    doc_b_id: int


class ELI5Request(BaseModel):
    topic: str = Field(..., min_length=1, max_length=200)


class InterviewPrepRequest(BaseModel):
    role: Optional[str] = None
    level: str = Field(default="mid", pattern="^(junior|mid|senior)$")


class CodeGenerateRequest(BaseModel):
    project_type: str = Field(default="starter")
    language: str = Field(default="python")


class DebugRequest(BaseModel):
    error_message: str = Field(..., min_length=1, max_length=5000)
    code_snippet: Optional[str] = Field(default=None, max_length=10000)
    context: Optional[str] = Field(default=None, max_length=2000)


# =============================================================================
# Helper
# =============================================================================

def check_services():
    """Check if services are available."""
    if not KNOWLEDGE_SERVICES_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Knowledge services not available. Check server logs."
        )


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/gaps")
@limiter.limit("3/minute")
async def analyze_knowledge_gaps(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze the knowledge base to identify gaps and missing areas.

    Returns:
    - Critical knowledge gaps
    - Shallow coverage areas
    - Recommended learning path
    - Inferred learning goal
    - Strongest areas

    Rate limited: 3/minute
    """
    check_services()

    kb_id = get_user_default_kb_id(current_user.username, db)
    services = get_knowledge_services(db)

    try:
        result = await services.analyze_knowledge_gaps(current_user.username, kb_id)

        return {
            "status": "success",
            "total_documents": result.total_documents,
            "total_concepts": result.total_concepts,
            "inferred_goal": result.inferred_goal,
            "strongest_areas": result.strongest_areas,
            "coverage_areas": result.coverage_areas,
            "gaps": [
                {
                    "area": g.area,
                    "severity": g.severity,
                    "description": g.description,
                    "suggested_topics": g.suggested_topics,
                    "learning_priority": g.learning_priority
                }
                for g in result.gaps
            ],
            "shallow_areas": result.shallow_areas,
            "recommended_learning_path": result.recommended_learning_path
        }

    except Exception as e:
        logger.error(f"Gap analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flashcards/{doc_id}")
@limiter.limit("5/minute")
async def generate_flashcards(
    doc_id: int,
    req: FlashcardRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate study flashcards from a document.

    Args:
    - doc_id: Document to generate cards from
    - num_cards: Number of cards (1-30, default 10)
    - difficulty_mix: easy, balanced, or hard

    Rate limited: 5/minute
    """
    check_services()

    services = get_knowledge_services(db)

    try:
        cards = await services.generate_flashcards(
            doc_id=doc_id,
            num_cards=req.num_cards,
            difficulty_mix=req.difficulty_mix
        )

        return {
            "status": "success",
            "doc_id": doc_id,
            "cards_generated": len(cards),
            "flashcards": [
                {
                    "front": c.front,
                    "back": c.back,
                    "difficulty": c.difficulty,
                    "concept": c.concept,
                    "source_section": c.source_section
                }
                for c in cards
            ]
        }

    except Exception as e:
        logger.error(f"Flashcard generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/digest")
@limiter.limit("3/minute")
async def get_weekly_digest(
    request: Request,
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate a digest of recent learning activity.

    Args:
    - days: Number of days to look back (default 7)

    Returns:
    - Executive summary
    - New concepts learned
    - Skills improved
    - Focus suggestions
    - Quick wins

    Rate limited: 3/minute
    """
    check_services()

    kb_id = get_user_default_kb_id(current_user.username, db)
    services = get_knowledge_services(db)

    try:
        digest = await services.generate_weekly_digest(
            current_user.username, kb_id, days=min(days, 30)
        )

        return {
            "status": "success",
            "period": {
                "start": digest.period_start.isoformat(),
                "end": digest.period_end.isoformat(),
                "days": days
            },
            "documents_added": digest.documents_added,
            "executive_summary": digest.executive_summary,
            "new_concepts": digest.new_concepts,
            "skills_improved": digest.skills_improved,
            "focus_suggestions": digest.focus_suggestions,
            "connections_to_existing": digest.connections_to_existing,
            "quick_wins": digest.quick_wins
        }

    except Exception as e:
        logger.error(f"Digest generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/learning-path")
@limiter.limit("3/minute")
async def optimize_learning_path(
    req: LearningPathRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create an optimized learning path for a specific goal.

    Args:
    - goal: What you want to learn/achieve

    Returns:
    - Ordered list of documents with time estimates
    - Checkpoints after each section
    - Documents to skip
    - External resources to supplement

    Rate limited: 3/minute
    """
    check_services()

    kb_id = get_user_default_kb_id(current_user.username, db)
    services = get_knowledge_services(db)

    try:
        path = await services.optimize_learning_path(
            current_user.username, kb_id, req.goal
        )

        return {
            "status": "success",
            "goal": path.goal,
            "total_documents": path.total_documents,
            "estimated_hours": path.estimated_hours,
            "ordered_documents": path.ordered_docs,
            "skip_list": path.skip_list,
            "external_resources": path.external_resources
        }

    except Exception as e:
        logger.error(f"Learning path generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quality/{doc_id}")
@limiter.limit("10/minute")
async def score_document_quality(
    doc_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Rate a document's quality and usefulness.

    Returns scores (1-10) for:
    - Information density
    - Actionability
    - Currency
    - Uniqueness
    - Overall score

    Also provides:
    - Key excerpts worth highlighting
    - Sections to skip
    - Missing context

    Rate limited: 10/minute
    """
    check_services()

    services = get_knowledge_services(db)

    try:
        quality = await services.score_document_quality(doc_id)

        return {
            "status": "success",
            "doc_id": quality.doc_id,
            "scores": {
                "information_density": quality.information_density,
                "actionability": quality.actionability,
                "currency": quality.currency,
                "uniqueness": quality.uniqueness,
                "overall": quality.overall_score
            },
            "key_excerpts": quality.key_excerpts,
            "sections_to_skip": quality.sections_to_skip,
            "missing_context": quality.missing_context
        }

    except Exception as e:
        logger.error(f"Quality scoring failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat")
@limiter.limit("10/minute")
async def conversation_chat(
    req: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Multi-turn conversation with knowledge base context.

    Args:
    - query: Your question
    - conversation_history: Previous turns (optional)

    Returns:
    - Response with context
    - Suggested follow-up questions

    Rate limited: 10/minute
    """
    check_services()

    kb_id = get_user_default_kb_id(current_user.username, db)
    services = get_knowledge_services(db)

    try:
        result = await services.conversation_rag(
            query=req.query,
            kb_id=kb_id,
            conversation_history=req.conversation_history
        )

        return {
            "status": "success",
            **result
        }

    except Exception as e:
        error_msg = str(e).lower()
        logger.error(f"Conversation failed for user {current_user.username}: {e}")

        # Provide specific error messages for common issues
        if "api key" in error_msg or "authentication" in error_msg or "openai" in error_msg:
            raise HTTPException(
                status_code=503,
                detail="AI service not configured. Please set OPENAI_API_KEY in environment."
            )
        elif "rate limit" in error_msg:
            raise HTTPException(
                status_code=429,
                detail="AI service rate limited. Please wait a moment and try again."
            )
        elif "connection" in error_msg or "timeout" in error_msg:
            raise HTTPException(
                status_code=503,
                detail="Could not connect to AI service. Please try again."
            )
        else:
            raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/generate-code")
@limiter.limit("3/minute")
async def generate_code(
    req: CodeGenerateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate starter code based on concepts in the knowledge base.

    Args:
    - project_type: Type of project (starter, api, cli, etc.)
    - language: Programming language (python, javascript, etc.)

    Returns:
    - Complete project files
    - Setup instructions
    - Concepts demonstrated

    Rate limited: 3/minute
    """
    check_services()

    kb_id = get_user_default_kb_id(current_user.username, db)
    services = get_knowledge_services(db)

    try:
        result = await services.generate_code_from_concepts(
            kb_id=kb_id,
            project_type=req.project_type,
            language=req.language
        )

        return {
            "status": "success",
            **result
        }

    except Exception as e:
        logger.error(f"Code generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
@limiter.limit("5/minute")
async def compare_documents(
    req: CompareRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Compare two documents for overlaps and contradictions.

    Args:
    - doc_a_id: First document ID
    - doc_b_id: Second document ID

    Returns:
    - Overlapping concepts
    - Contradictions
    - Complementary information
    - Recommended reading order
    - Synthesis

    Rate limited: 5/minute
    """
    check_services()

    services = get_knowledge_services(db)

    try:
        comparison = await services.compare_documents(req.doc_a_id, req.doc_b_id)

        return {
            "status": "success",
            "doc_a_id": comparison.doc_a_id,
            "doc_b_id": comparison.doc_b_id,
            "overlapping_concepts": comparison.overlapping_concepts,
            "contradictions": comparison.contradictions,
            "complementary_info": comparison.complementary_info,
            "more_authoritative": comparison.more_authoritative,
            "recommended_order": comparison.recommended_order,
            "synthesis": comparison.synthesis
        }

    except Exception as e:
        logger.error(f"Document comparison failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/eli5")
@limiter.limit("10/minute")
async def explain_simply(
    req: ELI5Request,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Explain a topic in simple terms (ELI5 style).

    Args:
    - topic: Topic to explain

    Returns:
    - Simple explanation
    - Real-world analogy
    - Why it matters
    - Simple example
    - What to learn next

    Rate limited: 10/minute
    """
    check_services()

    kb_id = get_user_default_kb_id(current_user.username, db)
    services = get_knowledge_services(db)

    try:
        result = await services.explain_eli5(req.topic, kb_id)

        return {
            "status": "success",
            **result
        }

    except Exception as e:
        logger.error(f"ELI5 explanation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/interview-prep")
@limiter.limit("3/minute")
async def generate_interview_prep(
    req: InterviewPrepRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate interview preparation materials.

    Args:
    - role: Target role (optional, inferred from KB)
    - level: junior, mid, or senior

    Returns:
    - Behavioral questions
    - Technical questions with answers
    - System design questions
    - Gotcha questions
    - Study recommendations

    Rate limited: 3/minute
    """
    check_services()

    kb_id = get_user_default_kb_id(current_user.username, db)
    services = get_knowledge_services(db)

    try:
        prep = await services.generate_interview_prep(
            kb_id=kb_id,
            role=req.role,
            level=req.level
        )

        return {
            "status": "success",
            "topics_covered": prep.topics,
            "behavioral_questions": prep.behavioral_questions,
            "technical_questions": prep.technical_questions,
            "system_design_questions": prep.system_design_questions,
            "gotcha_questions": prep.gotcha_questions,
            "study_recommendations": prep.study_recommendations
        }

    except Exception as e:
        logger.error(f"Interview prep generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/debug")
@limiter.limit("10/minute")
async def debug_error(
    req: DebugRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Debug an error using knowledge base context.

    Paste in an error message and optional code snippet, get:
    - Likely cause analysis
    - Step-by-step fix instructions
    - Code suggestions if applicable
    - Related documentation from your KB
    - Prevention tips for the future

    Args:
    - error_message: The error or exception message
    - code_snippet: Optional code that caused the error
    - context: Optional additional context

    Rate limited: 10/minute
    """
    check_services()

    kb_id = get_user_default_kb_id(current_user.username, db)
    services = get_knowledge_services(db)

    try:
        result = await services.debug_error(
            error_message=req.error_message,
            code_snippet=req.code_snippet,
            context=req.context,
            kb_id=kb_id
        )

        return {
            "status": "success",
            "error_message": result.error_message,
            "likely_cause": result.likely_cause,
            "step_by_step_fix": result.step_by_step_fix,
            "explanation": result.explanation,
            "prevention_tips": result.prevention_tips,
            "related_docs": result.related_docs,
            "code_suggestion": result.code_suggestion,
            "confidence": result.confidence
        }

    except Exception as e:
        logger.error(f"Debug assistant failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_knowledge_tools_status():
    """
    Check the status of knowledge tools.

    Returns which features are available.
    """
    return {
        "status": "operational" if KNOWLEDGE_SERVICES_AVAILABLE else "unavailable",
        "services_available": KNOWLEDGE_SERVICES_AVAILABLE,
        "features": {
            "gap_analysis": KNOWLEDGE_SERVICES_AVAILABLE,
            "flashcards": KNOWLEDGE_SERVICES_AVAILABLE,
            "weekly_digest": KNOWLEDGE_SERVICES_AVAILABLE,
            "learning_path": KNOWLEDGE_SERVICES_AVAILABLE,
            "document_quality": KNOWLEDGE_SERVICES_AVAILABLE,
            "conversation_rag": KNOWLEDGE_SERVICES_AVAILABLE,
            "code_generator": KNOWLEDGE_SERVICES_AVAILABLE,
            "document_comparison": KNOWLEDGE_SERVICES_AVAILABLE,
            "eli5_explainer": KNOWLEDGE_SERVICES_AVAILABLE,
            "interview_prep": KNOWLEDGE_SERVICES_AVAILABLE,
            "debugging_assistant": KNOWLEDGE_SERVICES_AVAILABLE,
        },
        "endpoints": [
            "GET /knowledge/gaps",
            "POST /knowledge/flashcards/{doc_id}",
            "GET /knowledge/digest",
            "POST /knowledge/learning-path",
            "GET /knowledge/quality/{doc_id}",
            "POST /knowledge/chat",
            "POST /knowledge/generate-code",
            "POST /knowledge/compare",
            "POST /knowledge/eli5",
            "POST /knowledge/interview-prep",
            "POST /knowledge/debug",
        ]
    }
