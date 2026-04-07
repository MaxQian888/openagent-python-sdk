"""Tool plugin contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol, runtime_checkable

from .plugin import BasePlugin


# Tool Error Types
class ToolError(Exception):
    """Base exception for tool errors."""

    tool_name: str = ""

    def __init__(self, message: str, tool_name: str = ""):
        super().__init__(message)
        self.tool_name = tool_name


class RetryableToolError(ToolError):
    """Tool error that can be retried.

    Examples: timeout, rate limit, temporary unavailability
    """

    pass


class PermanentToolError(ToolError):
    """Tool error that should not be retried.

    Examples: invalid parameters, permission denied, resource not found
    """

    pass


@dataclass
class ToolResult:
    """Standardized tool result."""

    success: bool
    data: Any = None
    error: str | None = None
    tool_name: str = ""


@dataclass
class ToolExecutionSpec:
    """Execution metadata for a tool."""

    concurrency_safe: bool = False
    interrupt_behavior: str = "block"
    side_effects: str = "unknown"
    approval_mode: str = "inherit"
    default_timeout_ms: int | None = None
    reads_files: bool = False
    writes_files: bool = False


@dataclass
class PolicyDecision:
    """Tool execution policy decision."""

    allowed: bool
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolExecutionRequest:
    """Structured request for tool execution."""

    tool_id: str
    tool: Any
    params: dict[str, Any] = field(default_factory=dict)
    context: Any = None
    execution_spec: ToolExecutionSpec = field(default_factory=ToolExecutionSpec)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolExecutionResult:
    """Structured result for tool execution."""

    tool_id: str
    success: bool
    data: Any = None
    error: str | None = None
    exception: Exception | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ExecutionPolicy(Protocol):
    """Policy hook for tool execution."""

    async def evaluate(self, request: ToolExecutionRequest) -> PolicyDecision: ...


@runtime_checkable
class ToolExecutor(Protocol):
    """Executor hook between patterns and tool implementations."""

    async def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult: ...

    async def execute_stream(
        self,
        request: ToolExecutionRequest,
    ) -> AsyncIterator[dict[str, Any]]: ...


class ExecutionPolicyPlugin(BasePlugin):
    """Optional base class for execution policies."""

    async def evaluate(self, request: ToolExecutionRequest) -> PolicyDecision:
        return PolicyDecision(allowed=True)


class ToolExecutorPlugin(BasePlugin):
    """Optional base class for tool executors."""

    async def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        try:
            data = await request.tool.invoke(request.params or {}, request.context)
            return ToolExecutionResult(tool_id=request.tool_id, success=True, data=data)
        except Exception as exc:
            return ToolExecutionResult(
                tool_id=request.tool_id,
                success=False,
                error=str(exc),
                exception=exc,
            )

    async def execute_stream(
        self,
        request: ToolExecutionRequest,
    ) -> AsyncIterator[dict[str, Any]]:
        async for chunk in request.tool.invoke_stream(request.params or {}, request.context):
            yield chunk


class ToolPlugin(BasePlugin):
    """Base tool plugin."""

    # Subclasses can override these
    name: str = ""
    description: str = ""

    @property
    def tool_name(self) -> str:
        """Tool name, defaults to class name."""
        return self.name or self.__class__.__name__

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        """Execute tool call synchronously.

        Args:
            params: Tool input parameters
            context: Execution context

        Returns:
            Tool result
        """
        raise NotImplementedError("ToolPlugin.invoke must be implemented")

    def execution_spec(self) -> ToolExecutionSpec:
        """Return execution metadata for this tool."""
        return ToolExecutionSpec()

    async def invoke_stream(
        self, params: dict[str, Any], context: Any
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute tool call with streaming output.

        Yields partial results as they become available.

        Args:
            params: Tool input parameters
            context: Execution context

        Yields:
            Partial tool results
        """
        # Default: fall back to non-streaming invoke
        result = await self.invoke(params, context)
        yield {"type": "result", "data": result}

    def schema(self) -> dict[str, Any]:
        """Return JSON Schema for tool parameters.

        Returns:
            JSON Schema object describing input parameters
        """
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def describe(self) -> dict[str, Any]:
        """Return tool description for LLM consumption.

        Returns:
            Tool description including name, purpose, and parameter info
        """
        return {
            "name": self.name or self.__class__.__name__,
            "description": self.description or "",
            "parameters": self.schema(),
        }

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, str | None]:
        """Validate tool parameters.

        Args:
            params: Parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Default implementation: no validation
        return True, None

    def get_dependencies(self) -> list[str]:
        """Get list of tool IDs this tool depends on.

        Returns:
            List of tool IDs that must be available
        """
        return []

    async def fallback(
        self,
        error: Exception,
        params: dict[str, Any],
        context: Any,
    ) -> Any:
        """Fallback handler when invoke fails.

        Called when primary invoke raises an exception. Implementations
        can provide degraded functionality or graceful error responses.

        The context object can contain:
        - pattern: Current PatternPlugin instance (if any)
        - runtime: Current RuntimePlugin instance (if any)
        - session_id: Current session ID
        - agent_id: Current agent ID
        - Any other runtime-specific data

        Args:
            error: The exception raised by invoke
            params: Original parameters passed to invoke
            context: Extended execution context (may include pattern, runtime, etc.)

        Returns:
            Fallback result, or re-raise the original error if no fallback available
        """
        raise error
