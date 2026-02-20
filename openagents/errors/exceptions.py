"""Shared exception types."""


class OpenAgentsError(Exception):
    """Base exception for SDK errors."""


class ConfigError(OpenAgentsError):
    """Raised when config parsing or validation fails."""


class PluginLoadError(OpenAgentsError):
    """Raised when plugin loading fails."""


class CapabilityError(OpenAgentsError):
    """Raised when plugin capabilities do not meet requirements."""

