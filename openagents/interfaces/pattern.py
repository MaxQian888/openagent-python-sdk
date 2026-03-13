"""Pattern plugin contract."""

from __future__ import annotations

from typing import Any

from .plugin import BasePlugin


class PatternPlugin(BasePlugin):
    """Base pattern plugin."""

    async def execute(self, context: Any) -> Any:
        """Execute the pattern and return the final result."""
        raise NotImplementedError("PatternPlugin.execute must be implemented")

    async def react(self, context: Any) -> dict[str, Any]:
        """Run one pattern step and return an action payload (legacy)."""
        raise NotImplementedError("PatternPlugin.react must be implemented")

