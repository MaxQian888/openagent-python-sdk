"""Contracts for plugin development."""

from .capabilities import MEMORY_INJECT, MEMORY_WRITEBACK, PATTERN_REACT, TOOL_INVOKE
from .memory import MemoryPlugin
from .pattern import PatternPlugin
from .plugin import BasePlugin
from .tool import ToolPlugin

__all__ = [
    "BasePlugin",
    "MemoryPlugin",
    "PatternPlugin",
    "ToolPlugin",
    "MEMORY_INJECT",
    "MEMORY_WRITEBACK",
    "PATTERN_REACT",
    "TOOL_INVOKE",
]

