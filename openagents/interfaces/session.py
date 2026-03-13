"""Session manager plugin contract - session lifecycle and isolation."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from .plugin import BasePlugin


class SessionManagerPlugin(BasePlugin):
    """Base session manager plugin.

    Implementations control session lifecycle, locking strategy,
    and state persistence. Enables distributed session management.
    """

    @asynccontextmanager
    async def session(self, session_id: str) -> AsyncIterator[dict[str, Any]]:
        """Acquire and manage a session.

        Args:
            session_id: Unique session identifier

        Yields:
            Session state dict that can be used to store/restore state
        """
        raise NotImplementedError("SessionManagerPlugin.session must be implemented")

    async def get_state(self, session_id: str) -> dict[str, Any]:
        """Get current session state without acquiring lock.

        Args:
            session_id: Session identifier

        Returns:
            Session state dict
        """
        raise NotImplementedError("SessionManagerPlugin.get_state must be implemented")

    async def set_state(self, session_id: str, state: dict[str, Any]) -> None:
        """Set session state.

        Args:
            session_id: Session identifier
            state: State dict to persist
        """
        raise NotImplementedError("SessionManagerPlugin.set_state must be implemented")

    async def delete_session(self, session_id: str) -> None:
        """Delete a session and its state.

        Args:
            session_id: Session identifier
        """
        raise NotImplementedError("SessionManagerPlugin.delete_session must be implemented")

    async def list_sessions(self) -> list[str]:
        """List all active session IDs.

        Returns:
            List of session IDs
        """
        raise NotImplementedError("SessionManagerPlugin.list_sessions must be implemented")

    async def close(self) -> None:
        """Cleanup session manager resources."""
        pass


# Capability constants
SESSION_MANAGE = "session.manage"
SESSION_STATE = "session.state"
