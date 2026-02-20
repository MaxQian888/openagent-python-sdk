"""Base LLM client contract."""

from __future__ import annotations

from typing import Any


class LLMClient:
    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        raise NotImplementedError

