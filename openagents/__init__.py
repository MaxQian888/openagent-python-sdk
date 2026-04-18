"""OpenAgents SDK package.

Quick Start:
    from openagents import Runtime, load_config
    from openagents import RunContext, tool, memory, pattern, runtime, session

    # Define a tool
    @tool
    async def my_tool(params, context: RunContext[object]):
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

from .config.loader import load_config, load_config_dict
from .config.schema import AppConfig
from .errors.exceptions import (
    ModelRetryError,
    OutputValidationError,
)
from .plugins.builtin.skills.local import (
    LocalSkillsManager,
)
from .interfaces.runtime import (
    RunStreamChunk,
    RunStreamChunkKind,
)
from .interfaces.skills import SkillsPlugin, SessionSkillSummary
from .interfaces.run_context import RunContext
from .decorators import (
    context_assembler,
    event_bus,
    get_context_assembler,
    get_event_bus,
    get_memory,
    get_pattern,
    get_runtime,
    get_session,
    get_tool,
    get_tool_executor,
    list_context_assemblers,
    list_event_buses,
    list_memories,
    list_patterns,
    list_runtimes,
    list_sessions,
    list_tools,
    list_tool_executors,
    memory,
    pattern,
    runtime,
    session,
    tool,
    tool_executor,
)
from .runtime.runtime import Runtime
from .runtime.sync import (
    run_agent,
    run_agent_detailed,
    run_agent_detailed_with_config,
    run_agent_with_config,
    run_agent_with_dict,
)

__all__ = [
    # Core
    "AppConfig",
    "LocalSkillsManager",
    "RunContext",
    "Runtime",
    "SkillsPlugin",
    "SessionSkillSummary",
    "load_config",
    "load_config_dict",
    "run_agent",
    "run_agent_detailed",
    "run_agent_detailed_with_config",
    "run_agent_with_config",
    "run_agent_with_dict",
    # Decorators
    "tool",
    "memory",
    "pattern",
    "runtime",
    "session",
    "event_bus",
    "tool_executor",
    "context_assembler",
    # Registry accessors
    "get_tool",
    "get_memory",
    "get_pattern",
    "get_runtime",
    "get_session",
    "get_event_bus",
    "get_tool_executor",
    "get_context_assembler",
    "list_tools",
    "list_memories",
    "list_patterns",
    "list_runtimes",
    "list_sessions",
    "list_event_buses",
    "list_tool_executors",
    "list_context_assemblers",
    # 0.3.0 additions
    "ModelRetryError",
    "OutputValidationError",
    "RunStreamChunk",
    "RunStreamChunkKind",
]
