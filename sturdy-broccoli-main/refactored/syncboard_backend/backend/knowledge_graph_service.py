"""
Knowledge Graph Service for SyncBoard 3.0 Knowledge Bank.

Builds and queries a graph of document relationships based on:
- Shared concepts
- Common technologies
- Skill level proximity
- Cluster membership

Enables discovering related documents and knowledge pathways.
"""

import logging
from typing import List, Dict, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class DocumentNode:
    """A document in the knowledge graph."""
    doc_id: int
    internal_id: int
    filename: Optional[str]
    source_type: str
    concepts: List[str] = field(default_factory=list)
    tech_stack: List[str] = field(default_factory=list)
    skill_level: Optional[str] = None
    cluster_id: Optional[int] = None


@dataclass
class DocumentRelationship:
    """A relationship between two documents."""
    source_doc_id: int
    target_doc_id: int
    relationship_type: str  # 'shared_concept', 'shared_tech', 'same_cluster', 'skill_path'
    strength: float  # 0.0 to 1.0
    shared_items: List[str] = field(default_factory=list)


@dataclass
class KnowledgeGraphStats:
    """Statistics about the knowledge graph."""
    total_documents: int
    total_relationships: int
    unique_concepts: int
    unique_technologies: int
    avg_connections_per_doc: float


