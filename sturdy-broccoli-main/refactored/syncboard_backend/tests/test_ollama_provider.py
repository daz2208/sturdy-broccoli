"""
Tests for Ollama LLM provider.

Tests the OllamaProvider class with mocked HTTP responses.
"""

import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))


# =============================================================================
# OllamaProvider Unit Tests
# =============================================================================

@pytest.mark.asyncio
async def test_ollama_provider_initialization():
    """Test OllamaProvider initialization with default and custom values."""
    from backend.llm_providers import OllamaProvider

    # Test default initialization
    with patch.dict('os.environ', {
        'OLLAMA_BASE_URL': 'http://localhost:11434',
        'OLLAMA_CONCEPT_MODEL': 'llama2',
        'OLLAMA_SUGGESTION_MODEL': 'mistral'
    }):
        provider = OllamaProvider()
        assert provider.base_url == 'http://localhost:11434'
        assert provider.concept_model == 'llama2'
        assert provider.suggestion_model == 'mistral'

    # Test custom initialization
    provider = OllamaProvider(
        base_url='http://custom:8080',
        concept_model='codellama',
        suggestion_model='mixtral'
    )
    assert provider.base_url == 'http://custom:8080'
    assert provider.concept_model == 'codellama'
    assert provider.suggestion_model == 'mixtral'


@pytest.mark.asyncio
async def test_ollama_extract_json_from_response():
    """Test JSON extraction from various Ollama response formats."""
    from backend.llm_providers import OllamaProvider

    provider = OllamaProvider()

    # Test plain JSON
    plain = '{"concepts": [{"name": "python", "category": "language"}]}'
    assert json.loads(provider._extract_json_from_response(plain)) == {
        "concepts": [{"name": "python", "category": "language"}]
    }

    # Test markdown code block
    markdown = '''Here's the extracted concepts:
```json
{"concepts": [{"name": "fastapi", "category": "framework"}]}
```
Let me know if you need more.'''
    result = provider._extract_json_from_response(markdown)
    assert json.loads(result) == {"concepts": [{"name": "fastapi", "category": "framework"}]}

    # Test JSON array
    array = '''I found these projects:
[{"title": "Project 1"}, {"title": "Project 2"}]'''
    result = provider._extract_json_from_response(array)
    assert json.loads(result) == [{"title": "Project 1"}, {"title": "Project 2"}]


@pytest.mark.asyncio
async def test_ollama_extract_concepts():
    """Test concept extraction with mocked Ollama response."""
    from backend.llm_providers import OllamaProvider

    provider = OllamaProvider()

    mock_response = {
        "message": {
            "content": json.dumps({
                "concepts": [
                    {"name": "python", "category": "language", "confidence": 0.95},
                    {"name": "fastapi", "category": "framework", "confidence": 0.9}
                ],
                "skill_level": "intermediate",
                "primary_topic": "web development",
                "suggested_cluster": "Backend Development"
            })
        }
    }

    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = mock_response
        mock_post_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_post_response

        mock_client_class.return_value = mock_client

        result = await provider.extract_concepts(
            "Python FastAPI tutorial for building REST APIs",
            "text"
        )

        assert len(result["concepts"]) == 2
        assert result["skill_level"] == "intermediate"
        assert result["primary_topic"] == "web development"


@pytest.mark.asyncio
async def test_ollama_generate_build_suggestions():
    """Test build suggestion generation with mocked Ollama response."""
    from backend.llm_providers import OllamaProvider

    provider = OllamaProvider()

    mock_response = {
        "message": {
            "content": json.dumps([
                {
                    "title": "Task Automation API",
                    "description": "Build a FastAPI service for task automation",
                    "feasibility": "high",
                    "effort_estimate": "3-5 days",
                    "required_skills": ["Python", "FastAPI"],
                    "missing_knowledge": [],
                    "starter_steps": ["Set up project", "Create models", "Build endpoints"]
                }
            ])
        }
    }

    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = mock_response
        mock_post_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_post_response

        mock_client_class.return_value = mock_client

        result = await provider.generate_build_suggestions(
            "User knows Python and FastAPI",
            3
        )

        assert len(result) == 1
        assert result[0]["title"] == "Task Automation API"
        assert result[0]["feasibility"] == "high"


@pytest.mark.asyncio
async def test_ollama_chat_completion():
    """Test generic chat completion with mocked Ollama response."""
    from backend.llm_providers import OllamaProvider

    provider = OllamaProvider()

    mock_response = {
        "message": {
            "content": "Hello! I'm here to help you with your coding questions."
        }
    }

    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = mock_response
        mock_post_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_post_response

        mock_client_class.return_value = mock_client

        result = await provider.chat_completion([
            {"role": "user", "content": "Hello!"}
        ])

        assert "Hello" in result


@pytest.mark.asyncio
async def test_ollama_connection_error_handling():
    """Test handling of connection errors to Ollama."""
    from backend.llm_providers import OllamaProvider
    import httpx

    provider = OllamaProvider()

    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")

        mock_client_class.return_value = mock_client

        # Should return fallback values instead of crashing
        result = await provider.extract_concepts("test content", "text")

        assert result["concepts"] == []
        assert result["skill_level"] == "unknown"


# =============================================================================
# Provider Factory Tests
# =============================================================================

def test_get_llm_provider_factory():
    """Test the LLM provider factory function."""
    from backend.llm_providers import get_llm_provider, OpenAIProvider, OllamaProvider, MockLLMProvider

    # Test OpenAI provider
    with patch.dict('os.environ', {'LLM_PROVIDER': 'openai', 'OPENAI_API_KEY': 'test-key'}):
        provider = get_llm_provider()
        assert isinstance(provider, OpenAIProvider)

    # Test Ollama provider
    with patch.dict('os.environ', {'LLM_PROVIDER': 'ollama'}):
        provider = get_llm_provider()
        assert isinstance(provider, OllamaProvider)

    # Test Mock provider
    with patch.dict('os.environ', {'LLM_PROVIDER': 'mock'}):
        provider = get_llm_provider()
        assert isinstance(provider, MockLLMProvider)

    # Test override parameter
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        provider = get_llm_provider("openai")
        assert isinstance(provider, OpenAIProvider)

    provider = get_llm_provider("mock")
    assert isinstance(provider, MockLLMProvider)


def test_get_llm_provider_invalid():
    """Test factory with invalid provider type."""
    from backend.llm_providers import get_llm_provider

    with pytest.raises(ValueError) as exc_info:
        get_llm_provider("invalid_provider")

    assert "Unknown LLM provider" in str(exc_info.value)
