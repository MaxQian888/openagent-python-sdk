"""Tests for llm registry and providers."""

import pytest

from openagents.config.schema import LLMOptions
from openagents.errors.exceptions import ConfigValidationError
from openagents.llm.registry import create_llm_client
from openagents.llm.providers.mock import MockLLMClient


def test_create_llm_client_mock():
    """Test creating a mock LLM client."""
    config = LLMOptions(provider="mock")
    client = create_llm_client(config)

    assert client is not None
    assert isinstance(client, MockLLMClient)


def test_create_llm_client_with_model():
    """Test creating a mock LLM client with model."""
    config = LLMOptions(provider="mock", model="gpt-4")
    client = create_llm_client(config)

    assert client is not None


def test_create_llm_client_unknown():
    """Test creating client with unknown provider raises error."""
    with pytest.raises(ConfigValidationError):
        LLMOptions(provider="unknown_provider")


@pytest.mark.asyncio
async def test_mock_llm_client_complete():
    """Test MockLLMClient complete method."""
    client = MockLLMClient()

    result = await client.complete(
        messages=[{"role": "user", "content": "Hello"}],
    )

    assert result is not None
    assert "Echo" in result


@pytest.mark.asyncio
async def test_mock_llm_client_complete_with_model():
    """Test MockLLMClient with model parameter."""
    client = MockLLMClient()

    result = await client.complete(
        messages=[{"role": "user", "content": "test"}],
        model="gpt-4",
    )

    assert result is not None


def test_create_llm_client_none():
    """Test creating client with None returns None."""
    client = create_llm_client(None)

    assert client is None


def test_mock_llm_client_parse_prompt():
    """Test MockLLMClient prompt parsing."""
    client = MockLLMClient()

    # Test basic parsing - needs INPUT: prefix
    result = client._parse_prompt("INPUT: Hello world")
    assert result == {"input": "Hello world", "history_count": 0}

    # Test with history
    text = "INPUT: New message\nHISTORY_COUNT: 3"
    result = client._parse_prompt(text)
    assert result["history_count"] == 3
