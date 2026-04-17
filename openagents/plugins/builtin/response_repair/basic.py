"""Builtin response repair policy for empty-response diagnostics."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from openagents.interfaces.response_repair import ResponseRepairDecision, ResponseRepairPolicyPlugin
from openagents.interfaces.typed_config import TypedConfigPluginMixin


class BasicResponseRepairPolicy(TypedConfigPluginMixin, ResponseRepairPolicyPlugin):
    """Default repair policy that emits a structured error diagnosis."""

    class Config(BaseModel):
        pass

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities=set())
        self._init_typed_config()

    async def repair_empty_response(
        self,
        *,
        context: Any,
        messages: list[dict[str, Any]],
        assistant_content: list[dict[str, Any]],
        stop_reason: str | None,
        retries: int,
    ) -> ResponseRepairDecision | None:
        tools = getattr(context, "tools", {}) or {}
        history = getattr(context, "memory_view", {}).get("history")
        history_items = len(history) if isinstance(history, list) else 0
        has_recent_tool_result = any(
            isinstance(msg.get("content"), list)
            and any(
                isinstance(block, dict) and block.get("type") == "tool_result"
                for block in msg.get("content", [])
            )
            for msg in messages[-4:]
        )
        input_text = str(getattr(context, "input_text", "")).strip().replace("\r", " ").replace("\n", " ")
        if len(input_text) > 120:
            input_text = input_text[:117] + "..."
        reason = stop_reason or "<none>"
        message = (
            "LLM returned an empty response after streaming and retry fallback. "
            f"stop_reason={reason}, retries={retries}, transcript_messages={len(messages)}, "
            f"content_blocks={len(assistant_content)}, tools={len(tools)}, "
            f"recent_tool_result={has_recent_tool_result}, history_items={history_items}, "
            f"input={input_text!r}. This usually means the provider ended the turn "
            "without any visible text or tool_use blocks."
        )
        return ResponseRepairDecision(
            status="error",
            reason=message,
            metadata={
                "stop_reason": reason,
                "retries": retries,
                "history_items": history_items,
                "recent_tool_result": has_recent_tool_result,
            },
        )
