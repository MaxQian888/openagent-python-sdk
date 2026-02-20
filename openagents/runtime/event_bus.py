"""Async event bus with in-memory history."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

EventHandler = Callable[["RuntimeEvent"], Awaitable[None] | None]


@dataclass
class RuntimeEvent:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = {}
        self.history: list[RuntimeEvent] = []

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._subscribers.setdefault(event_name, []).append(handler)

    async def emit(self, event_name: str, **payload: Any) -> RuntimeEvent:
        event = RuntimeEvent(name=event_name, payload=payload)
        self.history.append(event)

        handlers = []
        handlers.extend(self._subscribers.get(event_name, []))
        handlers.extend(self._subscribers.get("*", []))
        for handler in handlers:
            result = handler(event)
            if hasattr(result, "__await__"):
                await result
        return event

