"""Contracts for plugin development."""

from .capabilities import MEMORY_INJECT, MEMORY_WRITEBACK, PATTERN_REACT, TOOL_INVOKE
from .events import EventBusPlugin, EVENT_EMIT, EVENT_HISTORY, EVENT_SUBSCRIBE, RuntimeEvent
from .memory import MemoryPlugin
from .pattern import PatternPlugin
from .plugin import BasePlugin
from .runtime import RUNTIME_RUN, RuntimePlugin
from .session import SESSION_MANAGE, SESSION_STATE, SessionManagerPlugin
from .tool import ToolPlugin

__all__ = [
    "BasePlugin",
    "MemoryPlugin",
    "PatternPlugin",
    "ToolPlugin",
    "RuntimePlugin",
    "SessionManagerPlugin",
    "EventBusPlugin",
    "RuntimeEvent",
    # Capabilities
    "MEMORY_INJECT",
    "MEMORY_WRITEBACK",
    "PATTERN_REACT",
    "TOOL_INVOKE",
    "RUNTIME_RUN",
    "SESSION_MANAGE",
    "SESSION_STATE",
    "EVENT_SUBSCRIBE",
    "EVENT_EMIT",
    "EVENT_HISTORY",
]
