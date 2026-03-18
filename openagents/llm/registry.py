"""LLM client factory."""

from __future__ import annotations

from openagents.config.schema import LLMOptions
from openagents.errors.exceptions import ConfigError
from openagents.llm.base import LLMClient
from openagents.llm.providers.anthropic import AnthropicClient
from openagents.llm.providers.mock import MockLLMClient
from openagents.llm.providers.openai_compatible import OpenAICompatibleClient


def create_llm_client(llm: LLMOptions | None) -> LLMClient | None:
    if llm is None:
        return None

    provider = llm.provider
    if provider == "mock":
        return MockLLMClient()

    if provider == "anthropic":
        if not llm.api_base:
            api_base = "https://api.anthropic.com"
        else:
            api_base = llm.api_base
        return AnthropicClient(
            api_base=api_base,
            model=llm.model or "claude-3-haiku-20240307",
            api_key_env=llm.api_key_env or "ANTHROPIC_API_KEY",
            timeout_ms=llm.timeout_ms,
            default_temperature=llm.temperature,
            max_tokens=llm.max_tokens or 1024,
        )

    if provider == "openai_compatible":
        if not llm.api_base:
            raise ConfigError("llm.api_base is required for provider 'openai_compatible'")
        return OpenAICompatibleClient(
            api_base=llm.api_base,
            model=llm.model or "gpt-4o-mini",
            api_key_env=llm.api_key_env or "OPENAI_API_KEY",
            timeout_ms=llm.timeout_ms,
            default_temperature=llm.temperature,
        )

    raise ConfigError(f"Unsupported llm.provider: '{provider}'")

