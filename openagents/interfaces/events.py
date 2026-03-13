"""Event bus plugin contract - event publishing and subscription."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .plugin import BasePlugin

EventHandler = Callable[["RuntimeEvent"], Awaitable[None] | None]


@dataclass
class RuntimeEvent:
    """Runtime event data."""
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class EventBusPlugin(BasePlugin):
    """Base event bus plugin.

    Implementations control event routing, persistence, and external
    integrations (e.g., Kafka, Prometheus, webhooks).
    """

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Subscribe to an event.

        Args:
            event_name: Event name pattern (supports * wildcard)
            handler: Async handler function
        """
        raise NotImplementedError("EventBusPlugin.subscribe must be implemented")

    async def emit(self, event_name: str, **payload: Any) -> RuntimeEvent:
        """Emit an event.

        Args:
            event_name: Event name
            **payload: Event payload

        Returns:
            The created RuntimeEvent
        """
        raise NotImplementedError("EventBusPlugin.emit must be implemented")

    async def get_history(
        self,
        event_name: str | None = None,
        limit: int | None = None,
    ) -> list[RuntimeEvent]:
        """Get event history.

        Args:
            event_name: Filter by event name (optional)
            limit: Maximum number of events to return

        Returns:
            List of runtime events
        """
        raise NotImplementedError("EventBusPlugin.get_history must be implemented")

    async def clear_history(self) -> None:
        """Clear event history."""
        raise NotImplementedError("EventBusPlugin.clear_history must be implemented")

    async def close(self) -> None:
        """Cleanup event bus resources."""
        pass


# Capability constants
EVENT_SUBSCRIBE = "event.subscribe"
EVENT_EMIT = "event.emit"
EVENT_HISTORY = "event.history"
