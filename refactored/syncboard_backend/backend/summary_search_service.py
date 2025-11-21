"""
Summary Search Service for SyncBoard 3.0 Knowledge Bank.

Enables searching through document summaries for faster, context-aware results.
Uses TF-IDF similarity on summaries rather than full document content.

Benefits:
- Faster search (smaller text corpus)
- Better semantic understanding (summaries capture key concepts)
- Multi-level search (chunk, section, or document level)
"""

import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

logger = logging.getLogger(__name__)


@dataclass
class SummarySearchResult:
    """A search result from summary search."""
    document_id: int
    doc_id: int
    filename: Optional[str]
    source_type: Optional[str]
    summary_level: int
    summary_type: str
    short_summary: str
    long_summary: Optional[str]
    key_concepts: List[str]
    tech_stack: List[str]
    relevance_score: float
    match_type: str  # 'concept', 'tech', 'text', 'combined'


class SummarySearchService:
    """Service for searching through document summaries."""

    def __init__(self):
        """Initialize the summary search service."""
        self._vectorizer = None
        self._summary_matrix = None
        self._summary_ids = []

    def search_by_concepts(
        self,
        db: Session,
        knowledge_base_id: str,
        concepts: List[str],
        limit: int = 20
    ) -> List[SummarySearchResult]:
        """
        Search summaries by matching concepts.

        Args:
            db: Database session
            knowledge_base_id: KB to search within
            concepts: List of concepts to match
            limit: Maximum results

        Returns:
            List of matching summaries with relevance scores
        """
        from .db_models import DBDocument, DBDocumentSummary

        # Normalize concepts for matching
        concepts_lower = [c.lower().strip() for c in concepts]

        # Get document-level summaries with concepts
        summaries = db.query(DBDocumentSummary).filter(
            DBDocumentSummary.knowledge_base_id == knowledge_base_id,
            DBDocumentSummary.summary_level == 3,  # Document level
            DBDocumentSummary.key_concepts.isnot(None)
        ).all()

        results = []
        for summary in summaries:
            if not summary.key_concepts:
                continue

            # Calculate concept overlap
            summary_concepts = [c.lower() for c in summary.key_concepts]
            matching_concepts = set(concepts_lower) & set(summary_concepts)

            if matching_concepts:
                # Score based on overlap ratio
                score = len(matching_concepts) / max(len(concepts_lower), 1)

                # Get document info
                doc = db.query(DBDocument).filter(
                    DBDocument.id == summary.document_id
                ).first()

                if doc:
                    results.append(SummarySearchResult(
                        document_id=summary.document_id,
                        doc_id=doc.doc_id,
                        filename=doc.filename,
                        source_type=doc.source_type,
                        summary_level=summary.summary_level,
                        summary_type=summary.summary_type,
                        short_summary=summary.short_summary,
                        long_summary=summary.long_summary,
                        key_concepts=summary.key_concepts,
                        tech_stack=summary.tech_stack or [],
                        relevance_score=score,
                        match_type='concept'
                    ))

        # Sort by score and limit
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:limit]

    def search_by_technology(
        self,
        db: Session,
        knowledge_base_id: str,
        technologies: List[str],
        limit: int = 20
    ) -> List[SummarySearchResult]:
        """
        Search summaries by matching technologies.

        Args:
            db: Database session
            knowledge_base_id: KB to search within
            technologies: List of technologies to match
            limit: Maximum results

        Returns:
            List of matching summaries with relevance scores
        """
        from .db_models import DBDocument, DBDocumentSummary

        # Normalize technologies
        tech_lower = [t.lower().strip() for t in technologies]

        # Get document-level summaries with tech stack
        summaries = db.query(DBDocumentSummary).filter(
            DBDocumentSummary.knowledge_base_id == knowledge_base_id,
            DBDocumentSummary.summary_level == 3,
            DBDocumentSummary.tech_stack.isnot(None)
        ).all()

        results = []
        for summary in summaries:
            if not summary.tech_stack:
                continue

            # Calculate tech overlap
            summary_tech = [t.lower() for t in summary.tech_stack]
            matching_tech = set(tech_lower) & set(summary_tech)

            if matching_tech:
                score = len(matching_tech) / max(len(tech_lower), 1)

                doc = db.query(DBDocument).filter(
                    DBDocument.id == summary.document_id
                ).first()

                if doc:
                    results.append(SummarySearchResult(
                        document_id=summary.document_id,
                        doc_id=doc.doc_id,
                        filename=doc.filename,
                        source_type=doc.source_type,
                        summary_level=summary.summary_level,
                        summary_type=summary.summary_type,
                        short_summary=summary.short_summary,
                        long_summary=summary.long_summary,
                        key_concepts=summary.key_concepts or [],
                        tech_stack=summary.tech_stack,
                        relevance_score=score,
                        match_type='tech'
                    ))

        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:limit]

    def search_by_text(
        self,
        db: Session,
        knowledge_base_id: str,
        query: str,
        level: Optional[int] = None,
        limit: int = 20
    ) -> List[SummarySearchResult]:
        """
        Full-text search through summary content.

        Args:
            db: Database session
            knowledge_base_id: KB to search within
            query: Search query
            level: Optional summary level filter (1=chunk, 2=section, 3=document)
            limit: Maximum results

        Returns:
            List of matching summaries with relevance scores
        """
        from .db_models import DBDocument, DBDocumentSummary

        query_lower = query.lower()
        query_terms = query_lower.split()

        # Build base query
        filters = [DBDocumentSummary.knowledge_base_id == knowledge_base_id]
        if level:
            filters.append(DBDocumentSummary.summary_level == level)

        summaries = db.query(DBDocumentSummary).filter(*filters).all()

        results = []
        for summary in summaries:
            # Calculate text relevance
            text_to_search = (summary.short_summary or "").lower()
            if summary.long_summary:
                text_to_search += " " + summary.long_summary.lower()

            # Count matching terms
            matches = sum(1 for term in query_terms if term in text_to_search)

            # Also check concepts and tech
            concept_matches = 0
            if summary.key_concepts:
                concept_text = " ".join(c.lower() for c in summary.key_concepts)
                concept_matches = sum(1 for term in query_terms if term in concept_text)

            tech_matches = 0
            if summary.tech_stack:
                tech_text = " ".join(t.lower() for t in summary.tech_stack)
                tech_matches = sum(1 for term in query_terms if term in tech_text)

            total_matches = matches + concept_matches + tech_matches

            if total_matches > 0:
                # Score based on total matches and term coverage
                score = total_matches / (len(query_terms) * 3)  # Max 3 types of matches
                score = min(1.0, score)  # Cap at 1.0

                doc = db.query(DBDocument).filter(
                    DBDocument.id == summary.document_id
                ).first()

                if doc:
                    results.append(SummarySearchResult(
                        document_id=summary.document_id,
                        doc_id=doc.doc_id,
                        filename=doc.filename,
                        source_type=doc.source_type,
                        summary_level=summary.summary_level,
                        summary_type=summary.summary_type,
                        short_summary=summary.short_summary,
                        long_summary=summary.long_summary,
                        key_concepts=summary.key_concepts or [],
                        tech_stack=summary.tech_stack or [],
                        relevance_score=score,
                        match_type='text'
                    ))

        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:limit]

    def combined_search(
        self,
        db: Session,
        knowledge_base_id: str,
        query: str,
        concepts: Optional[List[str]] = None,
        technologies: Optional[List[str]] = None,
        level: Optional[int] = None,
        limit: int = 20
    ) -> List[SummarySearchResult]:
        """
        Combined search using text, concepts, and technologies.

        Merges results from all search types with weighted scoring.

        Args:
            db: Database session
            knowledge_base_id: KB to search within
            query: Text query
            concepts: Optional concept filters
            technologies: Optional technology filters
            level: Optional summary level
            limit: Maximum results

        Returns:
            Combined search results with relevance scores
        """
        # Collect results from each search type
        all_results: Dict[int, SummarySearchResult] = {}

        # Text search (weight 0.5)
        if query:
            text_results = self.search_by_text(
                db, knowledge_base_id, query, level, limit * 2
            )
            for result in text_results:
                doc_id = result.document_id
                if doc_id not in all_results:
                    all_results[doc_id] = result
                    all_results[doc_id].relevance_score *= 0.5
                else:
                    all_results[doc_id].relevance_score += result.relevance_score * 0.5

        # Concept search (weight 0.3)
        if concepts:
            concept_results = self.search_by_concepts(
                db, knowledge_base_id, concepts, limit * 2
            )
            for result in concept_results:
                doc_id = result.document_id
                if doc_id not in all_results:
                    all_results[doc_id] = result
                    all_results[doc_id].relevance_score *= 0.3
                else:
                    all_results[doc_id].relevance_score += result.relevance_score * 0.3

        # Technology search (weight 0.2)
        if technologies:
            tech_results = self.search_by_technology(
                db, knowledge_base_id, technologies, limit * 2
            )
            for result in tech_results:
                doc_id = result.document_id
                if doc_id not in all_results:
                    all_results[doc_id] = result
                    all_results[doc_id].relevance_score *= 0.2
                else:
                    all_results[doc_id].relevance_score += result.relevance_score * 0.2

        # Update match type to combined
        for result in all_results.values():
            result.match_type = 'combined'

        # Sort and limit
        results = sorted(
            all_results.values(),
            key=lambda x: x.relevance_score,
            reverse=True
        )

        return results[:limit]


