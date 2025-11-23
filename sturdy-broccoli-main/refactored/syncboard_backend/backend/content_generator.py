"""
Content Generation Engine for SyncBoard 3.0

This module provides industry-aware content generation from knowledge bases.
It uses the industry profiles to generate appropriately styled outputs.

Key Features:
    - Generate content FROM knowledge (not just query it)
    - Industry-specific templates and styling
    - Citation support
    - Multiple output formats
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from .industry_profiles import (
    Industry,
    IndustryProfile,
    OutputTemplate,
    get_industry_profile,
    get_template_by_name,
)
from .models import DocumentMetadata, Cluster

logger = logging.getLogger(__name__)


# =============================================================================
# Content Generation Request/Response Models
# =============================================================================

from pydantic import BaseModel, Field


class ContentGenerationRequest(BaseModel):
    """Request to generate content from knowledge base."""
    template_name: str = Field(..., description="Name of template to use")
    topic: Optional[str] = Field(None, description="Specific topic to focus on")
    cluster_ids: Optional[List[int]] = Field(None, description="Specific clusters to use as source")
    doc_ids: Optional[List[int]] = Field(None, description="Specific documents to use as source")
    additional_context: Optional[str] = Field(None, description="Additional context or instructions")
    target_length: Optional[str] = Field("medium", description="short, medium, or long")
    include_citations: bool = Field(True, description="Include source citations")


class ContentGenerationResponse(BaseModel):
    """Response from content generation."""
    content: str
    template_used: str
    industry: str
    sections: Dict[str, str]  # Structured sections if applicable
    citations: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any]
    generated_at: str


# =============================================================================
# Content Generator Class
# =============================================================================

class ContentGenerator:
    """
    Generates industry-appropriate content from knowledge bases.

    This is the core engine that transforms stored knowledge into
    useful outputs based on industry templates.
    """

    def __init__(self, llm_provider=None):
        """
        Initialize the content generator.

        Args:
            llm_provider: LLM provider for generation (OpenAI, Ollama, etc.)
        """
        self.llm_provider = llm_provider

    async def generate(
        self,
        request: ContentGenerationRequest,
        industry: Industry,
        documents: Dict[int, str],
        metadata: Dict[int, DocumentMetadata],
        clusters: Dict[int, Cluster],
    ) -> ContentGenerationResponse:
        """
        Generate content based on request and available knowledge.

        Args:
            request: Generation request with template and options
            industry: Target industry for styling
            documents: Available documents {doc_id: content}
            metadata: Document metadata {doc_id: metadata}
            clusters: Available clusters {cluster_id: cluster}

        Returns:
            ContentGenerationResponse with generated content
        """
        profile = get_industry_profile(industry)
        template = get_template_by_name(industry, request.template_name)

        if not template:
            # Fall back to first available template
            template = profile.output_templates[0] if profile.output_templates else None
            if not template:
                raise ValueError(f"No templates available for industry {industry}")

        # Gather source content
        source_content = self._gather_sources(
            request, documents, metadata, clusters
        )

        if not source_content["texts"]:
            raise ValueError("No source content found for generation")

        # Build the prompt
        prompt = self._build_prompt(
            template=template,
            profile=profile,
            source_content=source_content,
            request=request
        )

        # Generate content
        if self.llm_provider:
            generated = await self._generate_with_llm(prompt, profile)
        else:
            generated = self._generate_fallback(template, source_content)

        # Parse into sections if structured
        sections = self._parse_sections(generated, template)

        # Build citations if requested
        citations = None
        if request.include_citations:
            citations = self._build_citations(source_content, profile)

        return ContentGenerationResponse(
            content=generated,
            template_used=template.name,
            industry=profile.name,
            sections=sections,
            citations=citations,
            metadata={
                "source_docs": len(source_content["doc_ids"]),
                "source_clusters": len(source_content["cluster_ids"]),
                "target_length": request.target_length,
                "profile_style": profile.generation_style,
            },
            generated_at=datetime.utcnow().isoformat()
        )

    def _gather_sources(
        self,
        request: ContentGenerationRequest,
        documents: Dict[int, str],
        metadata: Dict[int, DocumentMetadata],
        clusters: Dict[int, Cluster],
    ) -> Dict[str, Any]:
        """Gather source content based on request filters."""
        source_doc_ids = set()
        source_cluster_ids = set()
        texts = []
        source_metadata = []

        # If specific docs requested
        if request.doc_ids:
            for doc_id in request.doc_ids:
                if doc_id in documents:
                    source_doc_ids.add(doc_id)
                    texts.append(documents[doc_id])
                    if doc_id in metadata:
                        source_metadata.append(metadata[doc_id])

        # If specific clusters requested
        if request.cluster_ids:
            for cluster_id in request.cluster_ids:
                if cluster_id in clusters:
                    source_cluster_ids.add(cluster_id)
                    cluster = clusters[cluster_id]
                    for doc_id in cluster.doc_ids:
                        if doc_id in documents and doc_id not in source_doc_ids:
                            source_doc_ids.add(doc_id)
                            texts.append(documents[doc_id])
                            if doc_id in metadata:
                                source_metadata.append(metadata[doc_id])

        # If no specific filter, use topic matching or all
        if not request.doc_ids and not request.cluster_ids:
            # Use all available (limited for performance)
            for doc_id, content in list(documents.items())[:20]:
                source_doc_ids.add(doc_id)
                texts.append(content[:5000])  # Limit per doc
                if doc_id in metadata:
                    source_metadata.append(metadata[doc_id])

        return {
            "doc_ids": list(source_doc_ids),
            "cluster_ids": list(source_cluster_ids),
            "texts": texts,
            "metadata": source_metadata
        }

    def _build_prompt(
        self,
        template: OutputTemplate,
        profile: IndustryProfile,
        source_content: Dict[str, Any],
        request: ContentGenerationRequest
    ) -> str:
        """Build the generation prompt."""
        # Combine source texts
        combined_sources = "\n\n---\n\n".join(
            text[:3000] for text in source_content["texts"][:10]
        )

        # Length guidance
        length_guidance = {
            "short": "Keep it concise, 200-400 words.",
            "medium": "Provide moderate detail, 500-1000 words.",
            "long": "Be comprehensive, 1000-2000 words."
        }.get(request.target_length, "")

        # Build sections guidance
        sections_list = ", ".join(template.structure.get("sections", []))

        prompt = f"""You are a {profile.name} expert creating content.
