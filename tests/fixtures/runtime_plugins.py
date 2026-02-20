from __future__ import annotations

import asyncio
from typing import Any

from openagents.interfaces.capabilities import MEMORY_INJECT, MEMORY_WRITEBACK, PATTERN_REACT


class InjectWritebackMemory:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {MEMORY_INJECT, MEMORY_WRITEBACK}

    async def inject(self, context: Any) -> None:
        context.state["memory_injected"] = True

    async def writeback(self, context: Any) -> None:
        context.state["memory_written"] = True


class FailingInjectMemory:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {MEMORY_INJECT}

    async def inject(self, context: Any) -> None:
        raise RuntimeError("inject failed")


class FinalPattern:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {PATTERN_REACT}

    async def react(self, context: Any) -> dict[str, Any]:
        injected = context.state.get("memory_injected", False)
        return {"type": "final", "content": f"injected={injected}"}


class SlowFinalPattern:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {PATTERN_REACT}

    async def react(self, context: Any) -> dict[str, Any]:
        delay = float(self.config.get("delay", 0.05))
        await asyncio.sleep(delay)
        return {"type": "final", "content": "slow-done"}


class NonDictActionPattern:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {PATTERN_REACT}

    async def react(self, context: Any) -> Any:
        return "not-a-dict-action"


class UnknownTypePattern:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {PATTERN_REACT}

    async def react(self, context: Any) -> dict[str, Any]:
        return {"type": "unknown_type"}


class MissingToolCallFieldPattern:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {PATTERN_REACT}

    async def react(self, context: Any) -> dict[str, Any]:
        return {"type": "tool_call", "params": {"query": "x"}}


class InvalidToolCallParamsPattern:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {PATTERN_REACT}

    async def react(self, context: Any) -> dict[str, Any]:
        return {"type": "tool_call", "tool": "search", "params": "not-an-object"}


class ContinueForeverPattern:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {PATTERN_REACT}

    async def react(self, context: Any) -> dict[str, Any]:
        return {"type": "continue"}


class SlowContinuePattern:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {PATTERN_REACT}

    async def react(self, context: Any) -> dict[str, Any]:
        delay = float(self.config.get("delay", 0.1))
        await asyncio.sleep(delay)
        return {"type": "continue"}


class FailOnceThenFinalPattern:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {PATTERN_REACT}

    async def react(self, context: Any) -> dict[str, Any]:
        if not context.state.get("failed_once"):
            context.state["failed_once"] = True
            raise RuntimeError("pattern fail once")
        return {"type": "final", "content": "recovered"}

