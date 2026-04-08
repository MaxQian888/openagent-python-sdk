"""Plugin decorators for easy registration.

Usage:
    @tool
    async def my_tool(params, context):
        '''My tool description'''
        return {"result": "ok"}

    @tool(name="custom_name")
    async def another_tool(params, context):
        ...

    @memory
    class MyMemory:
        async def inject(self, context): ...
        async def writeback(self, context): ...
        async def retrieve(self, query, context): ...

    @pattern
    class MyPattern:
        async def execute(self): ...

    @runtime
    class MyRuntime:
        async def run(self, ...): ...

    @session
    class MySession:
        ...
"""

from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar, overload

# Global registries for decorated plugins
_TOOL_REGISTRY: dict[str, type] = {}
_PATTERN_REGISTRY: dict[str, type] = {}
_MEMORY_REGISTRY: dict[str, type] = {}
_SKILL_REGISTRY: dict[str, type] = {}
_RUNTIME_REGISTRY: dict[str, type] = {}
_SESSION_REGISTRY: dict[str, type] = {}
_EVENT_REGISTRY: dict[str, type] = {}


# Type helpers
F = TypeVar("F", bound=Callable[..., Any])


def tool(name: str | None = None, description: str = ""):
    """Decorator to register a tool function or class.

    Usage:
        @tool
        async def my_tool(params, context):
            return {"result": "ok"}

        @tool(name="search", description="Search the web")
        async def search_tool(params, context):
            ...
    """
    # Support both @tool and @tool() syntax
    # If name is a callable (function/class), we're being used as @tool (not @tool())
    if callable(name):
        fn_or_cls = name
        tool_name = getattr(fn_or_cls, "__name__", fn_or_cls.__class__.__name__ if not callable(fn_or_cls) else "tool")
        _TOOL_REGISTRY[tool_name] = fn_or_cls
        if callable(fn_or_cls):
            fn_or_cls._tool_name = tool_name
            fn_or_cls._tool_description = ""
            fn_or_cls._is_tool = True
        return fn_or_cls

    def decorator(fn_or_cls: F) -> F:
        tool_name = name or getattr(fn_or_cls, "__name__", fn_or_cls.__class__.__name__ if not callable(fn_or_cls) else "tool")
        _TOOL_REGISTRY[tool_name] = fn_or_cls

        # Attach metadata
        if callable(fn_or_cls):
            fn_or_cls._tool_name = tool_name
            fn_or_cls._tool_description = description
            fn_or_cls._is_tool = True

        return fn_or_cls
    return decorator


def pattern(name: str | None = None):
    """Decorator to register a pattern class.

    Usage:
        @pattern
        class MyPattern:
            async def execute(self):
                ...

            async def react(self):
                ...

        # Or with custom name:
        @pattern(name="custom")
        class CustomPattern:
            ...
    """
    # Support both @pattern and @pattern() syntax
    if isinstance(name, type):
        cls = name
        pattern_name = cls.__name__
        _PATTERN_REGISTRY[pattern_name] = cls
        cls._pattern_name = pattern_name
        cls._is_pattern = True
        return cls

    def decorator(cls: type) -> type:
        pattern_name = name or cls.__name__
        _PATTERN_REGISTRY[pattern_name] = cls

        cls._pattern_name = pattern_name
        cls._is_pattern = True
        return cls
    return decorator


def memory(name: str | None = None):
    """Decorator to register a memory class.

    Usage:
        @memory
        class MyMemory:
            async def inject(self, context):
                '''Inject memory into context'''
                context.memory_view["history"] = [...]

            async def writeback(self, context):
                '''Save current interaction'''
                ...

            async def retrieve(self, query, context):
                '''Search memory for relevant info'''
                return [...]

        # Or with custom name:
        @memory(name="custom")
        class CustomMemory:
            ...
    """
    # Support both @memory and @memory() syntax
    # If name is actually a class, we're being used as @memory (not @memory())
    if isinstance(name, type):
        cls = name
        memory_name = cls.__name__
        _MEMORY_REGISTRY[memory_name] = cls
        cls._memory_name = memory_name
        cls._is_memory = True
        return cls

    def decorator(cls: type) -> type:
        memory_name = name or cls.__name__
        _MEMORY_REGISTRY[memory_name] = cls

        cls._memory_name = memory_name
        cls._is_memory = True
        return cls
    return decorator


