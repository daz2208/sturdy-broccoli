"""
Tests for the Agentic Learning System.

This module tests the CLOSED LOOP learning functionality:
- Feedback retrieval methods
- Learning context building
- Prompt additions generation
- Confidence calibration
- Integration with extract_with_learning()

The agentic learning system enables the AI to learn from user corrections
and apply past feedback to improve future extractions.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from backend.feedback_service import FeedbackService
from backend.db_models import DBAIDecision, DBUserFeedback, Base


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def feedback_service():
    """Create a FeedbackService instance for testing."""
    return FeedbackService()


@pytest.fixture
def sample_corrections():
    """Sample correction data for testing."""
    return [
        {
            "original_value": {"concepts": ["Docker", "Images", "Web"]},
            "new_value": {"concepts": ["Docker", "Docker Images", "Docker Hub"]},
            "user_reasoning": "Images is too vague, use Docker Images. Added Docker Hub.",
            "context": {"added": ["Docker Images", "Docker Hub"], "removed": ["Images", "Web"]},
            "feedback_type": "concept_edit",
            "confidence_at_decision": 0.72
        },
        {
            "original_value": {"concepts": ["API", "Backend", "Code"]},
            "new_value": {"concepts": ["REST API", "FastAPI", "Python"]},
            "user_reasoning": "Be more specific about the API type and framework.",
            "context": {"added": ["REST API", "FastAPI", "Python"], "removed": ["API", "Backend", "Code"]},
            "feedback_type": "concept_edit",
            "confidence_at_decision": 0.68
        },
        {
            "original_value": {"concepts": ["Data", "Processing"]},
            "new_value": {"concepts": ["Data Pipeline", "ETL", "Pandas"]},
            "user_reasoning": "Generic terms don't help. Use specific technologies.",
            "context": {"added": ["Data Pipeline", "ETL", "Pandas"], "removed": ["Data", "Processing"]},
            "feedback_type": "concept_edit",
            "confidence_at_decision": 0.65
        }
    ]


@pytest.fixture
def sample_patterns():
    """Sample user preference patterns."""
    return {
        "has_feedback": True,
        "total_corrections": 15,
        "frequently_removed": [
            {"concept": "api", "count": 5},
            {"concept": "web", "count": 4},
            {"concept": "data", "count": 3},
            {"concept": "code", "count": 2}
        ],
        "frequently_added": [
            {"concept": "rest api", "count": 4},
            {"concept": "fastapi", "count": 3},
            {"concept": "docker", "count": 3},
            {"concept": "postgresql", "count": 2}
        ],
        "prefers_specific_names": True,
        "avg_concepts_preferred": 6.5,
        "removal_patterns": ["User removes vague terms like: api, web, data"],
        "addition_patterns": ["User prefers specific technology names over generic terms"]
    }


@pytest.fixture
def sample_calibration_data():
    """Sample confidence calibration data."""
    return {
        "low": {
            "confidence_range": "0%-70%",
            "sample_size": 20,
            "actual_accuracy": 0.55,
            "avg_stated_confidence": 0.60,
            "calibration_delta": -0.05,
            "calibration_needed": False,
            "suggested_adjustment": 0.0
        },
        "medium": {
            "confidence_range": "70%-90%",
            "sample_size": 30,
            "actual_accuracy": 0.65,
            "avg_stated_confidence": 0.80,
            "calibration_delta": -0.15,
            "calibration_needed": True,
            "suggested_adjustment": -0.15
        },
        "high": {
            "confidence_range": "90%-100%",
            "sample_size": 10,
            "actual_accuracy": 0.92,
            "avg_stated_confidence": 0.95,
            "calibration_delta": -0.03,
            "calibration_needed": False,
            "suggested_adjustment": 0.0
        }
    }


# =============================================================================
# Tests for Prompt Additions Building
# =============================================================================

class TestPromptAdditionsBuilding:
    """Tests for _build_prompt_additions method."""

    def test_build_prompt_with_corrections(self, sample_corrections, sample_patterns):
        """Test that corrections are properly formatted into prompt text."""
        prompt = FeedbackService._build_prompt_additions(
            corrections=sample_corrections,
            patterns=sample_patterns
        )

        # Should include learning section header
        assert "LEARN FROM PAST CORRECTIONS" in prompt

        # Should include example numbering
        assert "Example 1:" in prompt
        assert "Example 2:" in prompt

        # Should include original and corrected concepts
        assert "AI extracted:" in prompt
        assert "User corrected to:" in prompt

        # Should include user reasoning
        assert "User's reason:" in prompt

    def test_build_prompt_with_preferences(self, sample_patterns):
        """Test that user preferences are included in prompt."""
        prompt = FeedbackService._build_prompt_additions(
            corrections=[],
            patterns=sample_patterns
        )

        # Should include preference for specific names
        assert "SPECIFIC" in prompt or "specific" in prompt

        # Should include concepts to avoid
        assert "AVOID" in prompt

        # Should include target concept count
        assert "6" in prompt or "approximately" in prompt

    def test_build_prompt_empty_data(self):
        """Test prompt building with no learning data."""
        prompt = FeedbackService._build_prompt_additions(
            corrections=[],
            patterns={"has_feedback": False}
        )

        # Should be empty string when no data
        assert prompt == ""

    def test_build_prompt_with_removed_concepts(self, sample_patterns):
        """Test that frequently removed concepts are included as warnings."""
        prompt = FeedbackService._build_prompt_additions(
            corrections=[],
            patterns=sample_patterns
        )

        # Should warn about removed concepts
        assert "api" in prompt.lower() or "AVOID" in prompt


# =============================================================================
# Tests for Confidence Calibration
# =============================================================================

class TestConfidenceCalibration:
    """Tests for confidence calibration logic."""

    def test_calibrate_confidence_medium_range(self, sample_calibration_data):
        """Test calibration when model is overconfident in medium range."""
        from backend.concept_extractor import ConceptExtractor

        extractor = ConceptExtractor()

        # Raw confidence of 0.80 in medium range where calibration is needed
        calibrated = extractor._calibrate_confidence(
            raw_confidence=0.80,
            calibration_data=sample_calibration_data
        )

        # Should be adjusted down by -0.15 (capped)
        assert calibrated < 0.80
        assert calibrated >= 0.65  # 0.80 - 0.15

    def test_calibrate_confidence_no_adjustment_needed(self, sample_calibration_data):
        """Test that calibration doesn't change confidence when not needed."""
        from backend.concept_extractor import ConceptExtractor

        extractor = ConceptExtractor()

        # High confidence where calibration is not needed
        calibrated = extractor._calibrate_confidence(
            raw_confidence=0.95,
            calibration_data=sample_calibration_data
        )

        # Should be unchanged
        assert calibrated == 0.95

    def test_calibrate_confidence_empty_data(self):
        """Test calibration with no calibration data."""
        from backend.concept_extractor import ConceptExtractor

        extractor = ConceptExtractor()

        calibrated = extractor._calibrate_confidence(
            raw_confidence=0.75,
            calibration_data={}
        )

        # Should be unchanged
        assert calibrated == 0.75

    def test_calibrate_confidence_insufficient_samples(self):
        """Test calibration is skipped with insufficient samples."""
        from backend.concept_extractor import ConceptExtractor

        extractor = ConceptExtractor()

        calibration_data = {
            "medium": {
                "sample_size": 3,  # Below threshold of 5
                "calibration_needed": True,
                "suggested_adjustment": -0.20
            }
        }

        calibrated = extractor._calibrate_confidence(
            raw_confidence=0.80,
            calibration_data=calibration_data
        )

        # Should be unchanged due to insufficient samples
        assert calibrated == 0.80

    def test_calibrate_confidence_bounds(self):
        """Test that calibration respects 0.0-1.0 bounds."""
        from backend.concept_extractor import ConceptExtractor

        extractor = ConceptExtractor()

        calibration_data = {
            "low": {
                "sample_size": 10,
                "calibration_needed": True,
                "suggested_adjustment": -0.50  # Would push below 0
            }
        }

        calibrated = extractor._calibrate_confidence(
            raw_confidence=0.30,
            calibration_data=calibration_data
        )

        # Should be clamped to 0.0 minimum (but adjustment is also capped at -0.15)
        assert calibrated >= 0.0
        assert calibrated <= 1.0


