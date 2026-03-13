"""Runtime entrypoint and orchestration flow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openagents.config.loader import load_config
from openagents.config.schema import AgentDefinition, AppConfig
from openagents.errors.exceptions import ConfigError
from openagents.plugins.loader import load_runtime_components


class Runtime:
    """Main runtime entrypoint.

    Delegates to pluggable runtime/session/events components loaded from config.
    """

    def __init__(
        self,
        config: AppConfig,
        _skip_plugin_load: bool = False,  # Internal: skip for backward compat
    ):
        self._config = config
        self._agents_by_id: dict[str, AgentDefinition] = {a.id: a for a in config.agents}

        if _skip_plugin_load:
            # Backward compatibility mode - use builtins directly
            from openagents.plugins.builtin.events.async_event_bus import AsyncEventBus
            from openagents.plugins.builtin.runtime.default_runtime import DefaultRuntime
            from openagents.plugins.builtin.session.in_memory import InMemorySessionManager

            self._events = AsyncEventBus()
            self._session = InMemorySessionManager()
            self._runtime = DefaultRuntime(
                config={},
                event_bus=self._events,
                session_manager=self._session,
            )
        else:
            # Load plugins from config
            components = load_runtime_components(
                runtime_ref=config.runtime,
                session_ref=config.session,
                events_ref=config.events,
            )
            self._runtime = components.runtime
            self._session = components.session
            self._events = components.events

    @property
    def event_bus(self) -> Any:
        """Access the event bus instance."""
        return self._events

    @property
    def session_manager(self) -> Any:
        """Access the session manager instance."""
        return self._session

    @classmethod
    def from_config(cls, config_path: str | Path) -> "Runtime":
        return cls(load_config(config_path))

    async def run(self, *, agent_id: str, session_id: str, input_text: str) -> Any:
        """Execute an agent run."""
        agent = self._agents_by_id.get(agent_id)
        if agent is None:
            raise ConfigError(f"Unknown agent id: '{agent_id}'")

        # Delegate to the runtime plugin
        return await self._runtime.run(
            agent_id=agent_id,
            session_id=session_id,
            input_text=input_text,
            app_config=self._config,
            agents_by_id=self._agents_by_id,
        )

    async def close(self) -> None:
        """Cleanup runtime resources."""
        if hasattr(self._runtime, "close"):
            await self._runtime.close()
        if hasattr(self._session, "close"):
            await self._session.close()
        if hasattr(self._events, "close"):
            await self._events.close()
