"""
Market Validation Service (Phase 10).

Uses AI to validate market viability for project ideas by analyzing
competition, market size, and user's unique advantages.
"""

import logging
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class MarketValidation:
    """Market validation result."""
    market_size_estimate: str  # 'small', 'medium', 'large', 'niche'
    market_size_details: str
    competition_level: str  # 'low', 'medium', 'high', 'crowded'
    competitors: List[str]
    competition_analysis: str
    unique_advantage: str
    potential_revenue: str  # '$0-500/mo', '$500-2k/mo', etc.
    revenue_reasoning: str
    validation_sources: List[str]
    target_customer_profile: Dict
    go_to_market_strategy: List[str]
    risk_factors: List[str]
    recommendation: str  # 'proceed', 'pivot', 'abandon'
    reasoning: str
    confidence_score: float  # 0.0-1.0
    next_validation_steps: List[str]

    def to_dict(self) -> Dict:
        return asdict(self)


class MarketValidator:
    """Validates market viability for project ideas using AI analysis."""

    def __init__(self, llm_provider):
        """
        Initialize market validator.

        Args:
            llm_provider: LLM provider instance for AI analysis
        """
        self.provider = llm_provider

    async def validate_idea(
        self,
        project_title: str,
        project_description: str,
        target_market: str,
        user_knowledge_summary: str,
        web_search_results: Optional[List[Dict]] = None
    ) -> MarketValidation:
        """
        Validate market viability of a project idea.

        Args:
            project_title: Name of project
            project_description: What it does
            target_market: Who it's for
            user_knowledge_summary: User's expertise/knowledge
            web_search_results: Optional web search results for market research

        Returns:
            MarketValidation object with comprehensive analysis
        """

        # Build web search context
        search_context = ""
        if web_search_results:
            search_context = "\n\n## WEB RESEARCH FINDINGS:\n"
            for i, result in enumerate(web_search_results[:5], 1):
                search_context += f"\n{i}. {result.get('title', 'Result')}\n"
                search_context += f"   {result.get('snippet', '')}\n"
                search_context += f"   Source: {result.get('url', '')}\n"

        prompt = f"""Analyze the market viability of this project idea:

**PROJECT:** {project_title}
**DESCRIPTION:** {project_description}
**TARGET MARKET:** {target_market}

**USER'S EXPERTISE:**
{user_knowledge_summary[:3000]}

{search_context}

Provide a COMPREHENSIVE market validation analysis.

Return ONLY a JSON object with this EXACT structure:

{{
  "market_size_estimate": "small|medium|large|niche",
  "market_size_details": "Estimated 5,000-10,000 potential customers in UK",

  "competition_level": "low|medium|high|crowded",
  "competitors": [
    "Competitor 1 Name (URL if found)",
    "Competitor 2 Name (URL if found)",
    "Competitor 3 Name (URL if found)"
  ],
  "competition_analysis": "Detailed analysis of competitive landscape",

  "unique_advantage": "What makes this different/better based on user's specific knowledge and skills",

  "potential_revenue": "$0-500/mo|$500-2k/mo|$2k-10k/mo|$10k+/mo",
  "revenue_reasoning": "Why this revenue range is realistic",

  "validation_sources": [
    "Source 1: What information was used",
    "Source 2: What information was used"
  ],

  "target_customer_profile": {{
    "who": "Small business owners",
    "problem": "Specific problem they have",
    "current_solution": "How they solve it now",
    "willingness_to_pay": "high|medium|low"
  }},

  "go_to_market_strategy": [
    "1. Build MVP and test with 5 beta users",
    "2. Post on indie hacker forums",
    "3. Create landing page with email capture",
    "4. Launch on Product Hunt",
    "5. Target specific subreddits or communities"
  ],

  "risk_factors": [
    "Risk 1: Description and mitigation",
    "Risk 2: Description and mitigation"
  ],

  "recommendation": "proceed|pivot|abandon",
  "reasoning": "Detailed reasoning for recommendation based on all factors",

  "confidence_score": 0.75,

  "next_validation_steps": [
    "Talk to 10 potential customers",
    "Build landing page and measure signup rate",
    "Research pricing of competitors",
    "Validate technical feasibility"
  ]
}}

**ANALYSIS GUIDELINES:**
1. Be BRUTALLY HONEST - better to pivot early than waste time
2. Consider user's specific skills and advantages
3. Look for "unfair advantages" they have
4. Check if market is growing or shrinking
5. Consider effort vs potential reward
6. Factor in competition difficulty
7. Validate that target customers will actually pay
8. Consider user's constraints (time, budget)
"""

        try:
            response = await self.provider._call_openai(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a startup advisor and market analyst. Provide honest, data-driven market validation. Return only valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                model="gpt-4o",
                temperature=0.3,
                max_tokens=4000
            )

            # Parse response
            result = json.loads(response)

            return MarketValidation(
                market_size_estimate=result.get('market_size_estimate', 'unknown'),
                market_size_details=result.get('market_size_details', ''),
                competition_level=result.get('competition_level', 'unknown'),
                competitors=result.get('competitors', []),
                competition_analysis=result.get('competition_analysis', ''),
                unique_advantage=result.get('unique_advantage', 'Unable to analyze'),
                potential_revenue=result.get('potential_revenue', 'unknown'),
                revenue_reasoning=result.get('revenue_reasoning', ''),
                validation_sources=result.get('validation_sources', []),
                target_customer_profile=result.get('target_customer_profile', {}),
                go_to_market_strategy=result.get('go_to_market_strategy', []),
                risk_factors=result.get('risk_factors', []),
                recommendation=result.get('recommendation', 'research_needed'),
                reasoning=result.get('reasoning', ''),
                confidence_score=result.get('confidence_score', 0.0),
                next_validation_steps=result.get('next_validation_steps', [])
            )

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in market validation: {e}")
            return self._create_error_validation(f"Failed to parse analysis: {str(e)}")
        except Exception as e:
            logger.error(f"Market validation failed: {e}")
            return self._create_error_validation(str(e))

    def _create_error_validation(self, error_message: str) -> MarketValidation:
        """Create a validation object indicating an error occurred."""
        return MarketValidation(
            market_size_estimate="unknown",
            market_size_details="Analysis could not be completed",
            competition_level="unknown",
            competitors=[],
            competition_analysis="",
            unique_advantage="Unable to analyze",
            potential_revenue="unknown",
            revenue_reasoning="",
            validation_sources=[],
            target_customer_profile={},
            go_to_market_strategy=[],
            risk_factors=[f"Analysis error: {error_message}"],
            recommendation="research_needed",
            reasoning=f"Analysis failed: {error_message}",
            confidence_score=0.0,
            next_validation_steps=["Retry market validation", "Gather more information manually"]
        )

    async def quick_validation(
        self,
        project_title: str,
        project_description: str
    ) -> Dict:
        """
        Perform a quick market validation with minimal context.

        Returns a simplified analysis suitable for quick decision making.
        """
        prompt = f"""Quick market validation for:
**{project_title}**: {project_description}

Return a brief JSON analysis:
{{
  "viability_score": 0-100,
  "recommendation": "proceed|consider|avoid",
  "key_opportunity": "one sentence",
  "main_risk": "one sentence",
  "quick_tip": "one actionable suggestion"
}}
"""

        try:
            response = await self.provider._call_openai(
                messages=[
                    {"role": "system", "content": "Quick market analysis. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                model="gpt-4o-mini",
                temperature=0.3,
                max_tokens=500
            )

            return json.loads(response)

        except Exception as e:
            logger.error(f"Quick validation failed: {e}")
            return {
                "viability_score": 50,
                "recommendation": "consider",
                "key_opportunity": "Unable to analyze",
                "main_risk": "Analysis failed",
                "quick_tip": "Perform manual market research"
            }

    async def compare_ideas(
        self,
        ideas: List[Dict]
    ) -> Dict:
        """
        Compare multiple project ideas to help prioritize.

        Args:
            ideas: List of dicts with 'title' and 'description'

        Returns:
            Ranked comparison of ideas
        """
        if not ideas or len(ideas) < 2:
            return {"error": "Need at least 2 ideas to compare"}

        ideas_text = "\n".join([
            f"{i+1}. **{idea['title']}**: {idea['description']}"
            for i, idea in enumerate(ideas[:5])  # Max 5 ideas
        ])

        prompt = f"""Compare these project ideas for market potential:

{ideas_text}

Return a JSON analysis:
{{
  "ranking": [
    {{
      "position": 1,
      "title": "idea title",
      "score": 85,
      "strengths": ["strength 1", "strength 2"],
      "weaknesses": ["weakness 1"]
    }}
  ],
  "best_choice": "title of recommended idea",
  "reasoning": "why this is the best choice",
  "synergies": "any ways these ideas could complement each other"
}}
"""

        try:
            response = await self.provider._call_openai(
                messages=[
                    {"role": "system", "content": "Market analyst comparing project ideas. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                model="gpt-4o",
                temperature=0.3,
                max_tokens=2000
            )

            return json.loads(response)

        except Exception as e:
            logger.error(f"Compare ideas failed: {e}")
            return {"error": str(e)}
