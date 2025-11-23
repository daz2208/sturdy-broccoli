"""
Industry Profiles System for SyncBoard 3.0

This module provides the abstraction layer for multi-industry support.
Adding a new industry is just configuration - no code rewrites needed.

Architecture:
    1. IndustryProfile - Defines taxonomy, terminology, output types
    2. IndustryRegistry - Central registry of all profiles
    3. get_industry_profile() - Fetch profile by ID

To add a new industry:
    1. Create profile dict with taxonomy, categories, templates
    2. Add to INDUSTRY_PROFILES dict
    3. Done - system auto-discovers and uses it
"""

from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field


# =============================================================================
# Industry Enum - All supported industries
# =============================================================================

class Industry(str, Enum):
    """Supported industry verticals."""
    GENERAL = "general"
    TECHNOLOGY = "technology"
    LEGAL = "legal"
    MEDICAL = "medical"
    BUSINESS = "business"
    CREATIVE = "creative"
    ACADEMIC = "academic"
    FINANCE = "finance"


# =============================================================================
# Industry Profile Model
# =============================================================================

class ConceptCategory(BaseModel):
    """A category for organizing concepts within an industry."""
    name: str
    description: str
    keywords: List[str] = []  # Keywords that suggest this category
    priority: int = 5  # 1-10, higher = more important


class OutputTemplate(BaseModel):
    """Template for generating industry-specific outputs."""
    name: str
    description: str
    template_type: str  # "summary", "report", "draft", "analysis", etc.
    structure: Dict[str, Any]  # Template structure/schema
    prompt_prefix: str  # Prefix for LLM prompts
    required_fields: List[str] = []


class IndustryProfile(BaseModel):
    """
    Complete profile for an industry vertical.

    This is the core abstraction - everything industry-specific
    is defined here, not scattered through the codebase.
    """
    id: Industry
    name: str
    description: str

    # Concept extraction settings
    categories: List[ConceptCategory]
    extraction_prompt_context: str  # Added to concept extraction prompts

    # Skill/complexity levels (industry-appropriate naming)
    skill_levels: Dict[str, str]  # internal_name -> display_name

    # Output templates
    output_templates: List[OutputTemplate]

    # Content generation settings
    generation_style: str  # "formal", "conversational", "technical", etc.
    citation_style: Optional[str] = None  # "apa", "bluebook", "ieee", etc.

    # Domain-specific terminology
    terminology: Dict[str, str] = {}  # term -> definition

    # Auto-detection keywords
    detection_keywords: List[str] = []  # Keywords that suggest this industry


# =============================================================================
# Industry Profile Definitions
# =============================================================================

