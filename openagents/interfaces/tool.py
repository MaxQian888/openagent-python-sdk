"""Tool plugin contract."""

from __future__ import annotations

from typing import Any

from .plugin import BasePlugin


class ToolPlugin(BasePlugin):
    """Base tool plugin."""

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        """Execute tool call."""
        raise NotImplementedError("ToolPlugin.invoke must be implemented")

