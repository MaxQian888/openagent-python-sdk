"""OpenAI-compatible LLM provider via HTTP API."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from urllib import request

from openagents.llm.base import LLMClient


class OpenAICompatibleClient(LLMClient):
    def __init__(
        self,
        *,
        api_base: str,
        model: str,
        api_key_env: str = "OPENAI_API_KEY",
        timeout_ms: int = 30000,
        default_temperature: float | None = None,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.model = model
        self.api_key_env = api_key_env
        self.timeout_ms = timeout_ms
        self.default_temperature = default_temperature

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

        payload: dict[str, Any] = {
            "model": chosen_model,
            "messages": messages,
        }
        if chosen_temp is not None:
            payload["temperature"] = chosen_temp
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        api_key = os.getenv(self.api_key_env, "")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        def _request_once() -> str:
            req = request.Request(
                url=f"{self.api_base}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            timeout_s = max(self.timeout_ms, 1) / 1000
            with request.urlopen(req, timeout=timeout_s) as resp:
                return resp.read().decode("utf-8")

        body = await asyncio.to_thread(_request_once)
        data = json.loads(body)
        choices = data.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, list):
            chunks = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    chunks.append(str(item.get("text", "")))
            return "".join(chunks)
        return str(content)
