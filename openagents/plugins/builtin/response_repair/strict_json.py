"""Strict-JSON response repair policy."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel

from openagents.interfaces.response_repair import ResponseRepairDecision, ResponseRepairPolicyPlugin
from openagents.plugins.builtin.response_repair.basic import BasicResponseRepairPolicy


_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*\n?(.*?)\n?```", re.DOTALL)


def _extract_balanced(text: str) -> str | None:
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return None


class StrictJsonResponseRepairPolicy(ResponseRepairPolicyPlugin):
    """Salvage JSON from assistant text blocks; optionally delegate to Basic on miss."""

    class Config(BaseModel):
        min_text_length: int = 8
        strip_code_fence: bool = True
        fallback_to_basic: bool = True

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities=set())
        cfg = self.Config.model_validate(self.config)
        self._min_len = cfg.min_text_length
        self._strip_fence = cfg.strip_code_fence
        self._fallback_to_basic = cfg.fallback_to_basic
        self._basic = BasicResponseRepairPolicy() if self._fallback_to_basic else None

    def _collect_text(self, blocks: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for block in blocks or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                t = block.get("text")
                if isinstance(t, str):
                    parts.append(t)
        return "\n".join(parts)

    async def repair_empty_response(
        self,
        *,
        context: Any,
        messages: list[dict[str, Any]],
        assistant_content: list[dict[str, Any]],
        stop_reason: str | None,
        retries: int,
    ) -> ResponseRepairDecision | None:
        text = self._collect_text(assistant_content)
        if len(text) < self._min_len:
            return await self._miss(context, messages, assistant_content, stop_reason, retries)

        candidate: str | None = None
        salvaged_from: str | None = None
        if self._strip_fence:
            match = _FENCE_RE.search(text)
            if match:
                candidate = match.group(1).strip()
                salvaged_from = "fenced_code"
        if candidate is None:
            extracted = _extract_balanced(text)
            if extracted is not None:
                candidate = extracted
                salvaged_from = "bare_json"

        if candidate is not None:
            try:
                obj = json.loads(candidate)
            except json.JSONDecodeError:
                obj = None
            if obj is not None:
                keys = list(obj.keys()) if isinstance(obj, dict) else []
                return ResponseRepairDecision(
                    status="repaired",
                    output=[{"type": "text", "text": json.dumps(obj, ensure_ascii=False)}],
                    metadata={"salvaged_from": salvaged_from, "keys": keys},
                )

        return await self._miss(context, messages, assistant_content, stop_reason, retries)

    async def _miss(self, context, messages, assistant_content, stop_reason, retries):
        if self._basic is not None:
            return await self._basic.repair_empty_response(
                context=context,
                messages=messages,
                assistant_content=assistant_content,
                stop_reason=stop_reason,
                retries=retries,
            )
        return ResponseRepairDecision(status="abstain", reason="no JSON extractable")