INDUSTRY_PROFILES: Dict[Industry, IndustryProfile] = {

    # -------------------------------------------------------------------------
    # GENERAL - Default for unspecified use cases
    # -------------------------------------------------------------------------
    Industry.GENERAL: IndustryProfile(
        id=Industry.GENERAL,
        name="General",
        description="General-purpose knowledge management",
        categories=[
            ConceptCategory(name="topic", description="Main subject or theme", keywords=["about", "topic", "subject"], priority=8),
            ConceptCategory(name="concept", description="Key ideas and concepts", keywords=["concept", "idea", "principle"], priority=7),
            ConceptCategory(name="entity", description="People, places, organizations", keywords=["person", "company", "location"], priority=6),
            ConceptCategory(name="action", description="Processes and actions", keywords=["how to", "process", "method"], priority=5),
            ConceptCategory(name="reference", description="Sources and citations", keywords=["source", "reference", "citation"], priority=4),
        ],
        extraction_prompt_context="Extract key concepts, topics, and entities from this content.",
        skill_levels={
            "beginner": "Basic",
            "intermediate": "Intermediate",
            "advanced": "Advanced",
            "unknown": "Unspecified"
        },
        output_templates=[
            OutputTemplate(
                name="Summary",
                description="Concise summary of content",
                template_type="summary",
                structure={"sections": ["overview", "key_points", "conclusion"]},
                prompt_prefix="Create a clear, concise summary:",
                required_fields=["overview"]
            ),
            OutputTemplate(
                name="Analysis",
                description="Detailed analysis",
                template_type="analysis",
                structure={"sections": ["context", "analysis", "insights", "recommendations"]},
                prompt_prefix="Provide a thorough analysis:",
                required_fields=["analysis"]
            ),
        ],
        generation_style="conversational",
        detection_keywords=[]
    ),

    # -------------------------------------------------------------------------
    # TECHNOLOGY - Software, engineering, technical content
    # -------------------------------------------------------------------------
    Industry.TECHNOLOGY: IndustryProfile(
        id=Industry.TECHNOLOGY,
        name="Technology",
        description="Software development, engineering, and technical content",
        categories=[
            ConceptCategory(name="language", description="Programming languages", keywords=["python", "javascript", "java", "rust", "go", "typescript"], priority=9),
            ConceptCategory(name="framework", description="Frameworks and libraries", keywords=["react", "django", "fastapi", "express", "spring"], priority=9),
            ConceptCategory(name="tool", description="Development tools", keywords=["docker", "kubernetes", "git", "vscode", "jenkins"], priority=8),
            ConceptCategory(name="platform", description="Platforms and services", keywords=["aws", "azure", "gcp", "vercel", "heroku"], priority=8),
            ConceptCategory(name="database", description="Data storage systems", keywords=["postgres", "mongodb", "redis", "elasticsearch"], priority=7),
            ConceptCategory(name="architecture", description="System design patterns", keywords=["microservices", "serverless", "monolith", "api"], priority=7),
            ConceptCategory(name="methodology", description="Development practices", keywords=["agile", "scrum", "devops", "ci/cd", "tdd"], priority=6),
            ConceptCategory(name="concept", description="Technical concepts", keywords=["algorithm", "data structure", "design pattern"], priority=6),
        ],
        extraction_prompt_context="""Extract technical concepts from this software/engineering content.
Focus on: programming languages, frameworks, tools, platforms, architectural patterns, and methodologies.
Use lowercase for concept names. Be specific (e.g., "react hooks" not just "react").""",
        skill_levels={
            "beginner": "Junior",
            "intermediate": "Mid-Level",
            "advanced": "Senior/Expert",
            "unknown": "Unspecified"
        },
        output_templates=[
            OutputTemplate(
                name="Technical Summary",
                description="Technical documentation summary",
                template_type="summary",
                structure={"sections": ["overview", "technologies", "architecture", "key_points"]},
                prompt_prefix="Summarize this technical content for developers:",
                required_fields=["overview", "technologies"]
            ),
            OutputTemplate(
                name="Code Review",
                description="Code analysis and suggestions",
                template_type="analysis",
                structure={"sections": ["summary", "strengths", "issues", "suggestions", "security"]},
                prompt_prefix="Review this code and provide constructive feedback:",
                required_fields=["summary", "suggestions"]
            ),
            OutputTemplate(
                name="Architecture Doc",
                description="System architecture documentation",
                template_type="report",
                structure={"sections": ["overview", "components", "data_flow", "dependencies", "deployment"]},
                prompt_prefix="Document the system architecture based on:",
                required_fields=["overview", "components"]
            ),
            OutputTemplate(
                name="Tutorial",
                description="Step-by-step tutorial",
                template_type="draft",
                structure={"sections": ["introduction", "prerequisites", "steps", "troubleshooting", "next_steps"]},
                prompt_prefix="Create a tutorial based on this knowledge:",
                required_fields=["steps"]
            ),
        ],
        generation_style="technical",
        detection_keywords=["api", "code", "function", "class", "database", "server", "deploy", "git", "npm", "docker", "kubernetes"]
    ),

    # -------------------------------------------------------------------------
    # LEGAL - Law, contracts, compliance
    # -------------------------------------------------------------------------
    Industry.LEGAL: IndustryProfile(
        id=Industry.LEGAL,
        name="Legal",
        description="Legal documents, contracts, compliance, and case law",
        categories=[
            ConceptCategory(name="statute", description="Laws and regulations", keywords=["act", "law", "regulation", "statute", "code"], priority=10),
            ConceptCategory(name="case_law", description="Court decisions and precedents", keywords=["v.", "case", "ruling", "precedent", "holding"], priority=9),
            ConceptCategory(name="contract_term", description="Contract clauses and terms", keywords=["clause", "provision", "term", "agreement"], priority=9),
            ConceptCategory(name="legal_concept", description="Legal principles", keywords=["liability", "negligence", "breach", "jurisdiction"], priority=8),
            ConceptCategory(name="party", description="Parties and entities", keywords=["plaintiff", "defendant", "party", "corporation"], priority=7),
            ConceptCategory(name="remedy", description="Legal remedies", keywords=["damages", "injunction", "remedy", "relief"], priority=7),
            ConceptCategory(name="procedure", description="Legal procedures", keywords=["motion", "filing", "discovery", "hearing"], priority=6),
            ConceptCategory(name="jurisdiction", description="Courts and jurisdictions", keywords=["court", "federal", "state", "circuit"], priority=6),
        ],
        extraction_prompt_context="""Extract legal concepts from this document.
Focus on: statutes, case citations, contract terms, legal principles, parties, and procedures.
Preserve exact citations and case names. Note jurisdictional relevance.""",
        skill_levels={
            "beginner": "General Audience",
            "intermediate": "Law Student/Paralegal",
            "advanced": "Attorney/Expert",
            "unknown": "Unspecified"
        },
        output_templates=[
            OutputTemplate(
                name="Case Brief",
                description="Summary of legal case",
                template_type="summary",
                structure={"sections": ["citation", "facts", "issue", "holding", "reasoning", "disposition"]},
                prompt_prefix="Brief this case following standard format:",
                required_fields=["citation", "facts", "holding"]
            ),
            OutputTemplate(
                name="Contract Summary",
                description="Plain-language contract summary",
                template_type="summary",
                structure={"sections": ["parties", "purpose", "key_terms", "obligations", "risks", "termination"]},
                prompt_prefix="Summarize this contract in plain language:",
                required_fields=["parties", "key_terms"]
            ),
            OutputTemplate(
                name="Legal Memo",
                description="Legal memorandum",
                template_type="report",
                structure={"sections": ["question_presented", "brief_answer", "facts", "discussion", "conclusion"]},
                prompt_prefix="Draft a legal memorandum addressing:",
                required_fields=["question_presented", "discussion"]
            ),
            OutputTemplate(
                name="Compliance Checklist",
                description="Regulatory compliance checklist",
                template_type="analysis",
                structure={"sections": ["regulation", "requirements", "current_status", "gaps", "remediation"]},
                prompt_prefix="Create a compliance checklist based on:",
                required_fields=["requirements", "gaps"]
            ),
        ],
        generation_style="formal",
        citation_style="bluebook",
        terminology={
            "prima facie": "On first appearance; sufficient to establish a fact unless rebutted",
            "stare decisis": "The doctrine of following precedent",
            "mens rea": "Guilty mind; criminal intent",
            "habeas corpus": "A writ requiring a person to be brought before a court",
        },
        detection_keywords=["court", "plaintiff", "defendant", "contract", "agreement", "liability", "statute", "regulation", "legal", "attorney", "jurisdiction"]
    ),

    # -------------------------------------------------------------------------
    # MEDICAL - Healthcare, clinical, research
    # -------------------------------------------------------------------------
    Industry.MEDICAL: IndustryProfile(
        id=Industry.MEDICAL,
        name="Medical/Healthcare",
        description="Clinical documentation, medical research, and healthcare content",
        categories=[
            ConceptCategory(name="condition", description="Diseases and conditions", keywords=["disease", "syndrome", "disorder", "condition"], priority=10),
            ConceptCategory(name="treatment", description="Treatments and interventions", keywords=["treatment", "therapy", "procedure", "surgery"], priority=9),
            ConceptCategory(name="medication", description="Drugs and pharmaceuticals", keywords=["drug", "medication", "dosage", "prescription"], priority=9),
            ConceptCategory(name="anatomy", description="Body systems and structures", keywords=["organ", "system", "tissue", "cell"], priority=8),
            ConceptCategory(name="symptom", description="Signs and symptoms", keywords=["symptom", "sign", "presentation", "finding"], priority=8),
            ConceptCategory(name="diagnostic", description="Tests and diagnostics", keywords=["test", "scan", "lab", "imaging", "diagnosis"], priority=7),
            ConceptCategory(name="research", description="Clinical research", keywords=["study", "trial", "research", "evidence"], priority=7),
            ConceptCategory(name="guideline", description="Clinical guidelines", keywords=["guideline", "protocol", "standard", "recommendation"], priority=6),
        ],
        extraction_prompt_context="""Extract medical/clinical concepts from this content.
Focus on: conditions, treatments, medications, anatomy, symptoms, and diagnostic procedures.
Use standard medical terminology. Note evidence levels where applicable.""",
        skill_levels={
            "beginner": "Patient Education",
            "intermediate": "Healthcare Professional",
            "advanced": "Specialist/Researcher",
            "unknown": "Unspecified"
        },
        output_templates=[
            OutputTemplate(
                name="Patient Summary",
                description="Patient-friendly explanation",
                template_type="summary",
                structure={"sections": ["condition", "what_it_means", "treatment_options", "what_to_expect", "questions_to_ask"]},
                prompt_prefix="Explain this in patient-friendly language:",
                required_fields=["condition", "what_it_means"]
            ),
            OutputTemplate(
                name="Clinical Summary",
                description="Clinical documentation summary",
                template_type="summary",
                structure={"sections": ["chief_complaint", "history", "findings", "assessment", "plan"]},
                prompt_prefix="Summarize for clinical documentation:",
                required_fields=["assessment", "plan"]
            ),
            OutputTemplate(
                name="Research Summary",
                description="Research paper summary",
                template_type="analysis",
                structure={"sections": ["objective", "methods", "results", "conclusions", "limitations", "clinical_implications"]},
                prompt_prefix="Summarize this research for clinical application:",
                required_fields=["objective", "results", "conclusions"]
            ),
            OutputTemplate(
                name="Treatment Protocol",
                description="Treatment protocol outline",
                template_type="report",
                structure={"sections": ["indication", "contraindications", "dosing", "monitoring", "adverse_effects", "patient_education"]},
                prompt_prefix="Outline the treatment protocol for:",
                required_fields=["indication", "dosing"]
            ),
        ],
        generation_style="formal",
        citation_style="apa",
        terminology={
            "etiology": "The cause or origin of a disease",
            "prognosis": "The likely course and outcome of a disease",
            "contraindication": "A reason that makes a treatment inadvisable",
            "differential diagnosis": "List of possible conditions that could explain symptoms",
        },
        detection_keywords=["patient", "diagnosis", "treatment", "symptom", "clinical", "medical", "hospital", "doctor", "prescription", "therapy", "disease"]
    ),

    # -------------------------------------------------------------------------
    # BUSINESS - Strategy, operations, management
    # -------------------------------------------------------------------------
    Industry.BUSINESS: IndustryProfile(
        id=Industry.BUSINESS,
        name="Business",
        description="Business strategy, operations, management, and entrepreneurship",
        categories=[
            ConceptCategory(name="strategy", description="Business strategies", keywords=["strategy", "competitive", "market", "growth"], priority=9),
            ConceptCategory(name="metric", description="KPIs and metrics", keywords=["kpi", "metric", "roi", "revenue", "margin"], priority=9),
            ConceptCategory(name="process", description="Business processes", keywords=["process", "workflow", "operation", "procedure"], priority=8),
            ConceptCategory(name="market", description="Markets and segments", keywords=["market", "segment", "customer", "audience"], priority=8),
            ConceptCategory(name="finance", description="Financial concepts", keywords=["revenue", "cost", "profit", "investment", "funding"], priority=8),
            ConceptCategory(name="organization", description="Organizational concepts", keywords=["team", "department", "structure", "culture"], priority=7),
            ConceptCategory(name="product", description="Products and services", keywords=["product", "service", "feature", "offering"], priority=7),
            ConceptCategory(name="risk", description="Business risks", keywords=["risk", "threat", "challenge", "obstacle"], priority=6),
        ],
        extraction_prompt_context="""Extract business concepts from this content.
Focus on: strategies, metrics, processes, markets, financial terms, and organizational elements.
Identify actionable insights and quantifiable metrics where present.""",
        skill_levels={
            "beginner": "Entry Level",
            "intermediate": "Manager",
            "advanced": "Executive/Consultant",
            "unknown": "Unspecified"
        },
        output_templates=[
            OutputTemplate(
                name="Executive Summary",
                description="Brief for executives",
                template_type="summary",
                structure={"sections": ["situation", "key_findings", "recommendations", "next_steps"]},
                prompt_prefix="Create an executive summary:",
                required_fields=["key_findings", "recommendations"]
            ),
            OutputTemplate(
                name="Business Case",
                description="Business case document",
                template_type="report",
                structure={"sections": ["problem", "solution", "benefits", "costs", "risks", "timeline", "roi"]},
                prompt_prefix="Build a business case for:",
                required_fields=["problem", "solution", "roi"]
            ),
            OutputTemplate(
                name="Market Analysis",
                description="Market analysis report",
                template_type="analysis",
                structure={"sections": ["market_overview", "size_growth", "segments", "competitors", "trends", "opportunities"]},
                prompt_prefix="Analyze the market based on:",
                required_fields=["market_overview", "opportunities"]
            ),
            OutputTemplate(
                name="Strategy Brief",
                description="Strategic recommendation",
                template_type="draft",
                structure={"sections": ["objective", "current_state", "target_state", "strategy", "tactics", "resources", "timeline"]},
                prompt_prefix="Develop a strategic brief for:",
                required_fields=["objective", "strategy"]
            ),
        ],
        generation_style="professional",
        detection_keywords=["business", "company", "market", "revenue", "customer", "strategy", "growth", "investment", "stakeholder", "roi"]
    ),

    # -------------------------------------------------------------------------
    # CREATIVE - Content creation, marketing, copywriting
    # -------------------------------------------------------------------------
    Industry.CREATIVE: IndustryProfile(
        id=Industry.CREATIVE,
        name="Creative/Content",
        description="Content creation, marketing, copywriting, and creative writing",
        categories=[
            ConceptCategory(name="topic", description="Content topics", keywords=["topic", "subject", "theme", "niche"], priority=9),
            ConceptCategory(name="audience", description="Target audiences", keywords=["audience", "reader", "viewer", "demographic"], priority=9),
            ConceptCategory(name="format", description="Content formats", keywords=["blog", "video", "podcast", "social", "email"], priority=8),
            ConceptCategory(name="channel", description="Distribution channels", keywords=["youtube", "instagram", "linkedin", "tiktok", "newsletter"], priority=8),
            ConceptCategory(name="style", description="Writing styles", keywords=["tone", "voice", "style", "brand"], priority=7),
            ConceptCategory(name="hook", description="Hooks and angles", keywords=["hook", "headline", "angle", "story"], priority=7),
            ConceptCategory(name="cta", description="Calls to action", keywords=["cta", "conversion", "action", "click"], priority=6),
            ConceptCategory(name="seo", description="SEO elements", keywords=["keyword", "seo", "search", "ranking"], priority=6),
        ],
        extraction_prompt_context="""Extract content creation concepts from this material.
Focus on: topics, target audiences, content formats, channels, style elements, and engagement hooks.
Identify what makes content compelling and shareable.""",
        skill_levels={
            "beginner": "Casual Creator",
            "intermediate": "Professional Creator",
            "advanced": "Expert/Strategist",
            "unknown": "Unspecified"
        },
        output_templates=[
            OutputTemplate(
                name="Blog Post",
                description="Blog article draft",
                template_type="draft",
                structure={"sections": ["headline", "hook", "body", "examples", "conclusion", "cta"]},
                prompt_prefix="Write an engaging blog post about:",
                required_fields=["headline", "body"]
            ),
            OutputTemplate(
                name="Social Posts",
                description="Social media content",
                template_type="draft",
                structure={"sections": ["twitter", "linkedin", "instagram", "hooks", "hashtags"]},
                prompt_prefix="Create social media posts for:",
                required_fields=["twitter", "linkedin"]
            ),
            OutputTemplate(
                name="Content Brief",
                description="Content creation brief",
                template_type="report",
                structure={"sections": ["objective", "audience", "key_messages", "tone", "keywords", "structure", "cta"]},
                prompt_prefix="Create a content brief for:",
                required_fields=["objective", "audience", "key_messages"]
            ),
            OutputTemplate(
                name="Email Sequence",
                description="Email marketing sequence",
                template_type="draft",
                structure={"sections": ["subject_lines", "email_1", "email_2", "email_3", "ctas"]},
                prompt_prefix="Write an email sequence about:",
                required_fields=["subject_lines", "email_1"]
            ),
            OutputTemplate(
                name="Video Script",
                description="Video content script",
                template_type="draft",
                structure={"sections": ["hook", "intro", "main_points", "examples", "conclusion", "cta"]},
                prompt_prefix="Write a video script for:",
                required_fields=["hook", "main_points"]
            ),
        ],
        generation_style="conversational",
        detection_keywords=["content", "blog", "post", "video", "social", "marketing", "audience", "engagement", "viral", "brand", "copy"]
    ),

    # -------------------------------------------------------------------------
    # ACADEMIC - Research, education, scholarly work
    # -------------------------------------------------------------------------
    Industry.ACADEMIC: IndustryProfile(
        id=Industry.ACADEMIC,
        name="Academic",
        description="Academic research, education, and scholarly content",
        categories=[
            ConceptCategory(name="theory", description="Theories and frameworks", keywords=["theory", "framework", "model", "hypothesis"], priority=9),
            ConceptCategory(name="methodology", description="Research methods", keywords=["method", "methodology", "approach", "design"], priority=9),
            ConceptCategory(name="finding", description="Research findings", keywords=["finding", "result", "evidence", "data"], priority=8),
            ConceptCategory(name="author", description="Researchers and authors", keywords=["author", "researcher", "scholar"], priority=7),
            ConceptCategory(name="publication", description="Publications", keywords=["journal", "paper", "study", "publication"], priority=7),
            ConceptCategory(name="concept", description="Academic concepts", keywords=["concept", "term", "definition"], priority=7),
            ConceptCategory(name="field", description="Academic fields", keywords=["field", "discipline", "domain", "area"], priority=6),
            ConceptCategory(name="citation", description="Citations and references", keywords=["citation", "reference", "source"], priority=6),
        ],
        extraction_prompt_context="""Extract academic concepts from this scholarly content.
Focus on: theories, methodologies, key findings, influential authors, and citations.
Note the academic field and level of evidence where applicable.""",
        skill_levels={
            "beginner": "Undergraduate",
            "intermediate": "Graduate",
            "advanced": "Researcher/Faculty",
            "unknown": "Unspecified"
        },
        output_templates=[
            OutputTemplate(
                name="Literature Review",
                description="Literature review section",
                template_type="analysis",
                structure={"sections": ["introduction", "themes", "synthesis", "gaps", "conclusion"]},
                prompt_prefix="Write a literature review covering:",
                required_fields=["themes", "synthesis"]
            ),
            OutputTemplate(
                name="Research Summary",
                description="Paper summary",
                template_type="summary",
                structure={"sections": ["citation", "objective", "methods", "findings", "implications", "limitations"]},
                prompt_prefix="Summarize this research paper:",
                required_fields=["objective", "findings"]
            ),
            OutputTemplate(
                name="Study Guide",
                description="Educational study guide",
                template_type="draft",
                structure={"sections": ["objectives", "key_concepts", "summary", "review_questions", "further_reading"]},
                prompt_prefix="Create a study guide for:",
                required_fields=["key_concepts", "summary"]
            ),
            OutputTemplate(
                name="Annotated Bibliography",
                description="Annotated bibliography entry",
                template_type="summary",
                structure={"sections": ["citation", "summary", "evaluation", "relevance"]},
                prompt_prefix="Create annotated bibliography entries for:",
                required_fields=["citation", "summary"]
            ),
        ],
        generation_style="formal",
        citation_style="apa",
        detection_keywords=["research", "study", "journal", "academic", "university", "thesis", "hypothesis", "methodology", "literature", "scholar"]
    ),

    # -------------------------------------------------------------------------
    # FINANCE - Financial analysis, investment, accounting
    # -------------------------------------------------------------------------
    Industry.FINANCE: IndustryProfile(
        id=Industry.FINANCE,
        name="Finance",
        description="Financial analysis, investment, accounting, and economics",
        categories=[
            ConceptCategory(name="metric", description="Financial metrics", keywords=["ratio", "margin", "return", "yield", "eps"], priority=10),
            ConceptCategory(name="instrument", description="Financial instruments", keywords=["stock", "bond", "option", "derivative", "etf"], priority=9),
            ConceptCategory(name="market", description="Markets and exchanges", keywords=["market", "exchange", "index", "nasdaq", "nyse"], priority=8),
            ConceptCategory(name="analysis", description="Analysis types", keywords=["fundamental", "technical", "valuation", "dcf"], priority=8),
            ConceptCategory(name="risk", description="Risk concepts", keywords=["risk", "volatility", "beta", "hedge", "exposure"], priority=8),
            ConceptCategory(name="accounting", description="Accounting concepts", keywords=["revenue", "expense", "asset", "liability", "equity"], priority=7),
            ConceptCategory(name="regulation", description="Financial regulations", keywords=["sec", "regulation", "compliance", "gaap", "ifrs"], priority=7),
            ConceptCategory(name="strategy", description="Investment strategies", keywords=["strategy", "portfolio", "diversification", "allocation"], priority=7),
        ],
        extraction_prompt_context="""Extract financial concepts from this content.
Focus on: metrics, financial instruments, markets, analysis methods, and risk factors.
Preserve exact figures and ratios. Note time periods and currencies.""",
        skill_levels={
            "beginner": "Retail Investor",
            "intermediate": "Financial Professional",
            "advanced": "Analyst/Expert",
            "unknown": "Unspecified"
        },
        output_templates=[
            OutputTemplate(
                name="Investment Summary",
                description="Investment thesis summary",
                template_type="summary",
                structure={"sections": ["ticker", "thesis", "financials", "risks", "catalysts", "recommendation"]},
                prompt_prefix="Summarize the investment case for:",
                required_fields=["thesis", "financials"]
            ),
            OutputTemplate(
                name="Financial Analysis",
                description="Financial statement analysis",
                template_type="analysis",
                structure={"sections": ["overview", "income_analysis", "balance_sheet", "cash_flow", "ratios", "trends"]},
                prompt_prefix="Analyze the financials:",
                required_fields=["overview", "ratios"]
            ),
            OutputTemplate(
                name="Risk Assessment",
                description="Risk analysis report",
                template_type="report",
                structure={"sections": ["risk_overview", "market_risks", "credit_risks", "operational_risks", "mitigation", "recommendations"]},
                prompt_prefix="Assess the risks for:",
                required_fields=["risk_overview", "recommendations"]
            ),
            OutputTemplate(
                name="Market Commentary",
                description="Market update commentary",
                template_type="draft",
                structure={"sections": ["summary", "market_moves", "drivers", "sectors", "outlook"]},
                prompt_prefix="Write market commentary covering:",
                required_fields=["summary", "outlook"]
            ),
        ],
        generation_style="professional",
        terminology={
            "P/E ratio": "Price to earnings ratio - stock price divided by earnings per share",
            "EBITDA": "Earnings before interest, taxes, depreciation, and amortization",
            "DCF": "Discounted cash flow - valuation method based on future cash flows",
            "Beta": "Measure of a stock's volatility relative to the market",
        },
        detection_keywords=["stock", "investment", "portfolio", "market", "revenue", "profit", "valuation", "financial", "trading", "dividend"]
    ),
}


