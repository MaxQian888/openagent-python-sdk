import pytest

from openagents.config.loader import load_config_dict
from openagents.errors.exceptions import CapabilityError, PluginLoadError
from openagents.plugins.loader import load_agent_plugins


def _base_payload() -> dict:
    return {
        "version": "1.0",
        "agents": [
            {
                "id": "assistant",
                "name": "demo-agent",
                "memory": {"type": "window_buffer"},
                "pattern": {"type": "react"},
                "llm": {"provider": "mock"},
                "tools": [{"id": "search", "type": "builtin_search"}],
            }
        ],
    }


def test_load_agent_plugins_builtin_types():
    config = load_config_dict(_base_payload())
    plugins = load_agent_plugins(config.agents[0])

    assert type(plugins.memory).__name__ == "WindowBufferMemory"
    assert type(plugins.pattern).__name__ == "ReActPattern"
    assert "search" in plugins.tools
    assert type(plugins.tools["search"]).__name__ == "BuiltinSearchTool"


def test_load_agent_plugins_impl_types():
    payload = _base_payload()
    payload["agents"][0]["memory"] = {"impl": "tests.fixtures.custom_plugins.CustomMemory"}
    payload["agents"][0]["pattern"] = {"impl": "tests.fixtures.custom_plugins.CustomPattern"}
    payload["agents"][0]["tools"] = [
        {"id": "custom_tool", "impl": "tests.fixtures.custom_plugins.CustomTool"}
    ]
    config = load_config_dict(payload)
    plugins = load_agent_plugins(config.agents[0])

    assert type(plugins.memory).__name__ == "CustomMemory"
    assert type(plugins.pattern).__name__ == "CustomPattern"
    assert type(plugins.tools["custom_tool"]).__name__ == "CustomTool"


def test_load_agent_plugins_rejects_pattern_without_react_capability():
    payload = _base_payload()
    payload["agents"][0]["pattern"] = {
        "impl": "tests.fixtures.custom_plugins.BadPatternNoCapability"
    }
    config = load_config_dict(payload)

    with pytest.raises(CapabilityError, match="missing required capabilities"):
        load_agent_plugins(config.agents[0])


def test_load_agent_plugins_rejects_unknown_builtin_type():
    payload = _base_payload()
    payload["agents"][0]["memory"] = {"type": "unknown_memory"}
    config = load_config_dict(payload)

    with pytest.raises(PluginLoadError, match="Unknown builtin memory plugin type"):
        load_agent_plugins(config.agents[0])

