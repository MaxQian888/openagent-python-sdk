"""Builtin window buffer memory plugin."""

from __future__ import annotations

from typing import Any

from .buffer import BufferMemory


class WindowBufferMemory(BufferMemory):
    """Sliding-window memory built on top of BufferMemory."""

    def __init__(self, config: dict[str, Any] | None = None):
        merged = dict(config or {})
        window_size = merged.get("window_size", 20)
        if not isinstance(window_size, int) or window_size <= 0:
            window_size = 20
        # Keep all trimming logic in BufferMemory through a single max_items switch.
        merged["max_items"] = window_size
        super().__init__(config=merged)

    def window_size(self) -> int:
        return int(self.config.get("max_items", 20))
