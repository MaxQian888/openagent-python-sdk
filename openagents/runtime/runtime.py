"""Runtime entrypoint and orchestration flow."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from openagents.config.loader import load_config
from openagents.config.schema import AgentDefinition, AppConfig
from openagents.interfaces.capabilities import MEMORY_INJECT, MEMORY_WRITEBACK
from openagents.errors.exceptions import ConfigError
from openagents.llm.registry import create_llm_client
from openagents.plugins.loader import load_agent_plugins

from .dispatcher import supports
from .event_bus import EventBus
from .execution_context import ExecutionContext
from .lifecycle import (
    CONTEXT_CREATED,
    MEMORY_INJECT_FAILED,
    MEMORY_INJECTED,
    MEMORY_WRITEBACK_FAILED,
    MEMORY_WRITEBACK_SUCCEEDED,
    PATTERN_STEP_FINISHED,
    PATTERN_STEP_STARTED,
    RUN_COMPLETED,
    RUN_FAILED,
    RUN_REQUESTED,
    RUN_VALIDATED,
    SESSION_ACQUIRED,
)
from .session_manager import SessionManager


class Runtime:
    """Single entrypoint for running configured agents."""

    def __init__(self, config: AppConfig, event_bus: EventBus | None = None):
        self._config = config
        self._agents_by_id: dict[str, AgentDefinition] = {a.id: a for a in config.agents}
        self._llm_clients: dict[str, Any | None] = {}
        self.event_bus = event_bus or EventBus()
        self.session_manager = SessionManager()

    @classmethod
    def from_config(cls, config_path: str | Path) -> "Runtime":
        return cls(load_config(config_path))

    async def run(self, *, agent_id: str, session_id: str, input_text: str) -> Any:
        agent = self._agents_by_id.get(agent_id)
        if agent is None:
            raise ConfigError(f"Unknown agent id: '{agent_id}'")

        await self.event_bus.emit(
            RUN_REQUESTED,
            agent_id=agent_id,
            session_id=session_id,
            input_text=input_text,
        )

        plugins = load_agent_plugins(agent)
        llm_client = self._get_llm_client(agent)
        await self.event_bus.emit(
            RUN_VALIDATED,
            agent_id=agent_id,
            session_id=session_id,
        )

        try:
            async with self.session_manager.session(session_id) as session_state:
                await self.event_bus.emit(
                    SESSION_ACQUIRED,
                    agent_id=agent_id,
                    session_id=session_id,
                )

                context = ExecutionContext(
                    agent_id=agent_id,
                    session_id=session_id,
                    input_text=input_text,
                    state=session_state,
                    tools=plugins.tools,
                    llm_client=llm_client,
                    llm_options=agent.llm,
                    event_bus=self.event_bus,
                )
                context.state.pop("_runtime_last_output", None)
                await self.event_bus.emit(
                    CONTEXT_CREATED,
                    agent_id=agent_id,
                    session_id=session_id,
                )

                await self._run_memory_inject(agent=agent, memory=plugins.memory, context=context)
                result = await self._run_pattern_loop(agent=agent, pattern=plugins.pattern, context=context)
                await self._run_memory_writeback(agent=agent, memory=plugins.memory, context=context)

                await self.event_bus.emit(
                    RUN_COMPLETED,
                    agent_id=agent_id,
                    session_id=session_id,
                    result=result,
                )
                return result
        except Exception as exc:
            await self.event_bus.emit(
                RUN_FAILED,
                agent_id=agent_id,
                session_id=session_id,
                error=str(exc),
            )
            raise

    def _get_llm_client(self, agent: AgentDefinition) -> Any | None:
        if agent.id in self._llm_clients:
            return self._llm_clients[agent.id]
        client = create_llm_client(agent.llm)
        self._llm_clients[agent.id] = client
        return client

    async def _run_memory_inject(self, *, agent: AgentDefinition, memory: Any, context: ExecutionContext) -> None:
        if not supports(memory, MEMORY_INJECT):
            return
        try:
            await memory.inject(context)
            await self.event_bus.emit(
                MEMORY_INJECTED,
                agent_id=context.agent_id,
                session_id=context.session_id,
            )
        except Exception as exc:
            await self.event_bus.emit(
                MEMORY_INJECT_FAILED,
                agent_id=context.agent_id,
                session_id=context.session_id,
                error=str(exc),
            )
            if agent.memory.on_error == "fail":
                raise

    async def _run_memory_writeback(
        self,
        *,
        agent: AgentDefinition,
        memory: Any,
        context: ExecutionContext,
    ) -> None:
        if not supports(memory, MEMORY_WRITEBACK):
            return
        try:
            await memory.writeback(context)
            await self.event_bus.emit(
                MEMORY_WRITEBACK_SUCCEEDED,
                agent_id=context.agent_id,
                session_id=context.session_id,
            )
        except Exception as exc:
            await self.event_bus.emit(
                MEMORY_WRITEBACK_FAILED,
                agent_id=context.agent_id,
                session_id=context.session_id,
                error=str(exc),
            )
            if agent.memory.on_error == "fail":
                raise

    async def _run_pattern_loop(self, *, agent: AgentDefinition, pattern: Any, context: ExecutionContext) -> Any:
        allowed_action_types = {"tool_call", "final", "continue"}
        timeout_s = agent.runtime.step_timeout_ms / 1000
        for step in range(agent.runtime.max_steps):
            await self.event_bus.emit(
                PATTERN_STEP_STARTED,
                agent_id=context.agent_id,
                session_id=context.session_id,
                step=step,
            )
            try:
                action = await asyncio.wait_for(pattern.react(context), timeout=timeout_s)
            except asyncio.TimeoutError as exc:
                raise TimeoutError(
                    f"Pattern step timed out after {agent.runtime.step_timeout_ms}ms "
                    f"for agent '{agent.id}' at step {step}"
                ) from exc
            await self.event_bus.emit(
                PATTERN_STEP_FINISHED,
                agent_id=context.agent_id,
                session_id=context.session_id,
                step=step,
                action=action,
            )

            if not isinstance(action, dict):
                raise TypeError(f"Pattern action must be dict, got {type(action).__name__}")

            action_type = action.get("type")
            if not isinstance(action_type, str) or not action_type.strip():
                raise ValueError("Pattern action must include a non-empty string 'type'")
            if action_type not in allowed_action_types:
                raise ValueError(
                    f"Unsupported pattern action type: '{action_type}'. "
                    f"Allowed: {sorted(allowed_action_types)}"
                )

            if action_type == "tool_call":
                tool_id = action.get("tool") or action.get("tool_id")
                if not isinstance(tool_id, str) or not tool_id:
                    raise ValueError("tool_call action must include non-empty 'tool' or 'tool_id'")
                params = action.get("params", {})
                if params is None:
                    params = {}
                if not isinstance(params, dict):
                    raise ValueError("tool_call action 'params' must be an object")
                await context.call_tool(tool_id, params)
                continue

            if action_type == "final":
                content = action.get("content")
                context.state["_runtime_last_output"] = content
                return content

            # action_type == "continue"
            continue

        raise RuntimeError(
            f"Pattern exceeded max_steps ({agent.runtime.max_steps}) for agent '{agent.id}'"
        )

