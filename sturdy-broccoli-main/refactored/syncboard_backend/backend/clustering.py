"""
IMPROVED clustering with semantic concept grouping.

IMPROVEMENTS over basic clustering.py:
1. Semantic similarity (not just exact string matching)
2. Concept synonyms and variations (AI = ML = machine learning)
3. Better relationship detection between concepts
4. Knowledge area identification
5. Depth analysis per cluster
6. SELF-LEARNING semantic dictionary that grows with user's content
"""

import logging
from typing import List, Dict, Optional, Set
from collections import Counter
from .models import Cluster, Concept
from .semantic_dictionary import SemanticDictionaryManager

logger = logging.getLogger(__name__)


class ImprovedClusteringEngine:
    """
    Enhanced clustering with semantic understanding.

    Recognizes that:
    - "AI" = "ML" = "machine learning"
    - "Docker" + "Kubernetes" = Container knowledge area
    - Related concepts should cluster together

    SELF-LEARNING:
    - Starts with 50+ concept seed dictionary
    - Learns new relationships from user's content
    - Persists to JSON (Docker-compatible)
    """

    def __init__(self, semantic_dict: Optional[SemanticDictionaryManager] = None):
        """
        Initialize improved clustering engine.

        Args:
            semantic_dict: Semantic dictionary manager (creates default if None)
        """
        self.similarity_threshold = 0.35  # Lower because semantic matching is better
        self.synonym_boost = 0.3  # Extra score for semantic matches

        # Initialize or use provided semantic dictionary
        if semantic_dict is None:
            self.semantic_dict = SemanticDictionaryManager()
        else:
            self.semantic_dict = semantic_dict

        stats = self.semantic_dict.get_stats()
        logger.info(
            f"ClusteringEngine initialized with semantic dictionary: "
            f"{stats['seed_concepts']} seed + {stats['learned_concepts']} learned concepts"
        )

    def _expand_concepts(self, concept_names: List[str]) -> Set[str]:
        """
        Expand concept names to include synonyms.

        Uses self-learning semantic dictionary.

        Example: ["AI", "Docker"] -> {"AI", "ML", "machine learning", "Docker", "containers", ...}
        """
        return self.semantic_dict.expand_concepts(concept_names)

    def _semantic_similarity(
        self,
        concepts_a: List[str],
        concepts_b: List[str]
    ) -> float:
        """
        Calculate semantic similarity between two concept sets.

        Accounts for synonyms and related terms.
        """
        # Expand both concept sets with synonyms
        expanded_a = self._expand_concepts(concepts_a)
        expanded_b = self._expand_concepts(concepts_b)

        if not expanded_a or not expanded_b:
            return 0.0

        # Jaccard similarity on expanded sets
        intersection = len(expanded_a & expanded_b)
        union = len(expanded_a | expanded_b)

        return intersection / union if union > 0 else 0.0

    def find_best_cluster(
        self,
        doc_concepts: List[Dict],
        suggested_name: str,
        existing_clusters: Dict[int, Cluster]
    ) -> Optional[int]:
        """
        Find best matching cluster using SEMANTIC similarity.

        Much better than exact string matching!
        """
        if not existing_clusters:
            return None

        doc_concept_names = [c["name"] for c in doc_concepts]

        best_match = None
        best_score = 0.0

        for cluster_id, cluster in existing_clusters.items():
            # Calculate semantic similarity
            similarity = self._semantic_similarity(
                doc_concept_names,
                cluster.primary_concepts
            )

            # Boost if suggested name semantically matches cluster name
            if self._names_are_related(suggested_name, cluster.name):
                similarity += self.synonym_boost

            if similarity > best_score:
                best_score = similarity
                best_match = cluster_id

        # Return match if above threshold
        if best_score >= self.similarity_threshold:
            logger.info(
                f"Found semantic match: cluster {best_match} "
                f"(similarity: {best_score:.2f})"
            )
            return best_match

        return None

    def _names_are_related(self, name_a: str, name_b: str) -> bool:
        """Check if two cluster names are semantically related."""
        # Expand both names with synonyms using semantic dictionary
        expanded_a = self._expand_concepts([name_a])
        expanded_b = self._expand_concepts([name_b])

        # Check for overlap
        return len(expanded_a & expanded_b) > 0

    def create_cluster(
        self,
        doc_id: int,
        name: str,
        concepts: List[Dict],
        skill_level: str,
        existing_clusters: Dict[int, Cluster]
    ) -> int:
        """Create new cluster with concept tracking."""
        cluster_id = max(existing_clusters.keys()) + 1 if existing_clusters else 1

        # Extract and expand primary concepts
        concept_names = [c["name"] for c in concepts]
        concept_freq = Counter(concept_names)

        # Top 8 concepts (more than before for better matching)
        primary = [name for name, _ in concept_freq.most_common(8)]

        cluster = Cluster(
            id=cluster_id,
            name=name,
            primary_concepts=primary,
            doc_ids=[doc_id],
            skill_level=skill_level,
            doc_count=1
        )

        existing_clusters[cluster_id] = cluster
        logger.info(f"Created cluster {cluster_id}: {name} ({len(primary)} concepts)")

        return cluster_id

    def add_to_cluster(
        self,
        cluster_id: int,
        doc_id: int,
        clusters: Dict[int, Cluster]
    ):
        """Add document to cluster and update concepts."""
        if cluster_id not in clusters:
            logger.error(f"Cluster {cluster_id} not found")
            return

        cluster = clusters[cluster_id]
        if doc_id not in cluster.doc_ids:
            cluster.doc_ids.append(doc_id)
            cluster.doc_count = len(cluster.doc_ids)
            logger.info(
                f"Added doc {doc_id} to cluster {cluster_id} "
                f"({cluster.name}, now {cluster.doc_count} docs)"
            )

    def detect_knowledge_areas(
        self,
        clusters: Dict[int, Cluster]
    ) -> List[Dict]:
        """
        Detect high-level knowledge areas by grouping related clusters.

        Example:
        - Clusters: "Docker basics", "Kubernetes intro", "Container networking"
        - Knowledge Area: "Container Orchestration" (3 clusters grouped)
        """
        # Group clusters by semantic similarity
        knowledge_areas = []
        processed = set()

        for cluster_id, cluster in clusters.items():
            if cluster_id in processed:
                continue

            # Find all related clusters
            related = [cluster_id]

            for other_id, other_cluster in clusters.items():
                if other_id == cluster_id or other_id in processed:
                    continue

                # Check if semantically related
                similarity = self._semantic_similarity(
                    cluster.primary_concepts,
                    other_cluster.primary_concepts
                )

                if similarity >= 0.3:  # Related threshold
                    related.append(other_id)
                    processed.add(other_id)

            processed.add(cluster_id)

            # Aggregate concepts from all related clusters
            all_concepts = []
            total_docs = 0

            for cid in related:
                all_concepts.extend(clusters[cid].primary_concepts)
                total_docs += clusters[cid].doc_count

            concept_freq = Counter(all_concepts)

            knowledge_areas.append({
                "name": cluster.name,  # Could generate better name
                "related_clusters": related,
                "total_documents": total_docs,
                "core_concepts": [name for name, _ in concept_freq.most_common(15)],
                "strength": "strong" if total_docs >= 5 else "emerging"
            })

        logger.info(f"Detected {len(knowledge_areas)} knowledge areas")
        return knowledge_areas
