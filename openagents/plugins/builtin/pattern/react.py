"""Builtin ReAct pattern plugin."""

from __future__ import annotations

import json
from typing import Any

from openagents.interfaces.capabilities import PATTERN_REACT
from openagents.interfaces.pattern import PatternPlugin


class ReActPattern(PatternPlugin):
    _PENDING_TOOL_KEY = "_react_pending_tool"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={PATTERN_REACT})

    def _tool_prefix(self) -> str:
        return str(self.config.get("tool_prefix", "/tool")).strip() or "/tool"

    def _echo_prefix(self) -> str:
        return str(self.config.get("echo_prefix", "Echo")).strip() or "Echo"

    def _format_tool_result(self, tool_id: str, result: Any) -> str:
        return f"Tool[{tool_id}] => {result}"

    def _llm_enabled(self, context: Any) -> bool:
        return getattr(context, "llm_client", None) is not None

    def _llm_system_prompt(self) -> str:
        return (
            "You are a strict planner for an agent runtime.\n"
            "Return only JSON with one of these shapes:\n"
            "{\"type\":\"final\",\"content\":\"...\"}\n"
            "{\"type\":\"continue\"}\n"
            "{\"type\":\"tool_call\",\"tool\":\"<tool_id>\",\"params\":{...}}\n"
            "No markdown, no extra text."
        )

    def _llm_user_prompt(self, context: Any) -> str:
        history = context.memory_view.get("history")
        history_count = len(history) if isinstance(history, list) else 0
        tool_ids = sorted(context.tools.keys())
        return (
            f"INPUT:{context.input_text}\n"
            f"HISTORY_COUNT:{history_count}\n"
            f"TOOLS:{','.join(tool_ids)}\n"
            "Prefer tool_call when user explicitly asks for tool usage.\n"
            "If no tool is needed, return final."
        )

    def _parse_llm_action(self, raw: str) -> dict[str, Any]:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        # Soft fallback: try to parse first JSON object block.
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            snippet = raw[start : end + 1]
            try:
                data = json.loads(snippet)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        return {"type": "final", "content": raw}

    async def _react_with_llm(self, context: Any) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": self._llm_system_prompt()},
            {"role": "user", "content": self._llm_user_prompt(context)},
        ]
        llm_options = getattr(context, "llm_options", None)
        model = getattr(llm_options, "model", None) if llm_options else None
        temperature = getattr(llm_options, "temperature", None) if llm_options else None
        max_tokens = getattr(llm_options, "max_tokens", None) if llm_options else None
        raw = await context.call_llm(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        action = self._parse_llm_action(raw)
        if action.get("type") == "tool_call":
            tool_id = action.get("tool") or action.get("tool_id")
            if isinstance(tool_id, str) and tool_id.strip():
                context.scratch[self._PENDING_TOOL_KEY] = tool_id.strip()
        return action

    async def react(self, context: Any) -> dict[str, Any]:
        pending_tool = context.scratch.get(self._PENDING_TOOL_KEY)
        if isinstance(pending_tool, str):
            context.scratch.pop(self._PENDING_TOOL_KEY, None)
            latest = context.tool_results[-1]["result"] if context.tool_results else None
            return {"type": "final", "content": self._format_tool_result(pending_tool, latest)}

        if self._llm_enabled(context):
            return await self._react_with_llm(context)

        raw_input = (context.input_text or "").strip()
        prefix = self._tool_prefix()
        if raw_input.startswith(prefix):
            rest = raw_input[len(prefix) :].strip()
            if not rest:
                return {
                    "type": "final",
                    "content": f"Usage: {prefix} <tool_id> <query>",
                }
            parts = rest.split(maxsplit=1)
            tool_id = parts[0].strip()
            query = parts[1].strip() if len(parts) == 2 else ""
            context.scratch[self._PENDING_TOOL_KEY] = tool_id
            return {
                "type": "tool_call",
                "tool": tool_id,
                "params": {"query": query},
            }

        history = context.memory_view.get("history")
        history_count = len(history) if isinstance(history, list) else 0
        return {
            "type": "final",
            "content": f"{self._echo_prefix()}: {raw_input} (history={history_count})",
        }