class KnowledgeGraphService:
    """Service for building and querying the knowledge graph."""

    def __init__(self):
        """Initialize the knowledge graph service."""
        self._nodes: Dict[int, DocumentNode] = {}
        self._relationships: List[DocumentRelationship] = []
        self._concept_index: Dict[str, Set[int]] = defaultdict(set)
        self._tech_index: Dict[str, Set[int]] = defaultdict(set)
        self._cluster_index: Dict[int, Set[int]] = defaultdict(set)

    def build_graph(
        self,
        db: Session,
        knowledge_base_id: str
    ) -> KnowledgeGraphStats:
        """
        Build the knowledge graph from document summaries.

        Args:
            db: Database session
            knowledge_base_id: Knowledge base ID

        Returns:
            KnowledgeGraphStats with graph statistics
        """
        from .db_models import DBDocument, DBDocumentSummary

        # Clear existing graph
        self._nodes.clear()
        self._relationships.clear()
        self._concept_index.clear()
        self._tech_index.clear()
        self._cluster_index.clear()

        # Load all documents with their summaries
        documents = db.query(DBDocument).filter(
            DBDocument.knowledge_base_id == knowledge_base_id
        ).all()

        for doc in documents:
            # Try to get document-level summary (level 3) first
            summary = db.query(DBDocumentSummary).filter(
                DBDocumentSummary.document_id == doc.id,
                DBDocumentSummary.summary_level == 3
            ).first()

            # If summaries exist, use them; otherwise fall back to concepts table
            if summary and summary.key_concepts:
                concepts = summary.key_concepts
                tech_stack = summary.tech_stack if summary.tech_stack else []
            else:
                # Fall back to concepts table
                from .db_models import DBConcept
                doc_concepts = db.query(DBConcept).filter(
                    DBConcept.document_id == doc.id
                ).all()

                concepts = [c.name for c in doc_concepts]
                tech_stack = [c.name for c in doc_concepts if c.category in ('tool', 'framework', 'language')]

            # Create node
            node = DocumentNode(
                doc_id=doc.doc_id,
                internal_id=doc.id,
                filename=doc.filename,
                source_type=doc.source_type or "unknown",
                concepts=[c.lower() for c in concepts],
                tech_stack=[t.lower() for t in tech_stack],
                skill_level=doc.skill_level,
                cluster_id=doc.cluster_id
            )
            self._nodes[doc.doc_id] = node

            # Build indexes
            for concept in node.concepts:
                self._concept_index[concept].add(doc.doc_id)

            for tech in node.tech_stack:
                self._tech_index[tech].add(doc.doc_id)

            if node.cluster_id is not None:
                self._cluster_index[node.cluster_id].add(doc.doc_id)

        # Build relationships
        self._build_relationships()

        # Calculate stats
        total_connections = sum(1 for r in self._relationships)
        avg_connections = total_connections / len(self._nodes) if self._nodes else 0

        return KnowledgeGraphStats(
            total_documents=len(self._nodes),
            total_relationships=len(self._relationships),
            unique_concepts=len(self._concept_index),
            unique_technologies=len(self._tech_index),
            avg_connections_per_doc=round(avg_connections, 2)
        )

    def _build_relationships(self):
        """Build relationships between documents."""
        doc_ids = list(self._nodes.keys())

        for i, doc1_id in enumerate(doc_ids):
            node1 = self._nodes[doc1_id]

            for doc2_id in doc_ids[i + 1:]:
                node2 = self._nodes[doc2_id]

                # Check shared concepts
                shared_concepts = set(node1.concepts) & set(node2.concepts)
                if shared_concepts:
                    strength = len(shared_concepts) / max(
                        len(node1.concepts), len(node2.concepts), 1
                    )
                    self._relationships.append(DocumentRelationship(
                        source_doc_id=doc1_id,
                        target_doc_id=doc2_id,
                        relationship_type="shared_concept",
                        strength=min(strength, 1.0),
                        shared_items=list(shared_concepts)
                    ))

                # Check shared technologies
                shared_tech = set(node1.tech_stack) & set(node2.tech_stack)
                if shared_tech:
                    strength = len(shared_tech) / max(
                        len(node1.tech_stack), len(node2.tech_stack), 1
                    )
                    self._relationships.append(DocumentRelationship(
                        source_doc_id=doc1_id,
                        target_doc_id=doc2_id,
                        relationship_type="shared_tech",
                        strength=min(strength, 1.0),
                        shared_items=list(shared_tech)
                    ))

                # Check same cluster
                if (node1.cluster_id is not None and
                    node1.cluster_id == node2.cluster_id):
                    self._relationships.append(DocumentRelationship(
                        source_doc_id=doc1_id,
                        target_doc_id=doc2_id,
                        relationship_type="same_cluster",
                        strength=0.8,
                        shared_items=[f"cluster_{node1.cluster_id}"]
                    ))

    def get_related_documents(
        self,
        doc_id: int,
        relationship_type: Optional[str] = None,
        min_strength: float = 0.1,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get documents related to a given document.

        Args:
            doc_id: Document ID
            relationship_type: Filter by relationship type
            min_strength: Minimum relationship strength
            limit: Maximum results

        Returns:
            List of related documents with relationship info
        """
        if doc_id not in self._nodes:
            return []

        related = []

        for rel in self._relationships:
            # Check if this relationship involves our document
            if rel.source_doc_id == doc_id:
                other_id = rel.target_doc_id
            elif rel.target_doc_id == doc_id:
                other_id = rel.source_doc_id
            else:
                continue

            # Apply filters
            if relationship_type and rel.relationship_type != relationship_type:
                continue
            if rel.strength < min_strength:
                continue

            other_node = self._nodes.get(other_id)
            if not other_node:
                continue

            related.append({
                "doc_id": other_id,
                "filename": other_node.filename,
                "source_type": other_node.source_type,
                "relationship_type": rel.relationship_type,
                "strength": rel.strength,
                "shared_items": rel.shared_items
            })

        # Sort by strength and limit
        related.sort(key=lambda x: x["strength"], reverse=True)
        return related[:limit]

    def find_documents_by_concept(
        self,
        concept: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Find documents that cover a specific concept."""
        concept_lower = concept.lower()
        doc_ids = self._concept_index.get(concept_lower, set())

        results = []
        for doc_id in doc_ids:
            node = self._nodes.get(doc_id)
            if node:
                results.append({
                    "doc_id": doc_id,
                    "filename": node.filename,
                    "source_type": node.source_type,
                    "concepts": node.concepts,
                    "technologies": node.tech_stack
                })

        return results[:limit]

    def find_documents_by_tech(
        self,
        technology: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Find documents that use a specific technology."""
        tech_lower = technology.lower()
        doc_ids = self._tech_index.get(tech_lower, set())

        results = []
        for doc_id in doc_ids:
            node = self._nodes.get(doc_id)
            if node:
                results.append({
                    "doc_id": doc_id,
                    "filename": node.filename,
                    "source_type": node.source_type,
                    "concepts": node.concepts,
                    "technologies": node.tech_stack
                })

        return results[:limit]

    def get_concept_cloud(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get top concepts across all documents."""
        concepts = [
            {"concept": concept, "frequency": len(doc_ids)}
            for concept, doc_ids in self._concept_index.items()
        ]
        concepts.sort(key=lambda x: x["frequency"], reverse=True)
        return concepts[:limit]

    def get_tech_cloud(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get top technologies across all documents."""
        techs = [
            {"tech": tech, "frequency": len(doc_ids)}
            for tech, doc_ids in self._tech_index.items()
        ]
        techs.sort(key=lambda x: x["frequency"], reverse=True)
        return techs[:limit]

    def find_learning_path(
        self,
        start_concept: str,
        end_concept: str,
        max_steps: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find a learning path from one concept to another.

        Uses BFS to find shortest path through related documents.
        """
        start_lower = start_concept.lower()
        end_lower = end_concept.lower()

        start_docs = self._concept_index.get(start_lower, set())
        end_docs = self._concept_index.get(end_lower, set())

        if not start_docs or not end_docs:
            return []

        # If same document has both concepts
        overlap = start_docs & end_docs
        if overlap:
            doc_id = next(iter(overlap))
            node = self._nodes[doc_id]
            return [{
                "step": 1,
                "doc_id": doc_id,
                "filename": node.filename,
                "connects": [start_concept, end_concept]
            }]

        # BFS to find path
        from collections import deque

        visited = set()
        queue = deque()

        # Start from all docs with start concept
        for doc_id in start_docs:
            queue.append((doc_id, [doc_id]))
            visited.add(doc_id)

        while queue and len(queue[0][1]) <= max_steps:
            current_id, path = queue.popleft()

            # Get related documents
            for rel in self._relationships:
                if rel.source_doc_id == current_id:
                    next_id = rel.target_doc_id
                elif rel.target_doc_id == current_id:
                    next_id = rel.source_doc_id
                else:
                    continue

                if next_id in visited:
                    continue

                new_path = path + [next_id]

                # Check if we reached the end
                if next_id in end_docs:
                    return self._format_path(new_path, start_concept, end_concept)

                visited.add(next_id)
                queue.append((next_id, new_path))

        return []  # No path found

    def _format_path(
        self,
        doc_ids: List[int],
        start_concept: str,
        end_concept: str
    ) -> List[Dict[str, Any]]:
        """Format a learning path for output."""
        path = []
        for i, doc_id in enumerate(doc_ids):
            node = self._nodes[doc_id]
            step = {
                "step": i + 1,
                "doc_id": doc_id,
                "filename": node.filename,
                "source_type": node.source_type,
                "concepts": node.concepts[:5],
                "tech": node.tech_stack[:5]
            }

            if i == 0:
                step["starts_with"] = start_concept
            if i == len(doc_ids) - 1:
                step["ends_with"] = end_concept

            path.append(step)

        return path


# Cache for knowledge graphs (per KB)
_graph_cache: Dict[str, KnowledgeGraphService] = {}


async def get_knowledge_graph(
    db: Session,
    knowledge_base_id: str,
    rebuild: bool = False
) -> KnowledgeGraphService:
    """Get or build knowledge graph for a KB."""
    global _graph_cache

    if knowledge_base_id not in _graph_cache or rebuild:
        service = KnowledgeGraphService()
        service.build_graph(db, knowledge_base_id)
        _graph_cache[knowledge_base_id] = service
        logger.info(f"Built knowledge graph for KB {knowledge_base_id}")

    return _graph_cache[knowledge_base_id]


async def get_graph_stats(
    db: Session,
    knowledge_base_id: str
) -> Dict[str, Any]:
    """Get statistics about the knowledge graph."""
    graph = await get_knowledge_graph(db, knowledge_base_id)

    stats = KnowledgeGraphStats(
        total_documents=len(graph._nodes),
        total_relationships=len(graph._relationships),
        unique_concepts=len(graph._concept_index),
        unique_technologies=len(graph._tech_index),
        avg_connections_per_doc=round(
            len(graph._relationships) / max(len(graph._nodes), 1), 2
        )
    )

    return {
        "total_documents": stats.total_documents,
        "total_relationships": stats.total_relationships,
        "unique_concepts": stats.unique_concepts,
        "unique_technologies": stats.unique_technologies,
        "avg_connections_per_doc": stats.avg_connections_per_doc
    }
