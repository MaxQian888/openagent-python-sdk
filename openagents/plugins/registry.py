"""Builtin plugin registry."""

from __future__ import annotations

from typing import Any

from openagents.plugins.builtin.events.async_event_bus import AsyncEventBus
from openagents.plugins.builtin.memory.buffer import BufferMemory
from openagents.plugins.builtin.memory.window_buffer import WindowBufferMemory
from openagents.plugins.builtin.pattern.react import ReActPattern
from openagents.plugins.builtin.runtime.default_runtime import DefaultRuntime
from openagents.plugins.builtin.session.in_memory import InMemorySessionManager
from openagents.plugins.builtin.tool.common import BuiltinSearchTool
from openagents.plugins.builtin.tool.file_ops import (
    DeleteFileTool,
    ListFilesTool,
    ReadFileTool,
    WriteFileTool,
)
from openagents.plugins.builtin.tool.http_ops import HttpRequestTool
from openagents.plugins.builtin.tool.system_ops import (
    ExecuteCommandTool,
    GetEnvTool,
    SetEnvTool,
)
from openagents.plugins.builtin.tool.text_ops import (
    GrepFilesTool,
    JsonParseTool,
    RipgrepTool,
    TextTransformTool,
)

_BUILTIN_REGISTRY: dict[str, dict[str, type[Any]]] = {
    "memory": {
        "buffer": BufferMemory,
        "window_buffer": WindowBufferMemory,
    },
    "pattern": {
        "react": ReActPattern,
    },
    "runtime": {
        "default": DefaultRuntime,
    },
    "session": {
        "in_memory": InMemorySessionManager,
    },
    "events": {
        "async": AsyncEventBus,
    },
    "tool": {
        "builtin_search": BuiltinSearchTool,
        # File operations
        "read_file": ReadFileTool,
        "write_file": WriteFileTool,
        "list_files": ListFilesTool,
        "delete_file": DeleteFileTool,
        # Text operations
        "grep_files": GrepFilesTool,
        "ripgrep": RipgrepTool,
        "json_parse": JsonParseTool,
        "text_transform": TextTransformTool,
        # HTTP operations
        "http_request": HttpRequestTool,
        # System operations
        "execute_command": ExecuteCommandTool,
        "get_env": GetEnvTool,
        "set_env": SetEnvTool,
    },
}


def get_builtin_plugin_class(kind: str, name: str) -> type[Any] | None:
    return _BUILTIN_REGISTRY.get(kind, {}).get(name)


def list_builtin_plugins(kind: str) -> list[str]:
    return sorted(_BUILTIN_REGISTRY.get(kind, {}).keys())

