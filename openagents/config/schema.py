"""Schema models for config-as-code agent definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _to_dict(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"'{field_name}' must be an object")
    return value


def _to_str_or_none(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"'{field_name}' must be a string")
    stripped = value.strip()
    return stripped or None


@dataclass
class PluginRef:
    type: str | None = None
    impl: str | None = None
    config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any], field_name: str) -> "PluginRef":
        if not isinstance(data, dict):
            raise ValueError(f"'{field_name}' must be an object")
        return cls(
            type=_to_str_or_none(data.get("type"), f"{field_name}.type"),
            impl=_to_str_or_none(data.get("impl"), f"{field_name}.impl"),
            config=_to_dict(data.get("config"), f"{field_name}.config"),
        )


@dataclass
class MemoryRef(PluginRef):
    on_error: str = "continue"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryRef":
        base = PluginRef.from_dict(data, "memory")
        on_error = data.get("on_error", "continue")
        if not isinstance(on_error, str):
            raise ValueError("'memory.on_error' must be a string")
        return cls(
            type=base.type,
            impl=base.impl,
            config=base.config,
            on_error=on_error.strip() or "continue",
        )


@dataclass
class PatternRef(PluginRef):
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PatternRef":
        base = PluginRef.from_dict(data, "pattern")
        return cls(type=base.type, impl=base.impl, config=base.config)


@dataclass
class ToolRef(PluginRef):
    id: str = ""
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any], index: int) -> "ToolRef":
        if not isinstance(data, dict):
            raise ValueError(f"'tools[{index}]' must be an object")
        base = PluginRef.from_dict(data, f"tools[{index}]")
        tool_id = data.get("id")
        if not isinstance(tool_id, str) or not tool_id.strip():
            raise ValueError(f"'tools[{index}].id' must be a non-empty string")
        enabled = data.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError(f"'tools[{index}].enabled' must be a boolean")
        return cls(
            id=tool_id.strip(),
            enabled=enabled,
            type=base.type,
            impl=base.impl,
            config=base.config,
        )


@dataclass
class RuntimeOptions:
    max_steps: int = 16
    step_timeout_ms: int = 30000
    session_queue_size: int = 1000
    event_queue_size: int = 2000

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "RuntimeOptions":
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError("'runtime' must be an object")
        return cls(
            max_steps=data.get("max_steps", 16),
            step_timeout_ms=data.get("step_timeout_ms", 30000),
            session_queue_size=data.get("session_queue_size", 1000),
            event_queue_size=data.get("event_queue_size", 2000),
        )


@dataclass
class LLMOptions:
    provider: str = "mock"
    model: str | None = None
    api_base: str | None = None
    api_key_env: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_ms: int = 30000
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LLMOptions | None":
        if data is None:
            return None
        if not isinstance(data, dict):
            raise ValueError("'llm' must be an object")
        provider = data.get("provider", "mock")
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("'llm.provider' must be a non-empty string")
        model = data.get("model")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise ValueError("'llm.model' must be a non-empty string when provided")
        api_base = data.get("api_base")
        if api_base is not None and (not isinstance(api_base, str) or not api_base.strip()):
            raise ValueError("'llm.api_base' must be a non-empty string when provided")
        api_key_env = data.get("api_key_env")
        if api_key_env is not None and (
            not isinstance(api_key_env, str) or not api_key_env.strip()
        ):
            raise ValueError("'llm.api_key_env' must be a non-empty string when provided")
        temperature = data.get("temperature")
        if temperature is not None and not isinstance(temperature, (int, float)):
            raise ValueError("'llm.temperature' must be a number when provided")
        max_tokens = data.get("max_tokens")
        if max_tokens is not None and (not isinstance(max_tokens, int) or max_tokens <= 0):
            raise ValueError("'llm.max_tokens' must be a positive integer when provided")
        timeout_ms = data.get("timeout_ms", 30000)
        if not isinstance(timeout_ms, int) or timeout_ms <= 0:
            raise ValueError("'llm.timeout_ms' must be a positive integer")

        known = {
            "provider",
            "model",
            "api_base",
            "api_key_env",
            "temperature",
            "max_tokens",
            "timeout_ms",
        }
        extra = {k: v for k, v in data.items() if k not in known}
        return cls(
            provider=provider.strip(),
            model=model.strip() if isinstance(model, str) else None,
            api_base=api_base.strip() if isinstance(api_base, str) else None,
            api_key_env=api_key_env.strip() if isinstance(api_key_env, str) else None,
            temperature=float(temperature) if temperature is not None else None,
            max_tokens=max_tokens,
            timeout_ms=timeout_ms,
            extra=extra,
        )


@dataclass
class AgentDefinition:
    id: str
    name: str
    memory: MemoryRef
    pattern: PatternRef
    llm: LLMOptions | None = None
    tools: list[ToolRef] = field(default_factory=list)
    runtime: RuntimeOptions = field(default_factory=RuntimeOptions)

    @classmethod
    def from_dict(cls, data: dict[str, Any], index: int) -> "AgentDefinition":
        if not isinstance(data, dict):
            raise ValueError(f"'agents[{index}]' must be an object")

        agent_id = data.get("id")
        if not isinstance(agent_id, str) or not agent_id.strip():
            raise ValueError(f"'agents[{index}].id' must be a non-empty string")

        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"'agents[{index}].name' must be a non-empty string")

        memory = data.get("memory")
        pattern = data.get("pattern")
        llm = data.get("llm")
        tools_raw = data.get("tools", [])
        if not isinstance(tools_raw, list):
            raise ValueError(f"'agents[{index}].tools' must be an array")

        return cls(
            id=agent_id.strip(),
            name=name.strip(),
            memory=MemoryRef.from_dict(memory if isinstance(memory, dict) else {}),
            pattern=PatternRef.from_dict(pattern if isinstance(pattern, dict) else {}),
            llm=LLMOptions.from_dict(llm),
            tools=[ToolRef.from_dict(item, i) for i, item in enumerate(tools_raw)],
            runtime=RuntimeOptions.from_dict(data.get("runtime")),
        )


@dataclass
class AppConfig:
    version: str = "1.0"
    agents: list[AgentDefinition] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        if not isinstance(data, dict):
            raise ValueError("Config root must be an object")
        version = data.get("version", "1.0")
        if not isinstance(version, str) or not version.strip():
            raise ValueError("'version' must be a non-empty string")

        agents_raw = data.get("agents", [])
        if not isinstance(agents_raw, list):
            raise ValueError("'agents' must be an array")

        agents = [AgentDefinition.from_dict(item, idx) for idx, item in enumerate(agents_raw)]
        return cls(version=version.strip(), agents=agents)
