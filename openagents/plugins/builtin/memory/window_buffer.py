"""Builtin window buffer memory plugin."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from .buffer import BufferMemory

logger = logging.getLogger(__name__)


class _WindowBufferConfig(BaseModel):
    """Module-private validator for the WindowBuffer-shaped config.

    Kept off the class so it does not become the ``self.Config`` that
    BufferMemory's typed-config init resolves via MRO.
    """

    state_key: str = "memory_buffer"
    view_key: str = "history"
    window_size: int = Field(default=20, gt=0)


class WindowBufferMemory(BufferMemory):
    """Sliding-window memory built on top of BufferMemory.

    What:
        Like :class:`BufferMemory` but rejects any items beyond the
        configured ``window_size``. Internally translates
        ``window_size`` to :class:`BufferMemory`'s ``max_items`` so
        trimming logic stays in one place.

    Usage:
        ``{"type": "window_buffer", "config": {"window_size": 20}}``
        (``state_key`` / ``view_key`` optional).

    Depends on:
        - :class:`BufferMemory` (parent class) for inject/writeback.
        - ``RunContext.state`` and ``RunContext.memory_view`` (via
          parent).
    """

    def __init__(self, config: dict[str, Any] | None = None):
        raw = dict(config or {})
        known = set(_WindowBufferConfig.model_fields.keys())
        unknown = sorted(set(raw.keys()) - known)
        if unknown:
            logger.warning(
                "plugin %s received unknown config keys: %s",
                type(self).__name__,
                unknown,
            )
        local_cfg = _WindowBufferConfig.model_validate(raw)
        # Translate window_size into BufferMemory's max_items switch so
        # all trimming logic stays in BufferMemory. Pass only fields
        # known to BufferMemory.Config to avoid duplicate warnings.
        merged = {
            "state_key": local_cfg.state_key,
            "view_key": local_cfg.view_key,
            "max_items": local_cfg.window_size,
        }
        super().__init__(config=merged)
        self._window_cfg = local_cfg

    def window_size(self) -> int:
        return int(self._window_cfg.window_size)
