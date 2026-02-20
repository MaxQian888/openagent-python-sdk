"""Session isolation and locking."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator


class SessionManager:
    """Provide per-session serialization with async locks."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._states: dict[str, dict] = {}

    def get_state(self, session_id: str) -> dict:
        state = self._states.get(session_id)
        if state is None:
            state = {}
            self._states[session_id] = state
        return state

    @asynccontextmanager
    async def session(self, session_id: str) -> AsyncIterator[dict]:
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        await lock.acquire()
        try:
            yield self.get_state(session_id)
        finally:
            lock.release()

