"""Shared exception types."""

from __future__ import annotations

from typing import Self


class OpenAgentsError(Exception):
    """Base exception for SDK errors."""

    agent_id: str | None
    session_id: str | None
    run_id: str | None
    tool_id: str | None
    step_number: int | None

    def __init__(
        self,
        message: str = "",
        *,
        agent_id: str | None = None,
        session_id: str | None = None,
        run_id: str | None = None,
        tool_id: str | None = None,
        step_number: int | None = None,
    ) -> None:
        super().__init__(message)
        self.agent_id = agent_id
        self.session_id = session_id
        self.run_id = run_id
        self.tool_id = tool_id
        self.step_number = step_number

    def with_context(self, **kwargs: str | int | None) -> Self:
        """Attach runtime identifiers to an existing exception."""

        for key in ("agent_id", "session_id", "run_id", "tool_id", "step_number"):
            if key in kwargs:
                setattr(self, key, kwargs[key])
        return self


class ConfigError(OpenAgentsError):
    """Raised when config parsing or validation fails."""


class ConfigValidationError(ConfigError):
    """Raised when a config payload violates the schema."""


class ConfigLoadError(ConfigError):
    """Raised when a config file cannot be read or decoded."""


class PluginError(OpenAgentsError):
    """Base exception for plugin loading and validation failures."""


class PluginLoadError(PluginError):
    """Raised when plugin loading fails."""


class PluginCapabilityError(PluginError):
    """Raised when plugin capabilities do not meet requirements."""


class PluginConfigError(PluginError):
    """Raised when plugin config is invalid."""


class ExecutionError(OpenAgentsError):
    """Base exception for runtime execution failures."""


class MaxStepsExceeded(ExecutionError):
    """Raised when a step or tool-call budget is exceeded."""


class BudgetExhausted(ExecutionError):
    """Raised when runtime budget limits are exceeded."""


class SessionError(ExecutionError):
    """Raised when session management fails."""


class PatternError(ExecutionError):
    """Raised when a pattern fails during execution."""


class ToolError(OpenAgentsError):
    """Base exception for tool errors."""

    tool_name: str

    def __init__(self, message: str, tool_name: str = "") -> None:
        super().__init__(message, tool_id=tool_name or None)
        self.tool_name = tool_name


class RetryableToolError(ToolError):
    """Tool error that can be retried."""


class PermanentToolError(ToolError):
    """Tool error that should not be retried."""


class ToolTimeoutError(RetryableToolError):
    """Raised when a tool execution times out."""


class ToolNotFoundError(PermanentToolError):
    """Raised when a requested tool is not registered."""


class LLMError(OpenAgentsError):
    """Base exception for LLM/provider failures."""


class LLMConnectionError(LLMError):
    """Raised when a provider connection fails."""


class LLMRateLimitError(LLMError):
    """Raised when a provider rate-limits a request."""


class LLMResponseError(LLMError):
    """Raised when a provider returns an invalid response."""


class ModelRetryError(LLMError):
    """Raised when the model should retry with corrected input."""


class UserError(OpenAgentsError):
    """Raised for caller-side mistakes."""


class InvalidInputError(UserError):
    """Raised when caller-provided input is invalid."""


class AgentNotFoundError(UserError):
    """Raised when the requested agent does not exist."""


# Backward-compatible alias kept during the migration.
CapabilityError = PluginCapabilityError
