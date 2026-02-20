from __future__ import annotations

from typing import Any

from openagents.interfaces.capabilities import MEMORY_INJECT, PATTERN_REACT, TOOL_INVOKE


class CustomMemory:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {MEMORY_INJECT}

    async def inject(self, context: Any) -> None:
        return None


class CustomPattern:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {PATTERN_REACT}

    async def react(self, context: Any) -> dict[str, Any]:
        return {"type": "final", "content": "ok"}


class CustomTool:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {TOOL_INVOKE}

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        return {"ok": True, "params": params}


class BadPatternNoCapability:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = set()

    async def react(self, context: Any) -> dict[str, Any]:
        return {"type": "final", "content": "bad"}


