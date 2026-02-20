"""Builtin plugin registry."""

from __future__ import annotations

from typing import Any

from openagents.plugins.builtin.memory.buffer import BufferMemory
from openagents.plugins.builtin.memory.window_buffer import WindowBufferMemory
from openagents.plugins.builtin.pattern.react import ReActPattern
from openagents.plugins.builtin.tool.common import BuiltinSearchTool

_BUILTIN_REGISTRY: dict[str, dict[str, type[Any]]] = {
    "memory": {
        "buffer": BufferMemory,
        "window_buffer": WindowBufferMemory,
    },
    "pattern": {
        "react": ReActPattern,
    },
    "tool": {
        "builtin_search": BuiltinSearchTool,
    },
}


def get_builtin_plugin_class(kind: str, name: str) -> type[Any] | None:
    return _BUILTIN_REGISTRY.get(kind, {}).get(name)


def list_builtin_plugins(kind: str) -> list[str]:
    return sorted(_BUILTIN_REGISTRY.get(kind, {}).keys())

