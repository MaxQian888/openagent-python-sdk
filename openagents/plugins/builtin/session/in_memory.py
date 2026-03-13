"""In-memory session manager implementation."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from openagents.interfaces.session import SESSION_MANAGE, SESSION_STATE, SessionManagerPlugin


class InMemorySessionManager(SessionManagerPlugin):
    """In-memory session manager with async locks.

    Sessions are stored in memory and will be lost on restart.
    Use for single-instance deployments or testing.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(
            config=config or {},
            capabilities={SESSION_MANAGE, SESSION_STATE},
        )
        self._locks: dict[str, asyncio.Lock] = {}
        self._states: dict[str, dict] = {}

    @asynccontextmanager
    async def session(self, session_id: str) -> AsyncIterator[dict[str, Any]]:
        """Acquire and manage a session with async lock."""
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        await lock.acquire()
        try:
            state = await self.get_state(session_id)
            yield state
        finally:
            lock.release()

    async def get_state(self, session_id: str) -> dict[str, Any]:
        """Get current session state."""
        state = self._states.get(session_id)
        if state is None:
            state = {}
            self._states[session_id] = state
        return state

    async def set_state(self, session_id: str, state: dict[str, Any]) -> None:
        """Set session state."""
        self._states[session_id] = state

    async def delete_session(self, session_id: str) -> None:
        """Delete a session and its state."""
        self._states.pop(session_id, None)

    async def list_sessions(self) -> list[str]:
        """List all active session IDs."""
        return list(self._states.keys())
