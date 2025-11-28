"""
Content Generation Router for SyncBoard 3.0

Endpoints for industry-aware content generation from knowledge bases.

Endpoints:
- GET /content/industries - List available industries
- GET /content/templates/{industry} - Get templates for industry
- POST /content/generate - Generate content from knowledge
- POST /content/detect-industry - Auto-detect industry from content
- PUT /content/kb-industry - Set industry for knowledge base
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ..models import User
from ..dependencies import (
    get_current_user,
    get_repository,
    get_kb_documents,
    get_kb_metadata,
    get_kb_clusters,
    get_user_default_kb_id,
)
from ..repository_interface import KnowledgeBankRepository
from ..database import get_db
from ..industry_profiles import (
    Industry,
    get_all_industries,
    get_industry_profile,
    get_output_templates,
    detect_industry_from_content,
)
from ..content_generator import (
    ContentGenerator,
    ContentGenerationRequest,
    ContentGenerationResponse,
    get_content_generator,
)
from ..llm_providers import get_llm_provider

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(
    prefix="/content",
    tags=["content-generation"],
    responses={401: {"description": "Unauthorized"}},
)


# =============================================================================
# Request/Response Models
# =============================================================================

class IndustryDetectionRequest(BaseModel):
    """Request to detect industry from text."""
    text: str = Field(..., min_length=50, description="Text to analyze")


class IndustryDetectionResponse(BaseModel):
    """Response from industry detection."""
    detected_industry: str
    confidence: str  # "high", "medium", "low"
    available_templates: list


class SetKBIndustryRequest(BaseModel):
    """Request to set KB industry."""
    industry: str = Field(..., description="Industry ID")


# =============================================================================
# List Industries Endpoint
# =============================================================================

@router.get("/industries")
async def list_industries():
    """
    List all available industries with their descriptions.

    Returns:
        List of industries with id, name, description
    """
    return {
        "industries": get_all_industries(),
        "total": len(get_all_industries())
    }


# =============================================================================
# Get Templates Endpoint
# =============================================================================

@router.get("/templates/{industry}")
async def get_industry_templates(industry: str):
    """
    Get available output templates for an industry.

    Args:
        industry: Industry ID (e.g., "legal", "medical", "technology")

    Returns:
        List of templates with name, description, type
    """
    try:
        industry_enum = Industry(industry.lower())
    except ValueError:
        raise HTTPException(400, f"Unknown industry: {industry}. Use /content/industries to see available options.")

    profile = get_industry_profile(industry_enum)
    templates = get_output_templates(industry_enum)

    return {
        "industry": {
            "id": profile.id.value,
            "name": profile.name,
            "description": profile.description,
            "style": profile.generation_style,
            "citation_style": profile.citation_style,
        },
        "templates": templates,
        "categories": [
            {"name": c.name, "description": c.description}
            for c in profile.categories
        ],
        "skill_levels": profile.skill_levels
    }


# =============================================================================
# Detect Industry Endpoint
# =============================================================================

@router.post("/detect-industry")
@limiter.limit("20/minute")
async def detect_industry(
    request: Request,
    req: IndustryDetectionRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Auto-detect the most appropriate industry for content.

    Args:
        req: Text to analyze

    Returns:
        Detected industry with confidence and available templates
    """
    detected = detect_industry_from_content(req.text)
    templates = get_output_templates(detected)

    # Calculate confidence based on keyword matches
    profile = get_industry_profile(detected)
    text_lower = req.text.lower()
    matches = sum(1 for kw in profile.detection_keywords if kw in text_lower)

    if matches >= 5:
        confidence = "high"
    elif matches >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    return IndustryDetectionResponse(
        detected_industry=detected.value,
        confidence=confidence,
        available_templates=templates
    )


# =============================================================================
# Generate Content Endpoint
# =============================================================================