async def search_summaries(
    db: Session,
    knowledge_base_id: str,
    query: Optional[str] = None,
    concepts: Optional[List[str]] = None,
    technologies: Optional[List[str]] = None,
    level: Optional[int] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Convenience function for summary search.

    Args:
        db: Database session
        knowledge_base_id: KB to search within
        query: Optional text query
        concepts: Optional concept filters
        technologies: Optional technology filters
        level: Optional summary level filter
        limit: Maximum results

    Returns:
        List of search result dicts
    """
    service = SummarySearchService()

    if query or concepts or technologies:
        results = service.combined_search(
            db=db,
            knowledge_base_id=knowledge_base_id,
            query=query or "",
            concepts=concepts,
            technologies=technologies,
            level=level,
            limit=limit
        )
    else:
        # No search criteria - return recent summaries
        from .db_models import DBDocument, DBDocumentSummary

        summaries = db.query(DBDocumentSummary).filter(
            DBDocumentSummary.knowledge_base_id == knowledge_base_id,
            DBDocumentSummary.summary_level == 3
        ).order_by(DBDocumentSummary.created_at.desc()).limit(limit).all()

        results = []
        for summary in summaries:
            doc = db.query(DBDocument).filter(
                DBDocument.id == summary.document_id
            ).first()

            if doc:
                results.append(SummarySearchResult(
                    document_id=summary.document_id,
                    doc_id=doc.doc_id,
                    filename=doc.filename,
                    source_type=doc.source_type,
                    summary_level=summary.summary_level,
                    summary_type=summary.summary_type,
                    short_summary=summary.short_summary,
                    long_summary=summary.long_summary,
                    key_concepts=summary.key_concepts or [],
                    tech_stack=summary.tech_stack or [],
                    relevance_score=1.0,
                    match_type='recent'
                ))

    # Convert to dicts
    return [
        {
            "doc_id": r.doc_id,
            "filename": r.filename,
            "source_type": r.source_type,
            "summary_level": r.summary_level,
            "summary_type": r.summary_type,
            "short_summary": r.short_summary,
            "long_summary": r.long_summary,
            "key_concepts": r.key_concepts,
            "tech_stack": r.tech_stack,
            "relevance_score": round(r.relevance_score, 3),
            "match_type": r.match_type
        }
        for r in results
    ]


async def get_summary_stats(
    db: Session,
    knowledge_base_id: str
) -> Dict[str, Any]:
    """
    Get statistics about summaries in a knowledge base.

    Returns:
        Dict with summary statistics
    """
    from .db_models import DBDocumentSummary
    from sqlalchemy import func

    # Count by level
    level_counts = db.query(
        DBDocumentSummary.summary_level,
        func.count(DBDocumentSummary.id)
    ).filter(
        DBDocumentSummary.knowledge_base_id == knowledge_base_id
    ).group_by(DBDocumentSummary.summary_level).all()

    level_stats = {
        "chunk_summaries": 0,
        "section_summaries": 0,
        "document_summaries": 0
    }
    for level, count in level_counts:
        if level == 1:
            level_stats["chunk_summaries"] = count
        elif level == 2:
            level_stats["section_summaries"] = count
        elif level == 3:
            level_stats["document_summaries"] = count

    # Count unique concepts and tech
    doc_summaries = db.query(DBDocumentSummary).filter(
        DBDocumentSummary.knowledge_base_id == knowledge_base_id,
        DBDocumentSummary.summary_level == 3
    ).all()

    all_concepts = set()
    all_tech = set()

    for summary in doc_summaries:
        if summary.key_concepts:
            all_concepts.update(c.lower() for c in summary.key_concepts)
        if summary.tech_stack:
            all_tech.update(t.lower() for t in summary.tech_stack)

    return {
        **level_stats,
        "unique_concepts": len(all_concepts),
        "unique_technologies": len(all_tech),
        "total_summaries": sum(level_stats.values())
    }


# Singleton instance
_summary_search_service: Optional[SummarySearchService] = None


def get_summary_search_service() -> SummarySearchService:
    """Get or create the summary search service singleton."""
    global _summary_search_service
    if _summary_search_service is None:
        _summary_search_service = SummarySearchService()
    return _summary_search_service
