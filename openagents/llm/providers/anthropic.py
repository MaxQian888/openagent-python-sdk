"""Anthropic-compatible LLM provider via HTTP API.

Supports:
- Anthropic API (api.anthropic.com)
- Anthropic-compatible APIs (e.g., LongCat, AWS Bedrock, etc.)
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from urllib import request

from openagents.llm.base import LLMClient


class AnthropicClient(LLMClient):
    """Anthropic-compatible LLM client.

    Usage:
        # Direct Anthropic
        provider: "anthropic"
        api_base: "https://api.anthropic.com"
        api_key_env: "ANTHROPIC_API_KEY"

        # LongCat (Anthropic-compatible)
        provider: "anthropic"
        api_base: "https://api.longcat.chat/anthropic/v1"
        api_key_env: "LONGCAT_API_KEY"
    """

    def __init__(
        self,
        *,
        api_base: str,
        model: str,
        api_key_env: str = "ANTHROPIC_API_KEY",
        timeout_ms: int = 30000,
        default_temperature: float | None = None,
        max_tokens: int = 1024,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.model = model
        self.api_key_env = api_key_env
        self.timeout_ms = timeout_ms
        self.default_temperature = default_temperature
        self.default_max_tokens = max_tokens

    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        chosen_model = model or self.model
        chosen_temp = self.default_temperature if temperature is None else temperature
        chosen_max_tokens = max_tokens or self.default_max_tokens

        # Convert OpenAI-style messages to Anthropic format
        anthropic_messages = []
        system_prompt = ""

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                # Anthropic uses system prompt separately
                system_prompt = content
            elif role in ("user", "assistant"):
                anthropic_messages.append({
                    "role": role,
                    "content": content,
                })

        payload: dict[str, Any] = {
            "model": chosen_model,
            "messages": anthropic_messages,
            "max_tokens": chosen_max_tokens,
        }

        if system_prompt:
            payload["system"] = system_prompt

        if chosen_temp is not None:
            payload["temperature"] = chosen_temp

        api_key = os.getenv(self.api_key_env, "")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }

        def _request_once() -> str:
            req = request.Request(
                url=f"{self.api_base}/messages",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            timeout_s = max(self.timeout_ms, 1) / 1000
            with request.urlopen(req, timeout=timeout_s) as resp:
                return resp.read().decode("utf-8")

        body = await asyncio.to_thread(_request_once)
        data = json.loads(body)

        # Parse Anthropic response
        content_blocks = data.get("content", [])
        if not content_blocks:
            return ""

        # Get text from first content block
        for block in content_blocks:
            if block.get("type") == "text":
                return block.get("text", "")

        return ""
