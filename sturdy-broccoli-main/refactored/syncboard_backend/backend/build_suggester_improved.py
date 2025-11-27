"""
Improved AI-powered build suggestion system.

IMPROVEMENTS:
1. Minimum knowledge thresholds
2. Depth analysis (not just concept names)
3. Knowledge area detection (semantic grouping)
4. Actual content snippets sent to AI
5. Feasibility validation
"""

import os
import json
import logging
from typing import List, Dict, Optional
from collections import Counter

from .llm_providers import LLMProvider, OpenAIProvider
from .models import Cluster, DocumentMetadata, BuildSuggestion

logger = logging.getLogger(__name__)


# Minimum thresholds for viable build suggestions (relaxed for small KBs)
MIN_DOCUMENTS = 1
MIN_CONCEPTS = 3
MIN_CLUSTERS = 1  # At least one coherent knowledge area
MIN_CONTENT_LENGTH = 200  # Total characters


class ImprovedBuildSuggester:
    """Generate intelligent project suggestions with knowledge validation."""

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        """
        Initialize improved build suggester.

        Args:
            llm_provider: LLM provider to use (defaults to OpenAIProvider)
        """
        if llm_provider is None:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable required")
            self.provider = OpenAIProvider(api_key=api_key)
        else:
            self.provider = llm_provider

    async def analyze_knowledge_bank(
        self,
        clusters: Dict[int, Cluster],
        metadata: Dict[int, DocumentMetadata],
        documents: Dict[int, str],
        max_suggestions: int = 5,
        enable_quality_filter: bool = True,
        idea_seeds: List[Dict] = None
    ) -> List[BuildSuggestion]:
        """
        Analyze user's knowledge with depth validation (Tier 2: Enhanced with idea seeds).

        Args:
            clusters: User's content clusters
            metadata: Document metadata
            documents: Full document content
            max_suggestions: Number of suggestions to return
            enable_quality_filter: If True, filter out low-coverage suggestions
            idea_seeds: Pre-computed idea seeds from database (Tier 2 enhancement)

        Returns:
            List of BuildSuggestion objects (empty if insufficient knowledge)
        """

        # Validate minimum knowledge thresholds
        validation = self._validate_knowledge_depth(clusters, metadata, documents)

        if not validation["sufficient"]:
            logger.info(f"Insufficient knowledge: {validation['reason']}")
            return []

        # Build RICH knowledge summary with actual content
        knowledge_summary = self._build_rich_summary(clusters, metadata, documents)

        # Detect knowledge areas (semantic grouping)
        knowledge_areas = self._detect_knowledge_areas(clusters, metadata)

        try:
            # Generate suggestions with context (enhanced with idea seeds)
            suggestions_data = await self.provider.generate_build_suggestions_improved(
                knowledge_summary=knowledge_summary,
                knowledge_areas=knowledge_areas,
                validation_info=validation,
                max_suggestions=max_suggestions,
                enable_quality_filter=enable_quality_filter,
                idea_seeds=idea_seeds or []  # Pass idea seeds for enhancement
            )

            # Convert to BuildSuggestion objects
            suggestions = []
            for data in suggestions_data[:max_suggestions]:
                suggestions.append(BuildSuggestion(**data))

            logger.info(f"Generated {len(suggestions)} validated build suggestions")
            return suggestions

        except Exception as e:
            logger.error(f"Build suggestion failed: {e}")
            return []

    def _validate_knowledge_depth(
        self,
        clusters: Dict[int, Cluster],
        metadata: Dict[int, DocumentMetadata],
        documents: Dict[int, str]
    ) -> Dict:
        """
        Validate if user has ENOUGH knowledge to build something.

        Returns:
            {
                "sufficient": bool,
                "reason": str,
                "stats": {...}
            }
        """
        total_docs = len(documents)
        total_clusters = len(clusters)

        # Count total concepts
        all_concepts = []
        for meta in metadata.values():
            all_concepts.extend([c.name for c in meta.concepts])

        unique_concepts = len(set(all_concepts))

        # Calculate total content
        total_content_length = sum(len(doc) for doc in documents.values())

        # Check skill level distribution
        skill_levels = [meta.skill_level for meta in metadata.values()]
        skill_counter = Counter(skill_levels)
        has_advanced = skill_counter.get("advanced", 0) > 0
        has_intermediate = skill_counter.get("intermediate", 0) > 0

        # Validation checks
        reasons = []

        if total_docs < MIN_DOCUMENTS:
            reasons.append(f"Only {total_docs} documents (need {MIN_DOCUMENTS}+)")

        if unique_concepts < MIN_CONCEPTS:
            reasons.append(f"Only {unique_concepts} concepts (need {MIN_CONCEPTS}+)")

        if total_clusters < MIN_CLUSTERS:
            reasons.append(f"No coherent knowledge areas (need {MIN_CLUSTERS}+ cluster)")

        if total_content_length < MIN_CONTENT_LENGTH:
            reasons.append(f"Shallow content ({total_content_length} chars, need {MIN_CONTENT_LENGTH}+)")

        sufficient = len(reasons) == 0

        return {
            "sufficient": sufficient,
            "reason": "; ".join(reasons) if reasons else "Knowledge depth validated",
            "stats": {
                "total_documents": total_docs,
                "total_clusters": total_clusters,
                "unique_concepts": unique_concepts,
                "total_content_length": total_content_length,
                "has_advanced": has_advanced,
                "has_intermediate": has_intermediate,
                "skill_distribution": dict(skill_counter)
            }
        }

    def _build_rich_summary(
        self,
        clusters: Dict[int, Cluster],
        metadata: Dict[int, DocumentMetadata],
        documents: Dict[int, str]
    ) -> str:
        """
        Build RICH summary with actual content snippets.

        Not just concept names - include actual code, examples, quotes.
        """
        # Token budget management (GPT-5 has 272k input limit)
        MAX_SUMMARY_TOKENS = 150000  # Conservative limit for summary
        CHARS_PER_TOKEN = 4  # Rough estimate
        max_chars = MAX_SUMMARY_TOKENS * CHARS_PER_TOKEN

        lines = []
        lines.append("=== KNOWLEDGE BANK ANALYSIS ===\n")
        total_chars = 0

        for cluster_id, cluster in clusters.items():
            cluster_header = f"\n## CLUSTER {cluster_id}: {cluster.name}\n"
            cluster_header += f"   Documents: {cluster.doc_count} | Skill: {cluster.skill_level}\n"
            cluster_header += f"   Core Concepts: {', '.join(cluster.primary_concepts[:8])}\n"

            if total_chars + len(cluster_header) > max_chars:
                logger.warning(f"Truncated knowledge summary at cluster {cluster_id} (token budget)")
                break

            lines.append(cluster_header)
            total_chars += len(cluster_header)

            # Get docs in this cluster
            cluster_docs = [
                (did, meta) for did, meta in metadata.items()
                if meta.cluster_id == cluster_id
            ][:5]  # Top 5 docs

            lines.append(f"\n   ### Document Details:")
            for doc_id, meta in cluster_docs:
                doc_content = documents.get(doc_id, "")

                # Get actual content snippet (first 500 chars for better context)
                snippet = doc_content[:1000].strip()
                if len(doc_content) > 1000:
                    snippet += "..."

                # Get concept details
                concept_list = ", ".join([
                    f"{c.name} ({c.confidence:.2f})"
                    for c in meta.concepts[:5]
                ])

                doc_section = f"\n   [{meta.source_type}] Concepts: {concept_list}\n"
                doc_section += f"   Content: {snippet}\n"

                if total_chars + len(doc_section) > max_chars:
                    logger.warning(f"Truncated knowledge summary at doc {doc_id} (token budget)")
                    lines.append("\n   [... remaining documents truncated ...]")
                    break

                lines.append(doc_section)
                total_chars += len(doc_section)

            if total_chars >= max_chars:
                break

        summary = "\n".join(lines)
        logger.info(f"Built knowledge summary (~{len(summary)//CHARS_PER_TOKEN} tokens, {len(clusters)} clusters)")
        return summary

    def _detect_knowledge_areas(
        self,
        clusters: Dict[int, Cluster],
        metadata: Dict[int, DocumentMetadata]
    ) -> List[Dict]:
        """
        Detect coherent knowledge areas by grouping similar clusters.

        Example: Clusters about "Docker", "Kubernetes", "Containers"
                 -> Knowledge Area: "Container Orchestration"
        """
        # Group clusters by semantic similarity
        # This is simplified - a real implementation would use embeddings

        knowledge_areas = []

        for cluster_id, cluster in clusters.items():
            # Count documents and concepts in this area
            doc_count = cluster.doc_count

            # Get all concepts from docs in this cluster
            cluster_concepts = []
            for meta in metadata.values():
                if meta.cluster_id == cluster_id:
                    cluster_concepts.extend([c.name for c in meta.concepts])

            concept_freq = Counter(cluster_concepts)
            top_concepts = [name for name, _ in concept_freq.most_common(10)]

            knowledge_areas.append({
                "name": cluster.name,
                "cluster_id": cluster_id,
                "document_count": doc_count,
                "skill_level": cluster.skill_level,
                "core_concepts": top_concepts,
                "concept_frequency": dict(concept_freq.most_common(10))
            })

        return knowledge_areas
