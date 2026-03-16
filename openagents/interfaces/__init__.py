"""Contracts for plugin development."""

from .capabilities import (
    MEMORY_INJECT,
    MEMORY_WRITEBACK,
    PATTERN_REACT,
    SKILL_EXECUTE,
    SKILL_GET_PROMPT,
    SKILL_GET_TOOLS,
    TOOL_INVOKE,
)
from .events import EventBusPlugin, EVENT_EMIT, EVENT_HISTORY, EVENT_SUBSCRIBE, RuntimeEvent
from .memory import MemoryPlugin
from .pattern import PatternPlugin
from .plugin import BasePlugin
from .runtime import RUNTIME_LIFECYCLE, RUNTIME_MANAGE, RUNTIME_RUN, RuntimePlugin
from .session import SESSION_MANAGE, SESSION_STATE, SessionManagerPlugin
from .skill import SKILL_EXECUTE, SKILL_GET_PROMPT, SKILL_GET_TOOLS, SkillPlugin
from .tool import ToolPlugin

__all__ = [
    "BasePlugin",
    "MemoryPlugin",
    "PatternPlugin",
    "ToolPlugin",
    "RuntimePlugin",
    "SessionManagerPlugin",
    "EventBusPlugin",
    "SkillPlugin",
    "RuntimeEvent",
    # Capabilities
    "MEMORY_INJECT",
    "MEMORY_WRITEBACK",
    "PATTERN_REACT",
    "TOOL_INVOKE",
    "SKILL_EXECUTE",
    "SKILL_GET_PROMPT",
    "SKILL_GET_TOOLS",
    "RUNTIME_RUN",
    "RUNTIME_MANAGE",
    "RUNTIME_LIFECYCLE",
    "SESSION_MANAGE",
    "SESSION_STATE",
    "EVENT_SUBSCRIBE",
    "EVENT_EMIT",
    "EVENT_HISTORY",
]
