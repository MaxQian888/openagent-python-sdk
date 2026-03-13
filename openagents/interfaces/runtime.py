"""Runtime plugin contract - core execution orchestration."""

from __future__ import annotations

from typing import Any

from .plugin import BasePlugin


class RuntimePlugin(BasePlugin):
    """Base runtime plugin.

    Implementations control the execution lifecycle, orchestration flow,
    and how agents are run. Runtime is the top-level coordinator.
    """

    async def run(
        self,
        *,
        agent_id: str,
        session_id: str,
        input_text: str,
    ) -> Any:
        """Execute an agent run with the given inputs.

        Args:
            agent_id: The agent to run
            session_id: Session identifier for isolation
            input_text: User input

        Returns:
            The execution result
        """
        raise NotImplementedError("RuntimePlugin.run must be implemented")

    async def close(self) -> None:
        """Cleanup runtime resources."""
        pass


# Capability constants for runtime plugins
RUNTIME_RUN = "runtime.run"
RUNTIME_MANAGE = "runtime.manage"  # start/stop/pause runtime
