"""
Tests for Knowledge Services.

Tests all 10 knowledge enhancement features:
1. Knowledge Gap Analysis
2. Flashcard Generator
3. Weekly Digest
4. Learning Path Optimizer
5. Document Quality Scorer
6. Conversation RAG
7. Code Generator
8. Document Comparison
9. ELI5 Explainer
10. Interview Prep Generator
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from dataclasses import asdict

from backend.knowledge_services import (
    KnowledgeServices,
    KnowledgeGap,
    GapAnalysisResult,
    Flashcard,
    WeeklyDigest,
    LearningPath,
    DocumentQuality,
    DocumentComparison,
    InterviewPrep,
    get_knowledge_services,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = Mock()
    return session


@pytest.fixture
def mock_kb_summary():
    """Sample knowledge base summary."""
    return {
        "document_count": 25,
        "concept_count": 150,
        "top_concepts": [
            {"name": "Python", "category": "language", "freq": 20},
            {"name": "FastAPI", "category": "framework", "freq": 15},
            {"name": "PostgreSQL", "category": "database", "freq": 12},
            {"name": "Docker", "category": "tool", "freq": 10},
            {"name": "REST API", "category": "concept", "freq": 8},
        ],
        "clusters": [
            {"name": "Web Development", "concepts": ["FastAPI", "REST API"]},
            {"name": "Data Storage", "concepts": ["PostgreSQL", "Redis"]},
        ],
        "source_distribution": {"file": 15, "url": 8, "text": 2}
    }


@pytest.fixture
def knowledge_services(mock_db_session):
    """Create KnowledgeServices instance."""
    return KnowledgeServices(mock_db_session)


# =============================================================================
# Data Class Tests
# =============================================================================

class TestDataClasses:
    """Test data class creation and structure."""

    def test_knowledge_gap_creation(self):
        """Test KnowledgeGap dataclass."""
        gap = KnowledgeGap(
            area="Testing",
            severity="critical",
            description="No testing knowledge found",
            suggested_topics=["pytest", "unittest", "TDD"],
            related_existing_docs=[1, 2, 3],
            learning_priority=9
        )
        assert gap.area == "Testing"
        assert gap.severity == "critical"
        assert gap.learning_priority == 9
        assert len(gap.suggested_topics) == 3

    def test_flashcard_creation(self):
        """Test Flashcard dataclass."""
        card = Flashcard(
            front="What is a REST API?",
            back="An architectural style for web services",
            difficulty="easy",
            concept="REST API",
            source_doc_id=123,
            source_section="Introduction"
        )
        assert card.front.startswith("What")
        assert card.difficulty == "easy"
        assert card.source_doc_id == 123

    def test_weekly_digest_creation(self):
        """Test WeeklyDigest dataclass."""
        digest = WeeklyDigest(
            period_start=datetime.utcnow() - timedelta(days=7),
            period_end=datetime.utcnow(),
            documents_added=5,
            executive_summary="Great week of learning!",
            new_concepts=["FastAPI", "Pydantic"],
            skills_improved=["API Development"],
            focus_suggestions=["Add more testing content"],
            connections_to_existing=["Builds on Python knowledge"],
            quick_wins=["Try building a simple API"]
        )
        assert digest.documents_added == 5
        assert len(digest.new_concepts) == 2

    def test_learning_path_creation(self):
        """Test LearningPath dataclass."""
        path = LearningPath(
            goal="Learn FastAPI",
            total_documents=10,
            estimated_hours=5.5,
            ordered_docs=[{"doc_id": 1, "title": "Intro"}],
            skip_list=[5, 6],
            external_resources=["fastapi.tiangolo.com"]
        )
        assert path.goal == "Learn FastAPI"
        assert path.estimated_hours == 5.5

    def test_document_quality_creation(self):
        """Test DocumentQuality dataclass."""
        quality = DocumentQuality(
            doc_id=123,
            information_density=8,
            actionability=7,
            currency=9,
            uniqueness=6,
            overall_score=7.5,
            key_excerpts=["Important section here"],
            sections_to_skip=["Outdated part"],
            missing_context=["Needs more examples"]
        )
        assert quality.overall_score == 7.5
        assert quality.information_density == 8

    def test_document_comparison_creation(self):
        """Test DocumentComparison dataclass."""
        comparison = DocumentComparison(
            doc_a_id=1,
            doc_b_id=2,
            overlapping_concepts=["Python", "API"],
            contradictions=[{"topic": "auth", "doc_a_says": "JWT", "doc_b_says": "OAuth"}],
            complementary_info=[{"doc_a_has": "basics", "doc_b_has": "advanced"}],
            more_authoritative=1,
            recommended_order=[1, 2],
            synthesis="Read A first for basics, then B for depth"
        )
        assert comparison.more_authoritative == 1
        assert len(comparison.overlapping_concepts) == 2

    def test_interview_prep_creation(self):
        """Test InterviewPrep dataclass."""
        prep = InterviewPrep(
            topics=["Python", "FastAPI"],
            behavioral_questions=[{"question": "Tell me about a challenge"}],
            technical_questions=[{"question": "Explain REST"}],
            system_design_questions=[{"question": "Design an API"}],
            gotcha_questions=[{"question": "What is GIL?"}],
            study_recommendations=["Review async/await"]
        )
        assert len(prep.topics) == 2
        assert len(prep.behavioral_questions) == 1


# =============================================================================
# KnowledgeServices Initialization Tests
# =============================================================================

class TestKnowledgeServicesInit:
    """Test service initialization."""

    def test_initialization(self, mock_db_session):
        """Test basic initialization."""
        services = KnowledgeServices(mock_db_session)
        assert services.db == mock_db_session
        assert services._client is None  # Lazy loaded

    def test_factory_function(self, mock_db_session):
        """Test factory function."""
        services = get_knowledge_services(mock_db_session)
        assert isinstance(services, KnowledgeServices)


# =============================================================================
# Knowledge Gap Analysis Tests
# =============================================================================

class TestKnowledgeGapAnalysis:
    """Tests for knowledge gap analysis."""

    @pytest.mark.asyncio
    async def test_gap_analysis_insufficient_docs(self, knowledge_services, mock_db_session):
        """Test gap analysis with too few documents."""
        # Mock the summary to return few docs
        with patch.object(knowledge_services, '_get_kb_summary') as mock_summary:
            mock_summary.return_value = {
                "document_count": 2,
                "concept_count": 5,
                "top_concepts": [],
                "clusters": [],
                "source_distribution": {}
            }

            result = await knowledge_services.analyze_knowledge_gaps("user1", "kb1")

            assert result.total_documents == 2
            assert "Add more documents" in result.recommended_learning_path[0]

    @pytest.mark.asyncio
    async def test_gap_analysis_success(self, knowledge_services, mock_db_session, mock_kb_summary):
        """Test successful gap analysis."""
        with patch.object(knowledge_services, '_get_kb_summary') as mock_summary:
            mock_summary.return_value = mock_kb_summary

            # Mock LLM response
            mock_llm_response = json.dumps({
                "inferred_goal": "Learn web development",
                "strongest_areas": ["Python", "FastAPI"],
                "coverage_areas": ["Backend", "Databases"],
                "gaps": [
                    {
                        "area": "Testing",
                        "severity": "critical",
                        "description": "No testing content",
                        "suggested_topics": ["pytest"],
                        "learning_priority": 9
                    }
                ],
                "shallow_areas": [
                    {"area": "Docker", "current_depth": "Basic", "missing_depth": "Advanced"}
                ],
                "recommended_learning_path": ["Learn pytest", "Add Docker content"]
            })

            with patch.object(knowledge_services, '_call_llm', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = mock_llm_response

                result = await knowledge_services.analyze_knowledge_gaps("user1", "kb1")

                assert result.inferred_goal == "Learn web development"
                assert len(result.gaps) == 1
                assert result.gaps[0].area == "Testing"
                assert result.gaps[0].severity == "critical"


# =============================================================================
# Flashcard Generator Tests
# =============================================================================

class TestFlashcardGenerator:
    """Tests for flashcard generation."""

    @pytest.mark.asyncio
    async def test_flashcard_generation_no_doc(self, knowledge_services, mock_db_session):
        """Test flashcard generation with missing document."""
        mock_db_session.execute.return_value.fetchone.return_value = None

        cards = await knowledge_services.generate_flashcards(doc_id=999)

        assert cards == []

    @pytest.mark.asyncio
    async def test_flashcard_generation_success(self, knowledge_services, mock_db_session):
        """Test successful flashcard generation."""
        # Mock document fetch
        mock_doc = Mock()
        mock_doc.doc_id = 123
        mock_doc.filename = "python_guide.md"
        mock_doc.source_type = "file"
        mock_doc.content = "Python is a programming language..."
        mock_db_session.execute.return_value.fetchone.return_value = mock_doc

        # Mock LLM response
        mock_cards = json.dumps([
            {
                "front": "What is Python?",
                "back": "A programming language",
                "difficulty": "easy",
                "concept": "Python basics",
                "source_section": "Introduction"
            },
            {
                "front": "What is a list in Python?",
                "back": "An ordered, mutable collection",
                "difficulty": "easy",
                "concept": "Data structures",
                "source_section": "Collections"
            }
        ])

        with patch.object(knowledge_services, '_call_llm', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_cards

            cards = await knowledge_services.generate_flashcards(
                doc_id=123,
                num_cards=10,
                difficulty_mix="balanced"
            )

            assert len(cards) == 2
            assert cards[0].front == "What is Python?"
            assert cards[0].difficulty == "easy"
            assert cards[0].source_doc_id == 123


# =============================================================================
# Weekly Digest Tests
# =============================================================================

class TestWeeklyDigest:
    """Tests for weekly digest generation."""

    @pytest.mark.asyncio
    async def test_digest_no_recent_docs(self, knowledge_services, mock_db_session):
        """Test digest with no recent documents."""
        mock_db_session.execute.return_value.fetchall.return_value = []

        digest = await knowledge_services.generate_weekly_digest("user1", "kb1", days=7)

        assert digest.documents_added == 0
        assert "No new documents" in digest.executive_summary

    @pytest.mark.asyncio
    async def test_digest_success(self, knowledge_services, mock_db_session):
        """Test successful digest generation."""
        # Mock recent documents
        mock_docs = [
            Mock(doc_id=1, filename="doc1.md", source_type="file", skill_level="beginner", content="...", ingested_at=datetime.utcnow()),
            Mock(doc_id=2, filename="doc2.md", source_type="url", skill_level="intermediate", content="...", ingested_at=datetime.utcnow()),
        ]

        # Mock concepts - use MagicMock and configure_mock since 'name' is special in Mock
        mock_concept1 = MagicMock()
        mock_concept1.configure_mock(name="Python", category="language")
        mock_concept2 = MagicMock()
        mock_concept2.configure_mock(name="FastAPI", category="framework")
        mock_concepts = [mock_concept1, mock_concept2]

        # Set up mock returns
        call_count = [0]
        def mock_execute(query, params=None):
            result = Mock()
            if call_count[0] == 0:
                result.fetchall.return_value = mock_docs
            else:
                result.fetchall.return_value = mock_concepts
            call_count[0] += 1
            return result

        mock_db_session.execute = mock_execute

        # Mock LLM response
        mock_digest = json.dumps({
            "executive_summary": "Great week! You learned about Python and FastAPI.",
            "skills_improved": ["Backend Development"],
            "focus_suggestions": ["Add more testing content"],
            "connections_to_existing": ["Builds on your Python foundation"],
            "quick_wins": ["Build a simple API endpoint"]
        })

        with patch.object(knowledge_services, '_call_llm', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_digest

            digest = await knowledge_services.generate_weekly_digest("user1", "kb1", days=7)

            assert digest.documents_added == 2
            assert "Python" in digest.new_concepts


# =============================================================================
# Learning Path Optimizer Tests
# =============================================================================

class TestLearningPathOptimizer:
    """Tests for learning path optimization."""

    @pytest.mark.asyncio
    async def test_learning_path_no_docs(self, knowledge_services, mock_db_session):
        """Test learning path with no documents."""
        mock_db_session.execute.return_value.fetchall.return_value = []

        path = await knowledge_services.optimize_learning_path("user1", "kb1", "Learn FastAPI")

        assert path.total_documents == 0
        assert "Add documents" in path.external_resources[0]

    @pytest.mark.asyncio
    async def test_learning_path_success(self, knowledge_services, mock_db_session):
        """Test successful learning path generation."""
        # Mock documents
        mock_docs = [
            Mock(doc_id=1, filename="basics.md", source_type="file", skill_level="beginner", content_length=1000, short_summary="Python basics"),
            Mock(doc_id=2, filename="advanced.md", source_type="file", skill_level="advanced", content_length=2000, short_summary="Advanced topics"),
        ]
        mock_db_session.execute.return_value.fetchall.return_value = mock_docs

        # Mock LLM response
        mock_path = json.dumps({
            "estimated_total_hours": 5.5,
            "ordered_docs": [
                {"doc_id": 1, "order": 1, "title": "basics.md", "time_estimate_minutes": 30},
                {"doc_id": 2, "order": 2, "title": "advanced.md", "time_estimate_minutes": 60},
            ],
            "skip_list": [],
            "external_resources": ["python.org"]
        })

        with patch.object(knowledge_services, '_call_llm', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_path

            path = await knowledge_services.optimize_learning_path("user1", "kb1", "Learn Python")

            assert path.goal == "Learn Python"
            assert path.estimated_hours == 5.5
            assert len(path.ordered_docs) == 2


# =============================================================================
# Document Quality Scorer Tests
# =============================================================================

class TestDocumentQualityScorer:
    """Tests for document quality scoring."""

    @pytest.mark.asyncio
    async def test_quality_score_no_doc(self, knowledge_services, mock_db_session):
        """Test quality scoring with missing document."""
        mock_db_session.execute.return_value.fetchone.return_value = None

        quality = await knowledge_services.score_document_quality(doc_id=999)

        assert quality.overall_score == 0
        assert "Document not found" in quality.missing_context

    @pytest.mark.asyncio
    async def test_quality_score_success(self, knowledge_services, mock_db_session):
        """Test successful quality scoring."""
        # Mock document
        mock_doc = Mock()
        mock_doc.doc_id = 123
        mock_doc.filename = "guide.md"
        mock_doc.source_type = "file"
        mock_doc.source_url = None
        mock_doc.ingested_at = datetime.utcnow()
        mock_doc.content = "This is a comprehensive guide..."
        mock_db_session.execute.return_value.fetchone.return_value = mock_doc

        # Mock LLM response
        mock_quality = json.dumps({
            "information_density": 8,
            "actionability": 7,
            "currency": 9,
            "uniqueness": 6,
            "key_excerpts": ["Important section here"],
            "sections_to_skip": ["Outdated part"],
            "missing_context": ["Needs more examples"]
        })

        with patch.object(knowledge_services, '_call_llm', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_quality

            quality = await knowledge_services.score_document_quality(doc_id=123)

            assert quality.information_density == 8
            assert quality.overall_score == 7.5  # (8+7+9+6)/4


# =============================================================================
# Conversation RAG Tests
# =============================================================================

class TestConversationRAG:
    """Tests for conversation-style RAG."""

    @pytest.mark.asyncio
    async def test_conversation_no_history(self, knowledge_services, mock_db_session, mock_kb_summary):
        """Test conversation without history."""
        with patch.object(knowledge_services, '_get_kb_summary') as mock_summary:
            mock_summary.return_value = mock_kb_summary

            with patch.object(knowledge_services, '_call_llm', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = "Based on your knowledge base, Python is a programming language..."

                result = await knowledge_services.conversation_rag(
                    query="What is Python?",
                    kb_id="kb1"
                )

                assert "response" in result
                assert result["query"] == "What is Python?"
                assert result["context_used"]["history_turns"] == 0

    @pytest.mark.asyncio
    async def test_conversation_with_history(self, knowledge_services, mock_db_session, mock_kb_summary):
        """Test conversation with history."""
        with patch.object(knowledge_services, '_get_kb_summary') as mock_summary:
            mock_summary.return_value = mock_kb_summary

            with patch.object(knowledge_services, '_call_llm', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = "As I mentioned before, FastAPI is built on Python..."

                history = [
                    {"user": "What is Python?", "assistant": "Python is a programming language."},
                    {"user": "What frameworks use it?", "assistant": "FastAPI, Django, Flask..."}
                ]

                result = await knowledge_services.conversation_rag(
                    query="Tell me more about FastAPI",
                    kb_id="kb1",
                    conversation_history=history
                )

                assert result["context_used"]["history_turns"] == 2


# =============================================================================
# Code Generator Tests
# =============================================================================

class TestCodeGenerator:
    """Tests for code generation from concepts."""

    @pytest.mark.asyncio
    async def test_code_generation_success(self, knowledge_services, mock_db_session, mock_kb_summary):
        """Test successful code generation."""
        with patch.object(knowledge_services, '_get_kb_summary') as mock_summary:
            mock_summary.return_value = mock_kb_summary

            mock_code = json.dumps({
                "project_name": "fastapi-starter",
                "description": "A simple FastAPI application",
                "concepts_demonstrated": ["FastAPI", "REST API"],
                "files": [
                    {"filename": "main.py", "content": "from fastapi import FastAPI\napp = FastAPI()", "purpose": "Main app"}
                ],
                "setup_instructions": ["pip install fastapi uvicorn"],
                "run_command": "uvicorn main:app --reload",
                "next_steps": ["Add database connection"]
            })

            with patch.object(knowledge_services, '_call_llm', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = mock_code

                result = await knowledge_services.generate_code_from_concepts(
                    kb_id="kb1",
                    project_type="starter",
                    language="python"
                )

                assert result["project_name"] == "fastapi-starter"
                assert len(result["files"]) == 1
                assert "main.py" in result["files"][0]["filename"]


# =============================================================================
# Document Comparison Tests
# =============================================================================

class TestDocumentComparison:
    """Tests for document comparison."""

    @pytest.mark.asyncio
    async def test_comparison_missing_doc(self, knowledge_services, mock_db_session):
        """Test comparison with missing document."""
        mock_db_session.execute.return_value.fetchall.return_value = [
            Mock(doc_id=1, filename="doc1.md", source_type="file", content="Content 1")
        ]  # Only one doc found

        comparison = await knowledge_services.compare_documents(doc_a_id=1, doc_b_id=2)

        assert "Could not find both documents" in comparison.synthesis

    @pytest.mark.asyncio
    async def test_comparison_success(self, knowledge_services, mock_db_session):
        """Test successful document comparison."""
        # Mock both documents
        mock_docs = [
            Mock(doc_id=1, filename="doc1.md", source_type="file", content="Content about Python basics"),
            Mock(doc_id=2, filename="doc2.md", source_type="file", content="Content about advanced Python")
        ]
        mock_db_session.execute.return_value.fetchall.return_value = mock_docs

        mock_comparison = json.dumps({
            "overlapping_concepts": ["Python", "programming"],
            "contradictions": [],
            "complementary_info": [{"doc_a_has": "basics", "doc_b_has": "advanced"}],
            "more_authoritative": "B",
            "authority_reason": "More detailed",
            "recommended_order": ["A", "B"],
            "order_reason": "Start with basics",
            "synthesis": "Read A for fundamentals, then B for depth"
        })

        with patch.object(knowledge_services, '_call_llm', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_comparison

            comparison = await knowledge_services.compare_documents(doc_a_id=1, doc_b_id=2)

            assert "Python" in comparison.overlapping_concepts
            assert comparison.more_authoritative == 2  # doc_b_id
            assert comparison.recommended_order == [1, 2]


# =============================================================================
# ELI5 Explainer Tests
# =============================================================================

class TestELI5Explainer:
    """Tests for ELI5 explanations."""

    @pytest.mark.asyncio
    async def test_eli5_success(self, knowledge_services, mock_db_session, mock_kb_summary):
        """Test successful ELI5 explanation."""
        with patch.object(knowledge_services, '_get_kb_summary') as mock_summary:
            mock_summary.return_value = mock_kb_summary

            mock_eli5 = json.dumps({
                "topic": "REST API",
                "simple_explanation": "A REST API is like a waiter at a restaurant. You tell the waiter what you want, and they bring it to you from the kitchen.",
                "analogy": "Like ordering food at a restaurant",
                "why_it_matters": "It lets different programs talk to each other over the internet",
                "simple_example": "When you check the weather on your phone, it uses an API to get the data",
                "learn_next": ["HTTP methods", "JSON"],
                "common_misconceptions": ["REST is not a protocol, it's an architectural style"]
            })

            with patch.object(knowledge_services, '_call_llm', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = mock_eli5

                result = await knowledge_services.explain_eli5("REST API", "kb1")

                assert result["topic"] == "REST API"
                assert "waiter" in result["simple_explanation"].lower() or "restaurant" in result["analogy"].lower()


# =============================================================================
# Interview Prep Tests
# =============================================================================

class TestInterviewPrep:
    """Tests for interview prep generation."""

    @pytest.mark.asyncio
    async def test_interview_prep_success(self, knowledge_services, mock_db_session, mock_kb_summary):
        """Test successful interview prep generation."""
        with patch.object(knowledge_services, '_get_kb_summary') as mock_summary:
            mock_summary.return_value = mock_kb_summary

            mock_prep = json.dumps({
                "role": "Python Backend Developer",
                "level": "mid",
                "behavioral_questions": [
                    {"question": "Tell me about a challenging project", "what_they_test": "Problem solving", "good_answer_elements": ["STAR format"]}
                ],
                "technical_questions": [
                    {"question": "Explain Python's GIL", "ideal_answer": "Global Interpreter Lock prevents...", "follow_ups": ["How to work around it?"]}
                ],
                "system_design_questions": [
                    {"question": "Design a URL shortener", "key_points": ["Database choice", "Hashing"], "common_mistakes": ["Not considering scale"]}
                ],
                "gotcha_questions": [
                    {"question": "Is Python interpreted or compiled?", "why_tricky": "It's actually both", "how_to_handle": "Explain the bytecode compilation"}
                ],
                "study_recommendations": ["Review async/await", "Practice system design"]
            })

            with patch.object(knowledge_services, '_call_llm', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = mock_prep

                prep = await knowledge_services.generate_interview_prep(
                    kb_id="kb1",
                    role="Python Developer",
                    level="mid"
                )

                assert len(prep.behavioral_questions) == 1
                assert len(prep.technical_questions) == 1
                assert len(prep.gotcha_questions) == 1
                assert "Python" in prep.topics


# =============================================================================
# LLM Call Helper Tests
# =============================================================================

class TestLLMCallHelper:
    """Tests for the LLM call helper method."""

    @pytest.mark.asyncio
    async def test_llm_call_success(self, knowledge_services):
        """Test successful LLM call."""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Test response"))]

        with patch.object(knowledge_services, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await knowledge_services._call_llm(
                system_message="You are helpful",
                user_message="Hello",
                temperature=0.7,
                max_tokens=100
            )

            assert result == "Test response"

    @pytest.mark.asyncio
    async def test_llm_call_error(self, knowledge_services):
        """Test LLM call error handling."""
        with patch.object(knowledge_services, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))
            mock_get_client.return_value = mock_client

            with pytest.raises(Exception) as exc_info:
                await knowledge_services._call_llm(
                    system_message="You are helpful",
                    user_message="Hello"
                )

            assert "API Error" in str(exc_info.value)


# =============================================================================
# KB Summary Helper Tests
# =============================================================================

class TestKBSummaryHelper:
    """Tests for the KB summary helper method."""

    def test_get_kb_summary(self, knowledge_services, mock_db_session):
        """Test getting KB summary."""
        # Mock the database calls
        mock_counts = Mock()
        mock_counts.doc_count = 10
        mock_counts.concept_count = 50

        mock_concepts = [
            Mock(name="Python", category="language", freq=5),
            Mock(name="FastAPI", category="framework", freq=3),
        ]

        mock_clusters = [
            Mock(name="Backend", primary_concepts=["Python", "FastAPI"]),
        ]

        mock_sources = [
            Mock(source_type="file", count=7),
            Mock(source_type="url", count=3),
        ]

        # Set up sequential mock returns
        call_count = [0]
        def mock_execute(query, params=None):
            result = Mock()
            if call_count[0] == 0:
                result.fetchone.return_value = mock_counts
            elif call_count[0] == 1:
                result.fetchall.return_value = mock_concepts
            elif call_count[0] == 2:
                result.fetchall.return_value = mock_clusters
            else:
                result.fetchall.return_value = mock_sources
            call_count[0] += 1
            return result

        mock_db_session.execute = mock_execute

        summary = knowledge_services._get_kb_summary("kb1")

        assert summary["document_count"] == 10
        assert summary["concept_count"] == 50
        assert len(summary["top_concepts"]) == 2
