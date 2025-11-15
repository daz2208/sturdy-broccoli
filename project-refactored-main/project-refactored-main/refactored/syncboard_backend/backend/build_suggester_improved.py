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


# Minimum thresholds for viable build suggestions
MIN_DOCUMENTS = 5
MIN_CONCEPTS = 10
MIN_CLUSTERS = 1  # At least one coherent knowledge area
MIN_CONTENT_LENGTH = 2000  # Total characters


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
        max_suggestions: int = 5
    ) -> List[BuildSuggestion]:
        """
        Analyze user's knowledge with depth validation.

        Args:
            clusters: User's content clusters
            metadata: Document metadata
            documents: Full document content
            max_suggestions: Number of suggestions to return

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
            # Generate suggestions with context
            suggestions_data = await self.provider.generate_build_suggestions_improved(
                knowledge_summary=knowledge_summary,
                knowledge_areas=knowledge_areas,
                validation_info=validation,
                max_suggestions=max_suggestions
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
        lines = []
        lines.append("=== KNOWLEDGE BANK ANALYSIS ===\n")

        for cluster_id, cluster in clusters.items():
            lines.append(f"\n## CLUSTER {cluster_id}: {cluster.name}")
            lines.append(f"   Documents: {cluster.doc_count} | Skill: {cluster.skill_level}")
            lines.append(f"   Core Concepts: {', '.join(cluster.primary_concepts[:8])}")

            # Get docs in this cluster
            cluster_docs = [
                (did, meta) for did, meta in metadata.items()
                if meta.cluster_id == cluster_id
            ][:5]  # Top 5 docs

            lines.append(f"\n   ### Document Details:")
            for doc_id, meta in cluster_docs:
                doc_content = documents.get(doc_id, "")

                # Get actual content snippet (first 300 chars)
                snippet = doc_content[:300].strip()
                if len(doc_content) > 300:
                    snippet += "..."

                # Get concept details
                concept_list = ", ".join([
                    f"{c.name} ({c.relevance:.2f})"
                    for c in meta.concepts[:5]
                ])

                lines.append(f"\n   [{meta.source_type}] Concepts: {concept_list}")
                lines.append(f"   Content: {snippet}")

        return "\n".join(lines)

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
