"""Builtin follow-up resolver for common multi-turn questions."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from openagents.interfaces.followup import FollowupResolution, FollowupResolverPlugin
from openagents.interfaces.typed_config import TypedConfigPluginMixin


class BasicFollowupResolver(TypedConfigPluginMixin, FollowupResolverPlugin):
    """Answer simple follow-up questions from local memory/state."""

    class Config(BaseModel):
        pass

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities=set())
        self._init_typed_config()

    async def resolve(self, *, context: Any) -> FollowupResolution | None:
        user_text = str(getattr(context, "input_text", "")).strip().lower()
        markers = (
            "你刚干了什么",
            "你刚刚干了什么",
            "刚才干了什么",
            "上一轮干了什么",
            "what did you do",
            "what did you just do",
            "what happened last turn",
        )
        if not any(marker in user_text for marker in markers):
            return None

        history = getattr(context, "memory_view", {}).get("history")
        if not isinstance(history, list) or not history:
            return FollowupResolution(
                status="abstain",
                reason="No local history available for follow-up resolution.",
            )

        last = history[-1]
        if not isinstance(last, dict):
            return FollowupResolution(status="abstain", reason="Last history item is not structured.")

        previous_input = str(last.get("input", "")).strip()
        output = str(last.get("output", "")).strip()
        tool_ids: list[str] = []
        raw_tool_results = last.get("tool_results")
        if isinstance(raw_tool_results, list):
            for item in raw_tool_results:
                if isinstance(item, dict):
                    tool_id = item.get("tool_id")
                    if isinstance(tool_id, str) and tool_id:
                        tool_ids.append(tool_id)

        if not previous_input and not output and not tool_ids:
            return FollowupResolution(
                status="abstain",
                reason="History exists but does not contain enough action detail.",
            )

        lines = []
        if previous_input:
            lines.append(f"上一轮我处理了你的请求：{previous_input}")
        if tool_ids:
            lines.append(f"调用的工具：{', '.join(tool_ids)}")
        if output:
            lines.append("并把结果返回给你。")

        return FollowupResolution(
            status="resolved",
            output="\n".join(lines) if lines else output,
            metadata={"tool_ids": tool_ids},
        )
