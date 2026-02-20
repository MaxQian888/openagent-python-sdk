"""Builtin buffer memory plugin."""

from __future__ import annotations

from typing import Any

from openagents.interfaces.capabilities import MEMORY_INJECT, MEMORY_WRITEBACK
from openagents.interfaces.memory import MemoryPlugin


class BufferMemory(MemoryPlugin):
    """Append-only in-session memory with configurable projection."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(
            config=config or {},
            capabilities={MEMORY_INJECT, MEMORY_WRITEBACK},
        )

    def _state_key(self) -> str:
        return str(self.config.get("state_key", "memory_buffer"))

    def _view_key(self) -> str:
        return str(self.config.get("view_key", "history"))

    def _max_items(self) -> int | None:
        raw = self.config.get("max_items")
        if raw is None:
            return None
        if isinstance(raw, int) and raw > 0:
            return raw
        return None

    def _get_buffer(self, context: Any) -> list[dict[str, Any]]:
        state_key = self._state_key()
        current = context.state.get(state_key)
        if not isinstance(current, list):
            current = []
            context.state[state_key] = current
        return current

    def _slice_for_view(self, buffer: list[dict[str, Any]]) -> list[dict[str, Any]]:
        max_items = self._max_items()
        if max_items is None:
            return list(buffer)
        return list(buffer[-max_items:])

    def _trim_in_place(self, buffer: list[dict[str, Any]]) -> None:
        max_items = self._max_items()
        if max_items is None:
            return
        if len(buffer) > max_items:
            del buffer[:-max_items]

    async def inject(self, context: Any) -> None:
        buffer = self._get_buffer(context)
        context.memory_view[self._view_key()] = self._slice_for_view(buffer)

    async def writeback(self, context: Any) -> None:
        buffer = self._get_buffer(context)

        record: dict[str, Any] = {
            "input": context.input_text,
            "tool_results": list(context.tool_results),
        }
        if "_runtime_last_output" in context.state:
            record["output"] = context.state["_runtime_last_output"]

        buffer.append(record)
        self._trim_in_place(buffer)
        context.memory_view[self._view_key()] = self._slice_for_view(buffer)