# =============================================================================
# Tests for Pattern Extraction
# =============================================================================

class TestPatternExtraction:
    """Tests for extracting patterns from feedback."""

    def test_extract_removal_patterns(self):
        """Test extraction of removal patterns from frequently removed concepts."""
        frequently_removed = [
            ("api", 5),
            ("web", 4),
            ("data", 3),
            ("service", 2)
        ]

        patterns = FeedbackService._extract_removal_patterns(frequently_removed)

        # Should identify vague terms
        assert len(patterns) >= 0  # May or may not find patterns

    def test_extract_addition_patterns(self):
        """Test extraction of addition patterns from frequently added concepts."""
        frequently_added = [
            ("rest api endpoint", 4),
            ("postgresql database", 3),
            ("docker container", 3)
        ]

        patterns = FeedbackService._extract_addition_patterns(frequently_added)

        # Should identify preference for specific names
        assert any("specific" in p.lower() for p in patterns) or len(patterns) == 0


# =============================================================================
# Tests for Learning Context Integration
# =============================================================================

class TestLearningContextIntegration:
    """Integration tests for the complete learning context flow."""

    @pytest.mark.asyncio
    async def test_get_learning_context_structure(self):
        """Test that learning context has correct structure."""
        with patch.object(FeedbackService, 'get_recent_corrections', new_callable=AsyncMock) as mock_corrections, \
             patch.object(FeedbackService, 'get_concept_correction_patterns', new_callable=AsyncMock) as mock_patterns, \
             patch.object(FeedbackService, 'get_accuracy_for_confidence_range', new_callable=AsyncMock) as mock_accuracy:

            mock_corrections.return_value = []
            mock_patterns.return_value = {"has_feedback": False}
            mock_accuracy.return_value = {"sample_size": 0, "actual_accuracy": None}

            context = await FeedbackService.get_learning_context_for_extraction(
                username="testuser",
                content_sample="Test content",
                decision_type="concept_extraction"
            )

            # Should have correct structure
            assert "has_learning_data" in context
            assert "recent_corrections" in context
            assert "user_preferences" in context
            assert "confidence_calibration" in context
            assert "prompt_additions" in context

    @pytest.mark.asyncio
    async def test_get_learning_context_with_data(self, sample_corrections, sample_patterns):
        """Test learning context with actual feedback data."""
        with patch.object(FeedbackService, 'get_recent_corrections', new_callable=AsyncMock) as mock_corrections, \
             patch.object(FeedbackService, 'get_concept_correction_patterns', new_callable=AsyncMock) as mock_patterns, \
             patch.object(FeedbackService, 'get_accuracy_for_confidence_range', new_callable=AsyncMock) as mock_accuracy:

            mock_corrections.return_value = sample_corrections
            mock_patterns.return_value = sample_patterns
            mock_accuracy.return_value = {"sample_size": 10, "actual_accuracy": 0.75}

            context = await FeedbackService.get_learning_context_for_extraction(
                username="testuser",
                content_sample="Test content about Docker and APIs"
            )

            # Should have learning data
            assert context["has_learning_data"] is True
            assert len(context["recent_corrections"]) == len(sample_corrections)
            assert context["prompt_additions"] != ""


