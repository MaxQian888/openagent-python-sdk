"""Runtime plugin contract - core execution orchestration."""

from __future__ import annotations

from typing import Any

from .plugin import BasePlugin


class RuntimePlugin(BasePlugin):
    """Base runtime plugin.

    Implementations control the execution lifecycle, orchestration flow,
    and how agents are run. Runtime is the top-level coordinator.
    """

    async def initialize(self) -> None:
        """Initialize runtime before first use.

        Called once during Runtime startup. Use for:
        - Loading configurations
        - Establishing connections
        - Setting up resources
        """
        pass

    async def validate(self) -> None:
        """Validate runtime configuration.

        Called after initialize(). Should raise if configuration is invalid.
        """
        pass

    async def health_check(self) -> bool:
        """Check runtime health status.

        Returns:
            True if runtime is healthy, False otherwise
        """
        return True

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

    async def pause(self) -> None:
        """Pause runtime execution.

        Suspends any ongoing runs. State should be preserved.
        """
        pass

    async def resume(self) -> None:
        """Resume runtime execution.

        Continues previously paused runs.
        """
        pass

    async def close(self) -> None:
        """Cleanup runtime resources.

        Called during Runtime shutdown. Use for:
        - Closing connections
        - Flushing buffers
        - Releasing resources
        """
        pass


# Capability constants for runtime plugins
RUNTIME_RUN = "runtime.run"
RUNTIME_MANAGE = "runtime.manage"  # start/stop/pause runtime
RUNTIME_LIFECYCLE = "runtime.lifecycle"  # initialize/validate/health_check
