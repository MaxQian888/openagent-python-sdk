"""Anthropic-compatible LLM provider via HTTP API.

Supports:
- Anthropic API (api.anthropic.com)
- Anthropic-compatible APIs (e.g., LongCat, AWS Bedrock, MiniMax, etc.)

Streaming is implemented with httpx SSE; non-streaming uses urllib for
minimal dependencies.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, AsyncIterator

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

from openagents.llm.base import LLMChunk, LLMClient


class AnthropicClient(LLMClient):
    """Anthropic-compatible LLM client.

    Usage:
        # Direct Anthropic
        provider: "anthropic"
        api_base: "https://api.anthropic.com"
        api_key_env: "ANTHROPIC_API_KEY"

        # Anthropic-compatible gateways
        provider: "anthropic"
        api_base: "https://api.minimaxi.com/anthropic"
        api_key_env: "MINIMAX_API_KEY"
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
        stream_endpoint: str | None = None,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.model = model
        self.api_key_env = api_key_env
        self.timeout_ms = timeout_ms
        self.default_temperature = default_temperature
        self.default_max_tokens = max_tokens
        self._stream_endpoint = stream_endpoint

    def _messages_endpoint(self) -> str:
        if self.api_base.endswith("/v1"):
            return f"{self.api_base}/messages"
        return f"{self.api_base}/v1/messages"

    def _stream_endpoint_url(self) -> str:
        """Streaming URL — defaults to _messages_endpoint but can be overridden."""
        if self._stream_endpoint:
            return self._stream_endpoint
        return self._messages_endpoint()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_payload(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], str]:
        chosen_model = model or self.model
        chosen_temp = self.default_temperature if temperature is None else temperature
        chosen_max_tokens = max_tokens or self.default_max_tokens

        anthropic_messages: list[dict[str, Any]] = []
        system_prompt = ""

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
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

        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice

        if stream:
            payload["stream"] = True

        api_key = os.getenv(self.api_key_env, "")

        # MiniMax-compatible: send both headers; some gateways require x-api-key
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }

        return payload, headers

    def _parse_sse_event(self, raw: bytes) -> tuple[str | None, str | None]:
        """Parse one SSE record.

        Handles two formats:
        - Anthropic:  'event: <type>\\ndata: <json>\\n\\n'
        - OpenAI:     'data: <json>\\n\\n'

        Returns (event_type, json_data_string) or (None, None) for empty/invalid.
        """
        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            return None, None

        # Some gateways return a single JSON body instead of SSE frames even when
        # the request asked for streaming. Preserve it so the caller can surface
        # a structured error instead of silently yielding nothing.
        if text.startswith("{") or text.startswith("["):
            return None, text

        # Strip SSE "data: " prefix if present (OpenAI /chat/completions format)
        if text.startswith("data:"):
            # Single-line OpenAI format: "data: {...}"
            data_str = text[5:].strip()
            # OpenAI streaming: no event type, data is the full JSON
            return None, data_str

        # Multi-line SSE format (Anthropic-style)
        event_type: str | None = None
        data_str: str | None = None

        for line in text.split("\n"):
            line = line.rstrip("\r")
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_str = line[5:].strip()

        return event_type, data_str

    def _extract_stream_error(self, data: dict[str, Any]) -> str | None:
        error = data.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message
            return json.dumps(error, ensure_ascii=False)
        if isinstance(error, str) and error.strip():
            return error

        base_resp = data.get("base_resp")
        if isinstance(base_resp, dict):
            status_code = base_resp.get("status_code")
            if status_code not in (None, 0, 200):
                status_msg = base_resp.get("status_msg")
                if isinstance(status_msg, str) and status_msg.strip():
                    return status_msg
                return json.dumps(base_resp, ensure_ascii=False)

        return None

    # ------------------------------------------------------------------
    # Non-streaming
    # ------------------------------------------------------------------

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | None = None,
    ) -> str:
        from urllib import request as urllib_request

        payload, headers = self._build_payload(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            tools=tools,
            tool_choice=tool_choice,
        )

        def _request_once() -> str:
            req = urllib_request.Request(
                url=self._messages_endpoint(),
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            timeout_s = max(self.timeout_ms, 1) / 1000
            with urllib_request.urlopen(req, timeout=timeout_s) as resp:
                return resp.read().decode("utf-8")

        body = await asyncio.to_thread(_request_once)
        data = json.loads(body)

        content_blocks = data.get("content", [])
        if not content_blocks:
            return ""

        for block in content_blocks:
            if block.get("type") == "text":
                return block.get("text", "")

        return ""

    # ------------------------------------------------------------------
    # Streaming (httpx SSE)
    # ------------------------------------------------------------------

    async def complete_stream(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | None = None,
    ) -> AsyncIterator[LLMChunk]:
        if httpx is None:
            raise RuntimeError(
                "httpx is required for streaming. "
                "Install with: pip install httpx"
            )

        payload, headers = self._build_payload(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            tools=tools,
            tool_choice=tool_choice,
        )

        # Streaming: use long read timeout (model may stream tokens over minutes)
        connect_s = max(self.timeout_ms, 1) / 1000
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect_s, read=120.0),
        ) as client:
            async with client.stream(
                "POST",
                self._stream_endpoint_url(),
                json=payload,
                headers=headers,
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    error_text = body.decode("utf-8", errors="replace")
                    yield LLMChunk(
                        type="error",
                        error=f"HTTP {response.status_code}: {error_text[:500]}",
                    )
                    return

                # SSE parsing: each chunk from the stream is one SSE "record"
                # (ending with \n\n).  We may receive partial records across
                # httpx chunks, so accumulate in a buffer.
                buffer = b""

                async for chunk in response.aiter_bytes():
                    buffer += chunk
                    # Process all complete SSE records (\n\n)
                    while b"\n\n" in buffer:
                        record, buffer = buffer.split(b"\n\n", 1)
                        event_type, data_str = self._parse_sse_event(record)
                        if data_str is None:
                            continue

                        # Parse JSON data
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        # ── OpenAI /chat/completions format (MiniMax) ──────────────
                        # No event_type → OpenAI SSE: data = {"id", "choices":[{"delta":{"content"}}]}
                        if event_type is None and "choices" in data:
                            choices = data.get("choices", [])
                            for choice in choices:
                                delta = choice.get("delta", {})
                                content_text = delta.get("content", "")
                                finish = choice.get("finish_reason", "")
                                if content_text:
                                    yield LLMChunk(
                                        type="content_block_delta",
                                        delta={"type": "text_delta", "text": content_text},
                                        content={"type": "text", "text": content_text},
                                    )
                                if finish and finish not in (None, "null"):
                                    yield LLMChunk(type="message_stop", content={"stop_reason": finish})
                            continue

                        error_text = self._extract_stream_error(data)
                        if error_text:
                            yield LLMChunk(type="error", error=error_text)
                            return

                        # ── Anthropic SSE format ────────────────────────────────────
                        if event_type is None:
                            continue

                        # Map Anthropic SSE event → LLMChunk
                        if event_type == "message_start":
                            yield LLMChunk(type="message_start", content=data)
                        elif event_type == "content_block_start":
                            yield LLMChunk(
                                type="content_block_start",
                                content=data.get("content_block", data),
                            )
                        elif event_type == "content_block_delta":
                            delta = data.get("delta", {})
                            yield LLMChunk(
                                type="content_block_delta",
                                delta=delta,
                                content=data,
                            )
                        elif event_type == "content_block_stop":
                            yield LLMChunk(type="content_block_stop", content=data)
                        elif event_type == "ping":
                            pass  # MiniMax keep-alive ping; ignore
                        elif event_type == "message_delta":
                            yield LLMChunk(type="message_delta", content=data)
                        elif event_type == "message_stop":
                            yield LLMChunk(type="message_stop", content=data)
                        elif event_type == "error":
                            yield LLMChunk(
                                type="error",
                                error=data.get("error", {}).get("message", str(data)),
                            )

                if buffer.strip():
                    event_type, data_str = self._parse_sse_event(buffer)
                    if data_str is not None:
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            data = None

                        if isinstance(data, dict):
                            if event_type is None and "choices" in data:
                                choices = data.get("choices", [])
                                for choice in choices:
                                    delta = choice.get("delta", {})
                                    content_text = delta.get("content", "")
                                    finish = choice.get("finish_reason", "")
                                    if content_text:
                                        yield LLMChunk(
                                            type="content_block_delta",
                                            delta={"type": "text_delta", "text": content_text},
                                            content={"type": "text", "text": content_text},
                                        )
                                    if finish and finish not in (None, "null"):
                                        yield LLMChunk(
                                            type="message_stop",
                                            content={"stop_reason": finish},
                                        )
                            else:
                                error_text = self._extract_stream_error(data)
                                if error_text:
                                    yield LLMChunk(type="error", error=error_text)
