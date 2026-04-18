"""Builtin execution policy helpers.

These are standalone helper classes (not plugins). They are intended to be
embedded inside a ``ToolExecutorPlugin.evaluate_policy()`` override, or used
via ``FilesystemAwareExecutor`` (a builtin executor that wraps
``FilesystemExecutionPolicy``).
"""

from .composite import CompositePolicy
from .filesystem import FilesystemExecutionPolicy
from .network import NetworkAllowlistExecutionPolicy

__all__ = [
    "FilesystemExecutionPolicy",
    "CompositePolicy",
    "NetworkAllowlistExecutionPolicy",
]
