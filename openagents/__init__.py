"""OpenAgents SDK package.

Quick Start:
    from openagents import Runtime, load_config
    from openagents import tool, memory, pattern, runtime, session

    # Define a tool
    @tool
    async def my_tool(params, context):
        return {"result": "ok"}

    # Define a memory
    @memory
    class MyMemory:
        async def inject(self, context):
            context.memory_view["history"] = []

        async def writeback(self, context):
            ...

        async def retrieve(self, query, context):
            return []

    # Define a pattern
    @pattern
    class MyPattern:
        async def execute(self):
            ...

    # Use in config
    runtime = Runtime.from_config("agent.json")
"""

from .config.loader import load_config
from .config.schema import AppConfig
from .decorators import (
    event_bus,
    get_event_bus,
    get_memory,
    get_pattern,
    get_runtime,
    get_session,
    get_tool,
    list_event_buses,
    list_memories,
    list_patterns,
    list_runtimes,
    list_sessions,
    list_tools,
    memory,
    pattern,
    runtime,
    session,
    tool,
)
from .runtime.runtime import Runtime
from .runtime.sync import run_agent, run_agent_with_config

__all__ = [
    # Core
    "AppConfig",
    "Runtime",
    "load_config",
    "run_agent",
    "run_agent_with_config",
    # Decorators
    "tool",
    "memory",
    "pattern",
    "runtime",
    "session",
    "event_bus",
    # Registry accessors
    "get_tool",
    "get_memory",
    "get_pattern",
    "get_runtime",
    "get_session",
    "get_event_bus",
    "list_tools",
    "list_memories",
    "list_patterns",
    "list_runtimes",
    "list_sessions",
    "list_event_buses",
]