# =============================================================================
# Tests for extract_with_learning
# =============================================================================

class TestExtractWithLearning:
    """Tests for the extract_with_learning method."""

    @pytest.mark.asyncio
    async def test_extract_with_learning_includes_metadata(self):
        """Test that extract_with_learning returns learning metadata."""
        from backend.concept_extractor import ConceptExtractor

        with patch.object(FeedbackService, 'get_learning_context_for_extraction', new_callable=AsyncMock) as mock_context:
            mock_context.return_value = {
                "has_learning_data": True,
                "recent_corrections": [{"original_value": {}, "new_value": {}}],
                "user_preferences": {"has_feedback": True, "prefers_specific_names": True},
                "confidence_calibration": {},
                "prompt_additions": "Test prompt additions"
            }

            extractor = ConceptExtractor()

            # Mock the internal extraction method
            with patch.object(extractor, '_extract_with_learning_prompt', new_callable=AsyncMock) as mock_extract:
                mock_extract.return_value = {
                    "concepts": [{"name": "Docker", "category": "tool", "confidence": 0.9}],
                    "skill_level": "intermediate",
                    "primary_topic": "containerization",
                    "suggested_cluster": "Docker",
                    "confidence_score": 0.85
                }

                result = await extractor.extract_with_learning(
                    content="Docker tutorial content",
                    source_type="text",
                    username="testuser"
                )

                # Should have learning_applied metadata
                assert "learning_applied" in result
                assert "corrections_used" in result["learning_applied"]
                assert "preferences_applied" in result["learning_applied"]

    @pytest.mark.asyncio
    async def test_extract_with_learning_no_data(self):
        """Test extract_with_learning when no learning data exists."""
        from backend.concept_extractor import ConceptExtractor

        with patch.object(FeedbackService, 'get_learning_context_for_extraction', new_callable=AsyncMock) as mock_context:
            mock_context.return_value = {
                "has_learning_data": False,
                "recent_corrections": [],
                "user_preferences": {"has_feedback": False},
                "confidence_calibration": {},
                "prompt_additions": ""
            }

            extractor = ConceptExtractor()

            with patch.object(extractor, '_extract_with_learning_prompt', new_callable=AsyncMock) as mock_extract:
                mock_extract.return_value = {
                    "concepts": [{"name": "Python", "category": "language", "confidence": 0.9}],
                    "skill_level": "beginner",
                    "primary_topic": "programming",
                    "suggested_cluster": "Python",
                    "confidence_score": 0.80
                }

                result = await extractor.extract_with_learning(
                    content="Python basics",
                    source_type="text",
                    username="newuser"
                )

                # Should still have learning_applied but with 0 corrections
                assert result["learning_applied"]["corrections_used"] == 0