# =============================================================================
# Registry Functions
# =============================================================================

def get_industry_profile(industry: Industry) -> IndustryProfile:
    """Get the profile for a specific industry."""
    return INDUSTRY_PROFILES.get(industry, INDUSTRY_PROFILES[Industry.GENERAL])


def get_all_industries() -> List[Dict[str, str]]:
    """Get list of all available industries with names and descriptions."""
    return [
        {
            "id": profile.id.value,
            "name": profile.name,
            "description": profile.description
        }
        for profile in INDUSTRY_PROFILES.values()
    ]


def detect_industry_from_content(content: str) -> Industry:
    """
    Auto-detect the most likely industry based on content keywords.

    Args:
        content: Text content to analyze

    Returns:
        Best matching Industry, or GENERAL if no strong match
    """
    content_lower = content.lower()
    scores: Dict[Industry, int] = {}

    for industry, profile in INDUSTRY_PROFILES.items():
        if industry == Industry.GENERAL:
            continue  # Skip general, it's the fallback

        score = sum(
            1 for keyword in profile.detection_keywords
            if keyword in content_lower
        )
        if score > 0:
            scores[industry] = score

    if not scores:
        return Industry.GENERAL

    # Return industry with highest score
    return max(scores, key=scores.get)


def get_output_templates(industry: Industry) -> List[Dict[str, str]]:
    """Get available output templates for an industry."""
    profile = get_industry_profile(industry)
    return [
        {
            "name": t.name,
            "description": t.description,
            "type": t.template_type
        }
        for t in profile.output_templates
    ]


def get_template_by_name(industry: Industry, template_name: str) -> Optional[OutputTemplate]:
    """Get a specific output template by name."""
    profile = get_industry_profile(industry)
    for template in profile.output_templates:
        if template.name.lower() == template_name.lower():
            return template
    return None
