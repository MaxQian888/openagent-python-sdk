"""Base LLM client contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator


@dataclass
class LLMChunk:
    """Streaming chunk from LLM."""

    type: str  # "content_block_delta", "message_stop", "error"
    delta: str | None = None  # Text delta
    content: dict | None = None  # Content block
    error: str | None = None


class LLMClient:
    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Complete a chat request synchronously.

        Args:
            messages: Chat messages
            model: Model name (optional, uses default if not specified)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text response
        """
        raise NotImplementedError

    async def complete_stream(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Complete a chat request with streaming.

        Args:
            messages: Chat messages
            model: Model name (optional)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Yields:
            LLMChunk objects with streaming content
        """
        # Default: fall back to non-streaming
        result = await self.complete(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        yield LLMChunk(type="content_block_delta", delta=result)
        yield LLMChunk(type="message_stop")

