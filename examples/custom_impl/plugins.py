from __future__ import annotations

from typing import Any

from openagents.interfaces.capabilities import (
    MEMORY_INJECT,
    MEMORY_WRITEBACK,
    PATTERN_EXECUTE,
    PATTERN_REACT,
    TOOL_INVOKE,
)
from openagents.interfaces.pattern import ExecutionContext


class CustomMemory:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {MEMORY_INJECT, MEMORY_WRITEBACK}
        self._state_key = self.config.get("state_key", "custom_history")

    async def inject(self, context: Any) -> None:
        history = context.state.get(self._state_key, [])
        context.memory_view["history"] = list(history)

    async def writeback(self, context: Any) -> None:
        history = list(context.state.get(self._state_key, []))
        history.append(
            {
                "input": context.input_text,
                "output": context.state.get("_runtime_last_output", ""),
            }
        )
        context.state[self._state_key] = history


class CustomTool:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {TOOL_INVOKE}
        self._prefix = self.config.get("prefix", "custom")

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        text = str(params.get("text", "")).strip()
        memory_items = len(context.memory_view.get("history", []))
        return {
            "text": text,
            "memory_items": memory_items,
            "prefix": self._prefix,
        }


class CustomPattern:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {PATTERN_EXECUTE, PATTERN_REACT}
        self.context: ExecutionContext | None = None

    async def setup(
        self,
        agent_id: str,
        session_id: str,
        input_text: str,
        state: dict[str, Any],
        tools: dict[str, Any],
        llm_client: Any,
        llm_options: Any,
        event_bus: Any,
    ) -> None:
        self.context = ExecutionContext(
            agent_id=agent_id,
            session_id=session_id,
            input_text=input_text,
            state=state,
            tools=tools,
            llm_client=llm_client,
            llm_options=llm_options,
            event_bus=event_bus,
        )

    async def react(self) -> dict[str, Any]:
        assert self.context is not None
        return {
            "type": "tool_call",
            "tool": "custom_tool",
            "params": {"text": self.context.input_text},
        }

    async def execute(self) -> Any:
        assert self.context is not None
        action = await self.react()
        tool = self.context.tools[action["tool"]]
        result = await tool.invoke(action["params"], self.context)
        output = (
            f"{result['prefix']}: {result['text']} "
            f"(history={result['memory_items']})"
        )
        self.context.state["_runtime_last_output"] = output
        return output
