"""Memory plugin contract."""

from __future__ import annotations

from typing import Any

from .plugin import BasePlugin


class MemoryPlugin(BasePlugin):
    """Base memory plugin.

    Strategy is owned by the plugin. Runtime only triggers lifecycle points.
    """

    async def inject(self, context: Any) -> None:
        """Inject memory into execution context."""

    async def writeback(self, context: Any) -> None:
        """Write memory updates from execution context."""

    async def close(self) -> None:
        """Cleanup resources."""

