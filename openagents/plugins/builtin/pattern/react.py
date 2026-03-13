"""Builtin ReAct pattern plugin."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from openagents.interfaces.capabilities import PATTERN_EXECUTE, PATTERN_REACT
from openagents.interfaces.pattern import PatternPlugin


class ReActPattern(PatternPlugin):
    _PENDING_TOOL_KEY = "_react_pending_tool"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={PATTERN_EXECUTE, PATTERN_REACT})

    def _tool_prefix(self) -> str:
        return str(self.config.get("tool_prefix", "/tool")).strip() or "/tool"

    def _echo_prefix(self) -> str:
        return str(self.config.get("echo_prefix", "Echo")).strip() or "Echo"

    def _max_steps(self) -> int:
        max_steps = self.config.get("max_steps", 16)
        if isinstance(max_steps, int) and max_steps > 0:
            return max_steps
        return 16

    def _step_timeout_ms(self) -> int:
        timeout = self.config.get("step_timeout_ms", 30000)
        if isinstance(timeout, int) and timeout > 0:
            return timeout
        return 30000

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

    async def execute(self, context: Any) -> Any:
        """Execute the complete ReAct loop."""
        allowed_action_types = {"tool_call", "final", "continue"}
        max_steps = self._max_steps()
        timeout_s = self._step_timeout_ms() / 1000

        for step in range(max_steps):
            await context.emit("pattern.step_started", step=step)

            try:
                action = await asyncio.wait_for(self.react(context), timeout=timeout_s)
            except asyncio.TimeoutError as exc:
                raise TimeoutError(
                    f"Pattern step timed out after {self._step_timeout_ms()}ms at step {step}"
                ) from exc

            await context.emit("pattern.step_finished", step=step, action=action)

            if not isinstance(action, dict):
                raise TypeError(f"Pattern action must be dict, got {type(action).__name__}")

            action_type = action.get("type")
            if not isinstance(action_type, str) or not action_type.strip():
                raise ValueError("Pattern action must include a non-empty string 'type'")
            if action_type not in allowed_action_types:
                raise ValueError(
                    f"Unsupported pattern action type: '{action_type}'. "
                    f"Allowed: {sorted(allowed_action_types)}"
                )

            if action_type == "tool_call":
                tool_id = action.get("tool") or action.get("tool_id")
                if not isinstance(tool_id, str) or not tool_id:
                    raise ValueError("tool_call action must include non-empty 'tool' or 'tool_id'")
                params = action.get("params", {})
                if params is None:
                    params = {}
                if not isinstance(params, dict):
                    raise ValueError("tool_call action 'params' must be an object")
                await context.call_tool(tool_id, params)
                continue

            if action_type == "final":
                content = action.get("content")
                context.state["_runtime_last_output"] = content
                return content

            # action_type == "continue"
            continue

        raise RuntimeError(f"Pattern exceeded max_steps ({max_steps})")

