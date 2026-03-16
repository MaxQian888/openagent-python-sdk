"""Plan-Execute pattern: first plan, then execute step by step."""

from __future__ import annotations

import asyncio
from typing import Any

from openagents.interfaces.capabilities import PATTERN_EXECUTE, PATTERN_REACT
from openagents.interfaces.pattern import PatternPlugin


class PlanExecutePattern(PatternPlugin):
    """Two-phase pattern: planning first, then execution.

    Phase 1 (Plan): LLM generates a step-by-step plan
    Phase 2 (Execute): Execute each step, handle tool results
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={PATTERN_EXECUTE, PATTERN_REACT})

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

    def _format_history(self, history: list) -> str:
        """Format history for LLM prompt."""
        if not history:
            return "(no conversation history)"

        lines = []
        for item in history[-5:]:  # Last 5 entries
            if isinstance(item, dict):
                user_msg = item.get("input", "")
                assistant_msg = item.get("output", "")
                if user_msg:
                    lines.append(f"User: {user_msg}")
                if assistant_msg:
                    lines.append(f"Assistant: {assistant_msg}")
        return "\n".join(lines) if lines else "(no conversation history)"

    def _planning_prompt(self, context: Any) -> str:
        history = context.memory_view.get("history", [])
        history_text = self._format_history(history)

        return (
            "You are a planner for an agent runtime.\n"
            "Given the user input and conversation history, create a detailed step-by-step plan.\n"
            f"CONVERSATION_HISTORY:\n{history_text}\n"
            "Return only JSON with this structure:\n"
            "{\"plan\": [{\"step\": 1, \"action\": \"tool_call\", \"tool\": \"tool_id\", \"params\": {...}}, {\"step\": 2, \"action\": \"final\", \"content\": \"...\"}]}\n"
            "No markdown, no extra text."
        )

    def _execution_prompt(self, context: Any, step_num: int, plan: list) -> str:
        tool_ids = sorted(context.tools.keys())
        history = context.memory_view.get("history", [])
        history_text = self._format_history(history)

        return (
            f"Execute step {step_num} of the plan.\n"
            f"Current input: {context.input_text}\n"
            f"CONVERSATION_HISTORY:\n{history_text}\n"
            f"Available tools: {', '.join(tool_ids)}\n"
            f"Return JSON:\n"
            "{\"type\":\"tool_call\",\"tool\":\"id\",\"params\":{...}} or {\"type\":\"final\",\"content\":\"...\"}\n"
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
        # Try to find JSON in text
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {"type": "final", "content": raw}

    async def _plan(self, context: Any) -> list[dict[str, Any]]:
        """Phase 1: Create a plan."""
        messages = [
            {"role": "system", "content": self._planning_prompt(context)},
            {"role": "user", "content": context.input_text},
        ]
        raw = await context.call_llm(messages=messages)
        result = self._parse_llm_response(raw)

        plan = result.get("plan", [])
        if not isinstance(plan, list):
            plan = [{"type": "final", "content": str(plan)}]
        return plan

    async def _execute_plan(self, context: Any, plan: list[dict[str, Any]]) -> str:
        """Phase 2: Execute the plan step by step."""
        max_steps = self._max_steps()
        timeout_s = self._step_timeout_ms() / 1000
        results = []

        for i, step in enumerate(plan[:max_steps]):
            step_num = i + 1
            await context.emit("pattern.step_started", step=step_num, plan_step=step)

            action_type = step.get("action") or step.get("type")

            if action_type == "tool_call":
                tool_id = step.get("tool")
                params = step.get("params", {})
                try:
                    await context.call_tool(tool_id, params)
                    results.append(f"Step {step_num}: {tool_id} completed")
                except Exception as e:
                    results.append(f"Step {step_num}: {tool_id} failed - {e}")
                continue

            # Assume final/continue
            content = step.get("content", step.get("result", ""))
            results.append(f"Step {step_num}: {content}")
            if action_type == "final":
                return content

        return "\n".join(results) if results else "Plan executed"

    async def react(self, context: Any) -> dict[str, Any]:
        """Single step - not used in PlanExecute, use execute instead."""
        return {"type": "final", "content": "Use execute() for PlanExecute pattern"}

    async def execute(self, context: Any) -> Any:
        """Execute the complete Plan-Execute workflow."""
        if not self._llm_enabled(context):
            return {"type": "final", "content": "PlanExecute requires LLM"}

        await context.emit("pattern.phase", phase="planning")

        # Phase 1: Create plan
        plan = await self._plan(context)
        context.scratch["_plan"] = plan

        await context.emit("pattern.phase", phase="executing")
        await context.emit("pattern.plan_created", plan=plan)

        # Phase 2: Execute plan
        result = await self._execute_plan(context, plan)

        context.state["_runtime_last_output"] = result
        return result