def runtime(name: str | None = None):
    """Decorator to register a runtime class.

    Usage:
        @runtime
        class MyRuntime:
            async def run(self, agent_id, session_id, input_text, ...):
                ...

        # Or with custom name:
        @runtime(name="custom")
        class CustomRuntime:
            ...
    """
    # Support both @runtime and @runtime() syntax
    if isinstance(name, type):
        cls = name
        runtime_name = cls.__name__
        _RUNTIME_REGISTRY[runtime_name] = cls
        cls._runtime_name = runtime_name
        cls._is_runtime = True
        return cls

    def decorator(cls: type) -> type:
        runtime_name = name or cls.__name__
        _RUNTIME_REGISTRY[runtime_name] = cls

        cls._runtime_name = runtime_name
        cls._is_runtime = True
        return cls
    return decorator


def skill(name: str | None = None):
    """Decorator to register a skill class.

    Usage:
        @skill
        class MySkill:
            def get_system_prompt(self, context=None):
                return "..."

        @skill(name="alchemy")
        class AlchemySkill:
            ...
    """
    if isinstance(name, type):
        cls = name
        skill_name = cls.__name__
        _SKILL_REGISTRY[skill_name] = cls
        cls._skill_name = skill_name
        cls._is_skill = True
        return cls

    def decorator(cls: type) -> type:
        skill_name = name or cls.__name__
        _SKILL_REGISTRY[skill_name] = cls

        cls._skill_name = skill_name
        cls._is_skill = True
        return cls

    return decorator


def session(name: str | None = None):
    """Decorator to register a session manager class.

    Usage:
        @session
        class MySession:
            async def get_state(self, session_id):
                ...

            async def set_state(self, session_id, state):
                ...

        # Or with custom name:
        @session(name="custom")
        class CustomSession:
            ...
    """
    # Support both @session and @session() syntax
    if isinstance(name, type):
        cls = name
        session_name = cls.__name__
        _SESSION_REGISTRY[session_name] = cls
        cls._session_name = session_name
        cls._is_session = True
        return cls

    def decorator(cls: type) -> type:
        session_name = name or cls.__name__
        _SESSION_REGISTRY[session_name] = cls

        cls._session_name = session_name
        cls._is_session = True
        return cls
    return decorator


def event_bus(name: str | None = None):
    """Decorator to register an event bus class.

    Usage:
        @event_bus
        class MyEventBus:
            async def emit(self, event_name, **payload):
                ...

            def subscribe(self, event_name, handler):
                ...

        # Or with custom name:
        @event_bus(name="custom")
        class CustomEventBus:
            ...
    """
    # Support both @event_bus and @event_bus() syntax
    if isinstance(name, type):
        cls = name
        event_name = cls.__name__
        _EVENT_REGISTRY[event_name] = cls
        cls._event_name = event_name
        cls._is_event_bus = True
        return cls

    def decorator(cls: type) -> type:
        event_name = name or cls.__name__
        _EVENT_REGISTRY[event_name] = cls

        cls._event_name = event_name
        cls._is_event_bus = True
        return cls
    return decorator


def get_tool(name: str) -> type | None:
    """Get a registered tool by name."""
    return _TOOL_REGISTRY.get(name)


def get_pattern(name: str) -> type | None:
    """Get a registered pattern by name."""
    return _PATTERN_REGISTRY.get(name)


def get_memory(name: str) -> type | None:
    """Get a registered memory by name."""
    return _MEMORY_REGISTRY.get(name)


def get_runtime(name: str) -> type | None:
    """Get a registered runtime by name."""
    return _RUNTIME_REGISTRY.get(name)


def get_skill(name: str) -> type | None:
    """Get a registered skill by name."""
    return _SKILL_REGISTRY.get(name)


def get_session(name: str) -> type | None:
    """Get a registered session by name."""
    return _SESSION_REGISTRY.get(name)


def get_event_bus(name: str) -> type | None:
    """Get a registered event bus by name."""
    return _EVENT_REGISTRY.get(name)


def list_tools() -> list[str]:
    """List all registered tool names."""
    return list(_TOOL_REGISTRY.keys())


def list_patterns() -> list[str]:
    """List all registered pattern names."""
    return list(_PATTERN_REGISTRY.keys())


def list_memories() -> list[str]:
    """List all registered memory names."""
    return list(_MEMORY_REGISTRY.keys())


def list_runtimes() -> list[str]:
    """List all registered runtime names."""
    return list(_RUNTIME_REGISTRY.keys())


def list_skills() -> list[str]:
    """List all registered skill names."""
    return list(_SKILL_REGISTRY.keys())


def list_sessions() -> list[str]:
    """List all registered session names."""
    return list(_SESSION_REGISTRY.keys())


def list_event_buses() -> list[str]:
    """List all registered event bus names."""
    return list(_EVENT_REGISTRY.keys())
