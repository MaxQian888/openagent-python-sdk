"""Plugin loader and capability checks."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

from openagents.config.schema import (
    AgentDefinition,
    EventBusRef,
    MemoryRef,
    PatternRef,
    PluginRef,
    RuntimeRef,
    SessionRef,
    ToolRef,
)
from openagents.interfaces.capabilities import (
    MEMORY_INJECT,
    MEMORY_WRITEBACK,
    PATTERN_EXECUTE,
    PATTERN_REACT,
    TOOL_INVOKE,
    normalize_capabilities,
)
from openagents.interfaces.runtime import RUNTIME_RUN
from openagents.interfaces.session import SESSION_MANAGE
from openagents.interfaces.events import EVENT_EMIT, EVENT_SUBSCRIBE
from openagents.errors.exceptions import CapabilityError, PluginLoadError
from openagents.plugins.registry import get_builtin_plugin_class


@dataclass
class LoadedAgentPlugins:
    memory: Any
    pattern: Any
    tools: dict[str, Any]


@dataclass
class LoadedRuntimeComponents:
    runtime: Any
    session: Any
    events: Any


def _import_symbol(path: str) -> Any:
    if "." not in path:
        raise PluginLoadError(f"Invalid impl path: '{path}'")
    module_name, attr_name = path.rsplit(".", 1)
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # pragma: no cover - defensive
        raise PluginLoadError(f"Failed to import module '{module_name}'") from exc
    try:
        return getattr(module, attr_name)
    except AttributeError as exc:
        raise PluginLoadError(f"Module '{module_name}' has no symbol '{attr_name}'") from exc


def _instantiate(factory: Any, config: dict[str, Any]) -> Any:
    if not callable(factory):
        return factory
    for call in (
        lambda: factory(config=config),
        lambda: factory(config),
        lambda: factory(),
    ):
        try:
            return call()
        except TypeError:
            continue
    raise PluginLoadError(f"Could not instantiate plugin from {factory!r}")


def _load_plugin(kind: str, ref: PluginRef) -> Any:
    if ref.type:
        plugin_cls = get_builtin_plugin_class(kind, ref.type)
        if plugin_cls is None:
            raise PluginLoadError(f"Unknown builtin {kind} plugin type: '{ref.type}'")
        return _instantiate(plugin_cls, ref.config)
    if ref.impl:
        symbol = _import_symbol(ref.impl)
        return _instantiate(symbol, ref.config)
    raise PluginLoadError(f"{kind} plugin must set one of 'type' or 'impl'")


def _capability_set(plugin: Any) -> set[str]:
    return normalize_capabilities(getattr(plugin, "capabilities", set()))


def _validate_method_for_capability(plugin: Any, capability: str, method_name: str) -> None:
    capabilities = _capability_set(plugin)
    if capability in capabilities and not callable(getattr(plugin, method_name, None)):
        raise CapabilityError(
            f"Plugin '{type(plugin).__name__}' declares '{capability}' "
            f"but does not implement '{method_name}'"
        )


def _validate_required_capabilities(
    plugin: Any,
    required: set[str],
    where: str,
) -> None:
    missing = required - _capability_set(plugin)
    if missing:
        raise CapabilityError(
            f"{where} is missing required capabilities: {sorted(missing)}"
        )


def load_memory_plugin(ref: MemoryRef) -> Any:
    plugin = _load_plugin("memory", ref)
    _validate_method_for_capability(plugin, MEMORY_INJECT, "inject")
    _validate_method_for_capability(plugin, MEMORY_WRITEBACK, "writeback")
    return plugin


def load_pattern_plugin(ref: PatternRef) -> Any:
    plugin = _load_plugin("pattern", ref)
    _validate_required_capabilities(plugin, {PATTERN_EXECUTE}, "pattern plugin")
    _validate_method_for_capability(plugin, PATTERN_EXECUTE, "execute")
    _validate_method_for_capability(plugin, PATTERN_REACT, "react")
    return plugin


def load_tool_plugin(ref: ToolRef) -> Any:
    plugin = _load_plugin("tool", ref)
    _validate_required_capabilities(plugin, {TOOL_INVOKE}, f"tool plugin '{ref.id}'")
    _validate_method_for_capability(plugin, TOOL_INVOKE, "invoke")
    return plugin


def load_agent_plugins(agent: AgentDefinition) -> LoadedAgentPlugins:
    memory = load_memory_plugin(agent.memory)
    pattern = load_pattern_plugin(agent.pattern)

    tools: dict[str, Any] = {}
    for tool_ref in agent.tools:
        if not tool_ref.enabled:
            continue
        tools[tool_ref.id] = load_tool_plugin(tool_ref)

    return LoadedAgentPlugins(memory=memory, pattern=pattern, tools=tools)


def load_runtime_plugin(ref: RuntimeRef) -> Any:
    """Load a runtime plugin."""
    plugin = _load_plugin("runtime", ref)
    _validate_required_capabilities(plugin, {RUNTIME_RUN}, "runtime plugin")
    _validate_method_for_capability(plugin, RUNTIME_RUN, "run")
    return plugin


def load_session_plugin(ref: SessionRef) -> Any:
    """Load a session manager plugin."""
    plugin = _load_plugin("session", ref)
    _validate_required_capabilities(plugin, {SESSION_MANAGE}, "session plugin")
    _validate_method_for_capability(plugin, SESSION_MANAGE, "session")
    return plugin


def load_events_plugin(ref: EventBusRef) -> Any:
    """Load an event bus plugin."""
    plugin = _load_plugin("events", ref)
    _validate_required_capabilities(plugin, {EVENT_EMIT}, "event bus plugin")
    _validate_method_for_capability(plugin, EVENT_EMIT, "emit")
    _validate_method_for_capability(plugin, EVENT_SUBSCRIBE, "subscribe")
    return plugin


def load_runtime_components(
    runtime_ref: RuntimeRef | None,
    session_ref: SessionRef | None,
    events_ref: EventBusRef | None,
) -> LoadedRuntimeComponents:
    """Load all runtime components from config references.

    Uses defaults if refs are None.
    Handles dependency injection between components.
    """
    from openagents.config.schema import EventBusRef as DefaultEventBusRef
    from openagents.config.schema import RuntimeRef as DefaultRuntimeRef
    from openagents.config.schema import SessionRef as DefaultSessionRef

    # Load events first (no dependencies)
    events = load_events_plugin(events_ref or DefaultEventBusRef(type="async"))

    # Load session (no dependencies)
    session = load_session_plugin(session_ref or DefaultSessionRef(type="in_memory"))

    # Load runtime with injected dependencies
    runtime = load_runtime_plugin(runtime_ref or DefaultRuntimeRef(type="default"))

    # Inject dependencies into runtime if it supports it
    if hasattr(runtime, "_event_bus"):
        runtime._event_bus = events
    if hasattr(runtime, "_session_manager"):
        runtime._session_manager = session

    return LoadedRuntimeComponents(runtime=runtime, session=session, events=events)


