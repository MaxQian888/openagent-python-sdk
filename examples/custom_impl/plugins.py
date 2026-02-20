from __future__ import annotations

from typing import Any

from openagents.interfaces.capabilities import MEMORY_INJECT, MEMORY_WRITEBACK, PATTERN_REACT, TOOL_INVOKE


class CustomMemory:
    """Memory strategy fully owned by plugin implementation."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {MEMORY_INJECT, MEMORY_WRITEBACK}
        self.state_key = str(self.config.get("state_key", "custom_memory_items"))

    async def inject(self, context: Any) -> None:
        items = context.state.get(self.state_key)
        if not isinstance(items, list):
            items = []
            context.state[self.state_key] = items
        context.memory_view["history"] = list(items)

    async def writeback(self, context: Any) -> None:
        items = context.state.get(self.state_key)
        if not isinstance(items, list):
            items = []
            context.state[self.state_key] = items
        items.append(
            {
                "input": context.input_text,
                "tool_results": list(context.tool_results),
                "output": context.state.get("_runtime_last_output"),
            }
        )


class CustomPattern:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {PATTERN_REACT}
        self._pending_key = "_custom_pending_tool"

    async def react(self, context: Any) -> dict[str, Any]:
        pending = context.scratch.get(self._pending_key)
        if pending:
            context.scratch.pop(self._pending_key, None)
            latest = context.tool_results[-1]["result"] if context.tool_results else None
            return {"type": "final", "content": f"custom tool result: {latest}"}

        text = (context.input_text or "").strip()
        if text.startswith("/weather"):
            query = text.replace("/weather", "", 1).strip()
            context.scratch[self._pending_key] = True
            return {
                "type": "tool_call",
                "tool": "weather",
                "params": {"query": query},
            }

        history = context.memory_view.get("history")
        count = len(history) if isinstance(history, list) else 0
        return {"type": "final", "content": f"custom echo: {text} (history={count})"}


class WeatherTool:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {TOOL_INVOKE}

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        query = str((params or {}).get("query", "")).strip() or "unknown"
        return {"location": query, "forecast": "sunny", "source": "custom-demo"}