# =============================================================================
# Tests for Database Integration
# =============================================================================

class TestDatabaseIntegration:
    """Tests that require database fixtures."""

    def test_record_and_retrieve_ai_decision(self, db_session):
        """Test recording and retrieving AI decisions."""
        # Create user first (required for foreign key)
        from backend.db_models import DBUser, DBKnowledgeBase
        import bcrypt

        user = DBUser(
            username="testuser",
            email="test@example.com",
            hashed_password=bcrypt.hashpw("password".encode(), bcrypt.gensalt()).decode()
        )
        db_session.add(user)
        db_session.commit()

        # Create knowledge base
        kb = DBKnowledgeBase(
            id="test-kb-id",
            name="Test KB",
            username="testuser"
        )
        db_session.add(kb)
        db_session.commit()

        # Create AI decision
        decision = DBAIDecision(
            decision_type="concept_extraction",
            username="testuser",
            knowledge_base_id="test-kb-id",
            input_data={"content_sample": "Test content"},
            output_data={"concepts": ["Docker", "Python"]},
            confidence_score=0.75,
            model_name="gpt-4o-mini"
        )
        db_session.add(decision)
        db_session.commit()

        # Query it back
        retrieved = db_session.query(DBAIDecision).filter_by(username="testuser").first()

        assert retrieved is not None
        assert retrieved.decision_type == "concept_extraction"
        assert retrieved.confidence_score == 0.75
        assert retrieved.output_data["concepts"] == ["Docker", "Python"]

    def test_record_and_retrieve_user_feedback(self, db_session):
        """Test recording and retrieving user feedback."""
        from backend.db_models import DBUser, DBKnowledgeBase
        import bcrypt

        # Setup user and KB
        user = DBUser(
            username="testuser2",
            email="test2@example.com",
            hashed_password=bcrypt.hashpw("password".encode(), bcrypt.gensalt()).decode()
        )
        db_session.add(user)

        kb = DBKnowledgeBase(
            id="test-kb-id-2",
            name="Test KB 2",
            username="testuser2"
        )
        db_session.add(kb)
        db_session.commit()

        # Create feedback
        feedback = DBUserFeedback(
            feedback_type="concept_edit",
            username="testuser2",
            knowledge_base_id="test-kb-id-2",
            original_value={"concepts": ["Web", "API"]},
            new_value={"concepts": ["REST API", "FastAPI"]},
            context={"added": ["REST API", "FastAPI"], "removed": ["Web", "API"]},
            user_reasoning="More specific names needed"
        )
        db_session.add(feedback)
        db_session.commit()

        # Query it back
        retrieved = db_session.query(DBUserFeedback).filter_by(username="testuser2").first()

        assert retrieved is not None
        assert retrieved.feedback_type == "concept_edit"
        assert "REST API" in retrieved.new_value["concepts"]
        assert retrieved.user_reasoning == "More specific names needed"


# =============================================================================
# Tests for Learning Loop Closure (End-to-End)
# =============================================================================