@router.post("/generate", response_model=ContentGenerationResponse)
@limiter.limit("10/minute")
async def generate_content(
    request: Request,
    req: ContentGenerationRequest,
    industry: Optional[str] = None,
    repo: KnowledgeBankRepository = Depends(get_repository),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate content from knowledge base using industry templates.

    Args:
        req: Generation request with template and options
        industry: Industry to use (optional, uses KB default if not specified)
        repo: Repository instance
        current_user: Authenticated user
        db: Database session

    Returns:
        Generated content with sections and citations
    """
    # Get user's KB
    kb_id = get_user_default_kb_id(current_user.username, db)

    # Get KB data from repository
    documents = await repo.get_documents_by_kb(kb_id)
    metadata = await repo.get_metadata_by_kb(kb_id)
    clusters = await repo.get_clusters_by_kb(kb_id)

    if not documents:
        raise HTTPException(400, "No documents in knowledge base. Upload content first.")

    # Determine industry
    if industry:
        try:
            industry_enum = Industry(industry.lower())
        except ValueError:
            raise HTTPException(400, f"Unknown industry: {industry}")
    else:
        # Use KB's configured industry or detect from content
        industry_enum = _get_kb_industry(kb_id, db) or Industry.GENERAL

    # Get LLM provider
    try:
        llm_provider = get_llm_provider()
    except Exception as e:
        logger.warning(f"LLM provider not available: {e}")
        llm_provider = None

    # Generate content
    generator = get_content_generator(llm_provider)

    try:
        result = await generator.generate(
            request=req,
            industry=industry_enum,
            documents=documents,
            metadata=metadata,
            clusters=clusters,
        )
        return result

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Content generation failed: {e}")
        raise HTTPException(500, f"Generation failed: {str(e)}")


# =============================================================================
# Set KB Industry Endpoint
# =============================================================================

@router.put("/kb-industry")
async def set_kb_industry(
    req: SetKBIndustryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Set the default industry for a knowledge base.

    This affects concept extraction categories and default templates.

    Args:
        req: Industry ID to set

    Returns:
        Updated KB settings
    """
    try:
        industry_enum = Industry(req.industry.lower())
    except ValueError:
        raise HTTPException(400, f"Unknown industry: {req.industry}")

    kb_id = get_user_default_kb_id(current_user.username, db)

    # Update KB industry in database
    from ..db_models import DBKnowledgeBase

    kb = db.query(DBKnowledgeBase).filter_by(id=kb_id).first()
    if not kb:
        raise HTTPException(404, "Knowledge base not found")

    # Store industry in settings JSON column
    if not kb.settings:
        kb.settings = {}
    kb.settings["industry"] = industry_enum.value

    db.commit()

    profile = get_industry_profile(industry_enum)

    logger.info(f"Set KB {kb_id} industry to {industry_enum.value} for user {current_user.username}")

    return {
        "message": "Industry updated",
        "knowledge_base_id": kb_id,
        "industry": {
            "id": profile.id.value,
            "name": profile.name,
            "description": profile.description
        }
    }


# =============================================================================
# Get KB Industry Endpoint
# =============================================================================

@router.get("/kb-industry")
async def get_kb_industry(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the current industry setting for user's knowledge base.

    Returns:
        Current industry configuration
    """
    kb_id = get_user_default_kb_id(current_user.username, db)
    industry = _get_kb_industry(kb_id, db)

    if industry:
        profile = get_industry_profile(industry)
        return {
            "knowledge_base_id": kb_id,
            "industry": {
                "id": profile.id.value,
                "name": profile.name,
                "description": profile.description
            },
            "templates": get_output_templates(industry),
            "categories": [c.name for c in profile.categories]
        }
    else:
        return {
            "knowledge_base_id": kb_id,
            "industry": None,
            "message": "No industry configured. Using general mode.",
            "available_industries": get_all_industries()
        }


# =============================================================================
# Quick Generate Endpoints (Convenience shortcuts)
# =============================================================================

@router.post("/generate/summary")
@limiter.limit("15/minute")
async def generate_summary(
    request: Request,
    topic: Optional[str] = None,
    cluster_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Quick endpoint to generate a summary from knowledge base."""
    req = ContentGenerationRequest(
        template_name="Summary",
        topic=topic,
        cluster_ids=[cluster_id] if cluster_id else None,
        target_length="medium"
    )

    # Reuse main generate endpoint logic
    return await generate_content(
        request=request,
        req=req,
        industry=None,
        current_user=current_user,
        db=db
    )


@router.post("/generate/analysis")
@limiter.limit("10/minute")
async def generate_analysis(
    request: Request,
    topic: Optional[str] = None,
    cluster_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Quick endpoint to generate an analysis from knowledge base."""
    req = ContentGenerationRequest(
        template_name="Analysis",
        topic=topic,
        cluster_ids=[cluster_id] if cluster_id else None,
        target_length="long"
    )

    return await generate_content(
        request=request,
        req=req,
        industry=None,
        current_user=current_user,
        db=db
    )


# =============================================================================
# Helper Functions
# =============================================================================

def _get_kb_industry(kb_id: str, db: Session) -> Optional[Industry]:
    """Get industry setting from KB."""
    from ..db_models import DBKnowledgeBase

    kb = db.query(DBKnowledgeBase).filter_by(id=kb_id).first()
    if kb and kb.settings and "industry" in kb.settings:
        try:
            return Industry(kb.settings["industry"])
        except ValueError:
            pass
    return None