Style: {profile.generation_style}
{f"Citation style: {profile.citation_style}" if profile.citation_style else ""}

{template.prompt_prefix}

{f"Topic focus: {request.topic}" if request.topic else ""}
{f"Additional context: {request.additional_context}" if request.additional_context else ""}

Structure your response with these sections: {sections_list}

{length_guidance}

SOURCE KNOWLEDGE:
{combined_sources}

Generate the {template.name} now. Use the source knowledge to inform your response.
{"Include citations in [Source N] format." if request.include_citations else ""}
"""
        return prompt

    async def _generate_with_llm(self, prompt: str, profile: IndustryProfile) -> str:
        """Generate content using LLM provider."""
        messages = [
            {"role": "system", "content": f"You are an expert {profile.name} content creator. "
                                          f"Your style is {profile.generation_style}. "
                                          "Generate high-quality, accurate content based on the provided sources."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = await self.llm_provider.chat_completion(
                messages,
                temperature=0.7
            )
            return response
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise

    def _generate_fallback(
        self,
        template: OutputTemplate,
        source_content: Dict[str, Any]
    ) -> str:
        """Fallback generation when no LLM is available."""
        # Create a structured summary without LLM
        sections = template.structure.get("sections", ["content"])

        output_parts = [f"# {template.name}\n"]

        for section in sections[:3]:  # Limit sections
            output_parts.append(f"\n## {section.replace('_', ' ').title()}\n")

            # Add sample content from sources
            if source_content["texts"]:
                sample = source_content["texts"][0][:500]
                output_parts.append(f"{sample}...\n")
            else:
                output_parts.append("No source content available for this section.\n")

        output_parts.append("\n---\n*Note: Full content generation requires LLM provider configuration.*")

        return "\n".join(output_parts)

    def _parse_sections(
        self,
        generated: str,
        template: OutputTemplate
    ) -> Dict[str, str]:
        """Parse generated content into sections."""
        sections = {}
        expected_sections = template.structure.get("sections", [])

        # Try to find section headers
        current_section = "content"
        current_content = []

        for line in generated.split("\n"):
            # Check if line is a section header
            line_lower = line.lower().strip("#").strip()

            matched_section = None
            for section in expected_sections:
                if section.replace("_", " ") in line_lower:
                    matched_section = section
                    break

            if matched_section:
                # Save previous section
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = matched_section
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    def _build_citations(
        self,
        source_content: Dict[str, Any],
        profile: IndustryProfile
    ) -> List[Dict[str, Any]]:
        """Build citation list from source documents."""
        citations = []

        for i, meta in enumerate(source_content.get("metadata", [])):
            if meta:
                citation = {
                    "id": i + 1,
                    "doc_id": getattr(meta, "doc_id", None),
                    "title": getattr(meta, "title", f"Source {i + 1}"),
                    "source_type": getattr(meta, "source_type", "unknown"),
                    "source_url": getattr(meta, "source_url", None),
                    "ingested_at": getattr(meta, "ingested_at", None),
                }

                # Format based on citation style
                if profile.citation_style == "apa":
                    citation["formatted"] = self._format_apa(citation)
                elif profile.citation_style == "bluebook":
                    citation["formatted"] = self._format_bluebook(citation)
                else:
                    citation["formatted"] = f"[{i + 1}] {citation['title']}"

                citations.append(citation)

        return citations

    def _format_apa(self, citation: Dict) -> str:
        """Format citation in APA style."""
        title = citation.get("title", "Untitled")
        date = citation.get("ingested_at", "n.d.")[:10] if citation.get("ingested_at") else "n.d."
        url = citation.get("source_url", "")

        if url:
            return f"{title}. ({date}). Retrieved from {url}"
        return f"{title}. ({date})."

    def _format_bluebook(self, citation: Dict) -> str:
        """Format citation in Bluebook style (legal)."""
        title = citation.get("title", "Untitled")
        date = citation.get("ingested_at", "")[:10] if citation.get("ingested_at") else ""
        source = citation.get("source_type", "")

        return f"{title}, {source} ({date})"


# =============================================================================
# Factory Function
# =============================================================================

def get_content_generator(llm_provider=None) -> ContentGenerator:
    """Get a content generator instance."""
    return ContentGenerator(llm_provider=llm_provider)
