"""Reflexion pattern: execute with self-reflection on failures."""

from __future__ import annotations

import json
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

    # Default implementations

    async def emit(self, event_name: str, **payload: Any) -> None:
        """Emit event using context's event_bus."""
        ctx = self.context
        await ctx.event_bus.emit(
            event_name,
            agent_id=ctx.agent_id,
            session_id=ctx.session_id,
            **payload,
        )

    async def call_tool(self, tool_id: str, params: dict[str, Any] | None = None) -> Any:
        """Call a tool and record result."""
        ctx = self.context
        if tool_id not in ctx.tools:
            raise KeyError(f"Tool '{tool_id}' is not registered")
        tool = ctx.tools[tool_id]
        await self.emit("tool.called", tool_id=tool_id, params=params or {})
        try:
            result = await tool.invoke(params or {}, ctx)
            ctx.tool_results.append({"tool_id": tool_id, "result": result})
            await self.emit("tool.succeeded", tool_id=tool_id, result=result)
            return result
        except Exception as exc:
            await self.emit("tool.failed", tool_id=tool_id, error=str(exc))
            raise

    async def call_llm(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Call the LLM."""
        ctx = self.context
        if ctx.llm_client is None:
            raise RuntimeError("No LLM client configured for this agent")
        await self.emit("llm.called", model=model)
        result = await ctx.llm_client.complete(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        await self.emit("llm.succeeded", model=model)
        return result

    # Pattern-specific methods

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

    def _llm_enabled(self) -> bool:
        ctx = self.context
        return ctx.llm_client is not None

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

    def _reflection_prompt(self) -> str:
        ctx = self.context
        history = ctx.memory_view.get("history", [])
        tool_results = ctx.tool_results

        history_text = self._format_history(history)

        results_text = ""
        if tool_results:
            results = []
            for tr in tool_results[-2:]:
                tool_id = tr.get("tool_id", "unknown")
                result = tr.get("result", tr.get("error", "error"))
                results.append(f"{tool_id}: {result}")
            results_text = f"Recent tool results: {', '.join(results)}\n"

        return (
            f"You are reflecting on the agent's recent actions.\n"
            f"CONVERSATION_HISTORY:\n{history_text}\n"
            f"{results_text}"
            f"Current input: {ctx.input_text}\n"
            "Determine if the task is complete or needs retry.\n"
            "Return JSON:\n"
            '{"type":"final","content":"result"} if complete\n'
            '{"type":"retry","reason":"why","adjusted_params":{...}} to retry\n'
            '{"type":"continue"} to do more steps\n'
            "No markdown."
        )

    def _action_prompt(self) -> str:
        ctx = self.context
        tool_ids = sorted(ctx.tools.keys())
        history = ctx.memory_view.get("history", [])
        history_text = self._format_history(history)

        return (
            f"Input: {ctx.input_text}\n"
            f"CONVERSATION_HISTORY:\n{history_text}\n"
            f"Available tools: {', '.join(tool_ids)}\n"
            "Return JSON:\n"
            '{"type":"tool_call","tool":"id","params":{...}}\n'
            '{"type":"final","content":"..."}\n'
            '{"type":"continue"}\n'
            "No markdown."
        )

    def _parse_llm_response(self, raw: str) -> dict[str, Any]:
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

    async def react(self) -> dict[str, Any]:
        """Single step with reflection."""
        ctx = self.context
        # Check if we should reflect on recent results
        if ctx.tool_results:
            # Reflect on last tool result
            messages = [
                {"role": "system", "content": self._reflection_prompt()},
                {"role": "user", "content": "Reflect on the previous action and determine next step."},
            ]
            try:
                raw = await self.call_llm(messages=messages)
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
        if self._llm_enabled():
            messages = [
                {"role": "system", "content": self._action_prompt()},
                {"role": "user", "content": ctx.input_text},
            ]
            raw = await self.call_llm(messages=messages)
            return self._parse_llm_response(raw)

        # No LLM, just continue
        return {"type": "continue"}

    async def execute(self) -> Any:
        """Execute with reflection after each step."""
        ctx = self.context
        max_steps = self._max_steps()
        retries = 0

        for step in range(max_steps):
            await self.emit("pattern.step_started", step=step)

            action = await self.react()

            await self.emit("pattern.step_finished", step=step, action=action)

            if not isinstance(action, dict):
                raise TypeError("Pattern action must be dict")

            action_type = action.get("type")

            if action_type == "tool_call":
                tool_id = action.get("tool") or action.get("tool_id")
                params = action.get("params", {})
                if not tool_id:
                    raise ValueError("tool_call must include 'tool'")
                await self.call_tool(tool_id, params)
                continue

            if action_type == "final":
                content = action.get("content", "")
                ctx.state["_runtime_last_output"] = content
                return content

            # continue or retry - loop continues
            if action_type == "retry":
                retries += 1
                if retries >= self._max_retries:
                    return f"Max retries ({self._max_retries}) reached"

        raise RuntimeError(f"Pattern exceeded max_steps ({max_steps})")
