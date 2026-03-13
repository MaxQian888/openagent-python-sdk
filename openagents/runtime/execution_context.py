"""Execution context exposed to pattern plugins."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openagents.interfaces.events import EventBusPlugin


@dataclass
class ExecutionContext:
    agent_id: str
    session_id: str
    input_text: str
    state: dict[str, Any]
    tools: dict[str, Any]
    llm_client: Any | None
    llm_options: Any | None
    event_bus: "EventBusPlugin"
    memory_view: dict[str, Any] = field(default_factory=dict)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    scratch: dict[str, Any] = field(default_factory=dict)

    async def emit(self, event_name: str, **payload: Any) -> None:
        await self.event_bus.emit(
            event_name,
            agent_id=self.agent_id,
            session_id=self.session_id,
            **payload,
        )

    async def call_tool(self, tool_id: str, params: dict[str, Any] | None = None) -> Any:
        if tool_id not in self.tools:
            raise KeyError(f"Tool '{tool_id}' is not registered")
        tool = self.tools[tool_id]
        await self.emit("tool.called", tool_id=tool_id, params=params or {})
        try:
            result = await tool.invoke(params or {}, self)
            self.tool_results.append({"tool_id": tool_id, "result": result})
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
        if self.llm_client is None:
            raise RuntimeError("No LLM client configured for this agent")
        await self.emit("llm.called", model=model)
        result = await self.llm_client.complete(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        await self.emit("llm.succeeded", model=model)
        return result
