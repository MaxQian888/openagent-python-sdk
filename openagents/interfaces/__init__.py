"""Contracts for plugin development."""

from .capabilities import (
    MEMORY_INJECT,
    MEMORY_RETRIEVE,
    MEMORY_WRITEBACK,
    PATTERN_EXECUTE,
    PATTERN_REACT,
    SKILL_CONTEXT_AUGMENT,  # noqa: F401
    SKILL_METADATA,  # noqa: F401
    SKILL_POST_RUN,  # noqa: F401
    SKILL_PRE_RUN,  # noqa: F401
    SKILL_SYSTEM_PROMPT,  # noqa: F401
    SKILL_TOOL_FILTER,  # noqa: F401
    SKILL_TOOLS,  # noqa: F401
    TOOL_INVOKE,
)
from .context import ContextAssemblerPlugin, ContextAssemblyResult
from .events import (
    EVENT_EMIT,
    EVENT_HISTORY,
    EVENT_SUBSCRIBE,
    RUNTIME_SHUTDOWN_COMPLETED,
    RUNTIME_SHUTDOWN_REQUESTED,
    RUNTIME_SHUTDOWN_STARTED,
    EventBusPlugin,
    RuntimeEvent,
)
from .followup import FollowupResolution
from .memory import MemoryPlugin
from .pattern import ExecutionContext, PatternPlugin
from .plugin import BasePlugin
from .response_repair import ResponseRepairDecision
from .run_context import RunContext
from .runtime import (
    RUNTIME_LIFECYCLE,
    RUNTIME_MANAGE,
    RUNTIME_RUN,
    RunArtifact,
    RunBudget,
    RunRequest,
    RunResult,
    RuntimePlugin,
    RunUsage,
    StopReason,
)
from .session import (
    SESSION_ARTIFACTS,
    SESSION_CHECKPOINTS,
    SESSION_MANAGE,
    SESSION_STATE,
    SESSION_TRANSCRIPT,
    SessionArtifact,
    SessionCheckpoint,
    SessionManagerPlugin,
)
from .skills import SessionSkillSummary, SkillsPlugin
from .tool import (
    PermanentToolError,
    PolicyDecision,
    RetryableToolError,
    ToolError,
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionSpec,
    ToolExecutor,
    ToolExecutorPlugin,
    ToolPlugin,
    ToolResult,
)

__all__ = [
    "BasePlugin",
    "ExecutionContext",
    "RunContext",
    "ContextAssemblerPlugin",
    "ContextAssemblyResult",
    "FollowupResolution",
    "MemoryPlugin",
    "PatternPlugin",
    "ResponseRepairDecision",
    "SkillsPlugin",
    "SessionSkillSummary",
    "PolicyDecision",
    "ToolPlugin",
    "ToolExecutionSpec",
    "ToolExecutionRequest",
    "ToolExecutionResult",
    "ToolExecutor",
    "ToolExecutorPlugin",
    "ToolError",
    "RetryableToolError",
    "PermanentToolError",
    "ToolResult",
    "RunBudget",
    "RunRequest",
    "RunResult",
    "RunUsage",
    "RunArtifact",
    "StopReason",
    "RuntimePlugin",
    "SessionArtifact",
    "SessionCheckpoint",
    "SessionManagerPlugin",
    "EventBusPlugin",
    "RuntimeEvent",
    # Capabilities
    "MEMORY_INJECT",
    "MEMORY_RETRIEVE",
    "MEMORY_WRITEBACK",
    "PATTERN_EXECUTE",
    "PATTERN_REACT",
    "TOOL_INVOKE",
    "RUNTIME_RUN",
    "RUNTIME_MANAGE",
    "RUNTIME_LIFECYCLE",
    "SESSION_MANAGE",
    "SESSION_STATE",
    "SESSION_TRANSCRIPT",
    "SESSION_ARTIFACTS",
    "SESSION_CHECKPOINTS",
    "EVENT_SUBSCRIBE",
    "EVENT_EMIT",
    "EVENT_HISTORY",
    "RUNTIME_SHUTDOWN_REQUESTED",
    "RUNTIME_SHUTDOWN_STARTED",
    "RUNTIME_SHUTDOWN_COMPLETED",
]
