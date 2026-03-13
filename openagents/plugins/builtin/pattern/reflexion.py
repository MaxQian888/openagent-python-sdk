"""Reflexion pattern: execute with self-reflection on failures."""

from __future__ import annotations

import asyncio
from typing import Any

from openagents.interfaces.capabilities import PATTERN_EXECUTE, PATTERN_REACT
from openagents.interfaces.pattern import PatternPlugin


class ReflexionPattern(PatternPlugin):
    """Reflexion pattern: execute, reflect on results, retry if needed.

    After each tool result, LLM reflects on whether the task is complete
    or needs retry with adjusted approach.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={PATTERN_EXECUTE, PATTERN_REACT})
        self._max_retries = config.get("max_retries", 2) if config else 2

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

    def _llm_enabled(self, context: Any) -> bool:
        return getattr(context, "llm_client", None) is not None

    def _reflection_prompt(self, context: Any) -> str:
        history = context.memory_view.get("history", [])
        tool_results = context.tool_results

        history_text = ""
        if history:
            history_text = f"History: {history[-3:]}\n"

        results_text = ""
        if tool_results:
            results_text = f"Recent tool results: {tool_results[-2:]}\n"

        return (
            f"You are reflecting on the agent's recent actions.\n"
            f"{history_text}"
            f"{results_text}"
            f"Current input: {context.input_text}\n"
            "Determine if the task is complete or needs retry.\n"
            "Return JSON:\n"
            "{\"type\":\"final\",\"content\":\"result\"} if complete\n"
            "{\"type\":\"retry\",\"reason\":\"why\",\"adjusted_params\":{...}} to retry\n"
            "{\"type\":\"continue\"} to do more steps\n"
            "No markdown."
        )

    def _action_prompt(self, context: Any) -> str:
        tool_ids = sorted(context.tools.keys())
        return (
            f"Input: {context.input_text}\n"
            f"Available tools: {', '.join(tool_ids)}\n"
            "Return JSON:\n"
            "{\"type\":\"tool_call\",\"tool\":\"id\",\"params\":{...}}\n"
            "{\"type\":\"final\",\"content\":\"...\"}\n"
            "{\"type\":\"continue\"}\n"
            "No markdown."
        )

    def _parse_llm_response(self, raw: str) -> dict[str, Any]:
        import json
        try:
            data = json.loads(raw.strip())
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {"type": "final", "content": raw}

    async def react(self, context: Any) -> dict[str, Any]:
        """Single step with reflection."""
        # Check if we should reflect on recent results
        if context.tool_results:
            # Reflect on last tool result
            messages = [
                {"role": "system", "content": self._reflection_prompt(context)},
                {"role": "user", "content": "Reflect on the previous action and determine next step."},
            ]
            try:
                raw = await context.call_llm(messages=messages)
                reflection = self._parse_llm_response(raw)

                action_type = reflection.get("type")
                if action_type == "final":
                    return {"type": "final", "content": reflection.get("content", "")}
                if action_type == "retry":
                    # Retry with adjusted approach
                    adjusted = reflection.get("adjusted_params", {})
                    tool_id = adjusted.get("tool")
                    params = adjusted.get("params", {})
                    if tool_id:
                        return {"type": "tool_call", "tool": tool_id, "params": params}
            except Exception:
                pass  # Fall through to normal action

        # Normal action selection
        if self._llm_enabled(context):
            messages = [
                {"role": "system", "content": self._action_prompt(context)},
                {"role": "user", "content": context.input_text},
            ]
            raw = await context.call_llm(messages=messages)
            return self._parse_llm_response(raw)

        # No LLM, just continue
        return {"type": "continue"}

    async def execute(self, context: Any) -> Any:
        """Execute with reflection after each step."""
        max_steps = self._max_steps()
        timeout_s = self._step_timeout_ms() / 1000
        retries = 0

        for step in range(max_steps):
            await context.emit("pattern.step_started", step=step)

            try:
                action = await asyncio.wait_for(self.react(context), timeout=timeout_s)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Step timed out at step {step}")

            await context.emit("pattern.step_finished", step=step, action=action)

            if not isinstance(action, dict):
                raise TypeError("Pattern action must be dict")

            action_type = action.get("type")

            if action_type == "tool_call":
                tool_id = action.get("tool") or action.get("tool_id")
                params = action.get("params", {})
                if not tool_id:
                    raise ValueError("tool_call must include 'tool'")
                await context.call_tool(tool_id, params)
                continue

            if action_type == "final":
                content = action.get("content", "")
                context.state["_runtime_last_output"] = content
                return content

            # continue or retry - loop continues
            if action_type == "retry":
                retries += 1
                if retries >= self._max_retries:
                    return f"Max retries ({self._max_retries}) reached"

        raise RuntimeError(f"Pattern exceeded max_steps ({max_steps})")