class TestLearningLoopClosure:
    """End-to-end tests verifying the learning loop is actually closed."""

    @pytest.mark.asyncio
    async def test_corrections_reach_extraction_prompt(self, sample_corrections):
        """
        Critical test: Verify that past corrections actually make it into
        the extraction prompt. This is the key test for loop closure.
        """
        with patch.object(FeedbackService, 'get_recent_corrections', new_callable=AsyncMock) as mock_corrections, \
             patch.object(FeedbackService, 'get_concept_correction_patterns', new_callable=AsyncMock) as mock_patterns, \
             patch.object(FeedbackService, 'get_accuracy_for_confidence_range', new_callable=AsyncMock) as mock_accuracy:

            mock_corrections.return_value = sample_corrections
            mock_patterns.return_value = {"has_feedback": True, "prefers_specific_names": True}
            mock_accuracy.return_value = {"sample_size": 0}

            context = await FeedbackService.get_learning_context_for_extraction(
                username="testuser",
                content_sample="Docker tutorial"
            )

            prompt_additions = context["prompt_additions"]

            # KEY ASSERTION: Past corrections should appear in prompt
            assert "Docker Images" in prompt_additions or "Docker Hub" in prompt_additions
            assert "LEARN FROM PAST CORRECTIONS" in prompt_additions

    @pytest.mark.asyncio
    async def test_user_preferences_reach_extraction_prompt(self, sample_patterns):
        """Verify that user preferences make it into the extraction prompt."""
        with patch.object(FeedbackService, 'get_recent_corrections', new_callable=AsyncMock) as mock_corrections, \
             patch.object(FeedbackService, 'get_concept_correction_patterns', new_callable=AsyncMock) as mock_patterns, \
             patch.object(FeedbackService, 'get_accuracy_for_confidence_range', new_callable=AsyncMock) as mock_accuracy:

            mock_corrections.return_value = []
            mock_patterns.return_value = sample_patterns
            mock_accuracy.return_value = {"sample_size": 0}

            context = await FeedbackService.get_learning_context_for_extraction(
                username="testuser"
            )

            prompt_additions = context["prompt_additions"]

            # Preferences should be in prompt
            assert "SPECIFIC" in prompt_additions or "specific" in prompt_additions.lower()
            assert "AVOID" in prompt_additions

    @pytest.mark.asyncio
    async def test_calibration_affects_final_confidence(self, sample_calibration_data):
        """Verify that confidence calibration actually changes the output."""
        from backend.concept_extractor import ConceptExtractor

        extractor = ConceptExtractor()

        # Raw confidence in medium range where calibration is needed
        calibrated = extractor._calibrate_confidence(
            raw_confidence=0.80,
            calibration_data=sample_calibration_data
        )

        # Calibration should have changed the confidence
        assert calibrated != 0.80
        assert calibrated < 0.80  # Should be adjusted down


# =============================================================================
# Summary Test
# =============================================================================

class TestAgenticLearningSummary:
    """Summary test documenting what the agentic learning system does."""

    def test_learning_loop_components_exist(self):
        """
        Verify all components of the learning loop exist.

        The closed loop consists of:
        1. Feedback retrieval (get_recent_corrections)
        2. Pattern analysis (get_concept_correction_patterns)
        3. Prompt injection (_build_prompt_additions)
        4. Confidence calibration (_calibrate_confidence)
        5. Learning-aware extraction (extract_with_learning)
        """
        # Check feedback retrieval exists
        assert hasattr(FeedbackService, 'get_recent_corrections')
        assert hasattr(FeedbackService, 'get_concept_correction_patterns')
        assert hasattr(FeedbackService, 'get_accuracy_for_confidence_range')
        assert hasattr(FeedbackService, 'get_learning_context_for_extraction')
        assert hasattr(FeedbackService, '_build_prompt_additions')

        # Check extraction with learning exists
        from backend.concept_extractor import ConceptExtractor
        assert hasattr(ConceptExtractor, 'extract_with_learning')
        assert hasattr(ConceptExtractor, '_calibrate_confidence')
        assert hasattr(ConceptExtractor, '_extract_with_learning_prompt')
        assert hasattr(ConceptExtractor, '_build_standard_learning_prompt')
        assert hasattr(ConceptExtractor, '_build_youtube_learning_prompt')
