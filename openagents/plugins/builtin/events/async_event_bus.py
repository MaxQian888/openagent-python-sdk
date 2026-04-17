"""Async event bus implementation - in-memory with history."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from pydantic import BaseModel

from openagents.interfaces.events import (
    EVENT_EMIT,
    EVENT_HISTORY,
    EVENT_SUBSCRIBE,
    EventBusPlugin,
    RuntimeEvent,
)
from openagents.interfaces.typed_config import TypedConfigPluginMixin

logger = logging.getLogger("openagents")


class AsyncEventBus(TypedConfigPluginMixin, EventBusPlugin):
    """Async in-memory event bus with history.

    Events are stored in memory and can be queried.
    Use for single-instance deployments or testing.
    """

    class Config(BaseModel):
        max_history: int = 10_000

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(
            config=config or {},
            capabilities={EVENT_SUBSCRIBE, EVENT_EMIT, EVENT_HISTORY},
        )
        self._init_typed_config()
        self._subscribers: dict[str, list[Callable[[RuntimeEvent], Awaitable[None] | None]]] = {}
        self._history: list[RuntimeEvent] = []
        self._max_history: int = self.cfg.max_history

    @property
    def history(self) -> list[RuntimeEvent]:
        """Get all events (backward compatibility)."""
        return self._history

    def subscribe(self, event_name: str, handler: Callable[[RuntimeEvent], Awaitable[None] | None]) -> None:
        """Subscribe to an event."""
        self._subscribers.setdefault(event_name, []).append(handler)

    async def emit(self, event_name: str, **payload: Any) -> RuntimeEvent:
        """Emit an event."""
        event = RuntimeEvent(name=event_name, payload=payload)
        self._history.append(event)

        # Trim history if needed
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]

        handlers = []
        handlers.extend(self._subscribers.get(event_name, []))
        handlers.extend(self._subscribers.get("*", []))  # Wildcard handlers
        for handler in handlers:
            try:
                result = handler(event)
                if hasattr(result, "__await__"):
                    await result
            except Exception as exc:
                logger.error("Event handler failed for %s: %s", event_name, exc, exc_info=True)

        return event

    async def get_history(
        self,
        event_name: str | None = None,
        limit: int | None = None,
    ) -> list[RuntimeEvent]:
        """Get event history."""
        history = self._history
        if event_name:
            history = [e for e in history if e.name == event_name]
        if limit:
            history = history[-limit:]
        return history

    async def clear_history(self) -> None:
        """Clear event history."""
        self._history.clear()
