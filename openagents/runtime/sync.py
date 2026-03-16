"""Synchronous runtime helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openagents.runtime.runtime import Runtime


def run_agent(
    config_path: str | Path,
    *,
    agent_id: str,
    session_id: str = "default",
    input_text: str,
) -> Any:
    """Synchronous agent execution.

    Convenience function for non-async contexts.
    Creates a Runtime from config and runs the agent synchronously.

    Args:
        config_path: Path to agent configuration JSON file
        agent_id: Agent ID to execute
        session_id: Session ID (default: "default")
        input_text: Input text for the agent

    Returns:
        Agent execution result

    Example:
        >>> result = run_agent("agent.json", agent_id="assistant", input_text="hello")
    """
    runtime = Runtime.from_config(config_path)
    return runtime.run_sync(agent_id=agent_id, session_id=session_id, input_text=input_text)


def run_agent_with_config(
    config: Any,
    *,
    agent_id: str,
    session_id: str = "default",
    input_text: str,
) -> Any:
    """Synchronous agent execution with pre-loaded config.

    Args:
        config: AppConfig object (from load_config())
        agent_id: Agent ID to execute
        session_id: Session ID (default: "default")
        input_text: Input text for the agent

    Returns:
        Agent execution result
    """
    runtime = Runtime(config, _skip_plugin_load=False)
    return runtime.run_sync(agent_id=agent_id, session_id=session_id, input_text=input_text)
