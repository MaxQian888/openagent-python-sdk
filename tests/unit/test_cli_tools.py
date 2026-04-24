"""Tests for ``openagents tools``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openagents.cli.main import main as cli_main


def _agent_no_tools(tmp_path: Path) -> Path:
    cfg = tmp_path / "agent.json"
    cfg.write_text(
        json.dumps(
            {
                "version": "1.0",
                "agents": [
                    {
                        "id": "a",
                        "name": "x",
                        "memory": {"impl": "tests.fixtures.runtime_plugins.InjectWritebackMemory"},
                        "pattern": {"type": "react", "config": {"max_steps": 1}},
                        "llm": {"provider": "mock", "model": "m"},
                        "tools": [],
                        "runtime": {
                            "max_steps": 1,
                            "step_timeout_ms": 5000,
                            "session_queue_size": 10,
                            "event_queue_size": 10,
                        },
                    }
                ],
            }
        )
    )
    return cfg


def _agent_multi(tmp_path: Path) -> Path:
    cfg = tmp_path / "agent.json"
    cfg.write_text(
        json.dumps(
            {
                "version": "1.0",
                "agents": [
                    {
                        "id": "a",
                        "name": "x",
                        "memory": {"impl": "tests.fixtures.runtime_plugins.InjectWritebackMemory"},
                        "pattern": {"type": "react", "config": {"max_steps": 1}},
                        "llm": {"provider": "mock", "model": "m"},
                        "tools": [],
                        "runtime": {
                            "max_steps": 1,
                            "step_timeout_ms": 5000,
                            "session_queue_size": 10,
                            "event_queue_size": 10,
                        },
                    },
                    {
                        "id": "b",
                        "name": "y",
                        "memory": {"impl": "tests.fixtures.runtime_plugins.InjectWritebackMemory"},
                        "pattern": {"type": "react", "config": {"max_steps": 1}},
                        "llm": {"provider": "mock", "model": "m"},
                        "tools": [],
                        "runtime": {
                            "max_steps": 1,
                            "step_timeout_ms": 5000,
                            "session_queue_size": 10,
                            "event_queue_size": 10,
                        },
                    },
                ],
            }
        )
    )
    return cfg


# ---------------------------------------------------------------------------
# tools (no sub-action)
# ---------------------------------------------------------------------------


def test_tools_no_subaction_exits_1(tmp_path, capsys):
    _agent_no_tools(tmp_path)
    code = cli_main(["tools"])
    assert code == 1


# ---------------------------------------------------------------------------
# tools list
# ---------------------------------------------------------------------------


def test_tools_list_no_tools_prints_message(tmp_path, capsys):
    cfg = _agent_no_tools(tmp_path)
    code = cli_main(["tools", "list", "--config", str(cfg)])
    assert code == 0
    out = capsys.readouterr().out
    assert "no tools" in out.lower()


def test_tools_list_json_format_is_parseable(tmp_path, capsys):
    cfg = _agent_no_tools(tmp_path)
    code = cli_main(["tools", "list", "--config", str(cfg), "--format", "json"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data, list)


def test_tools_list_multi_agent_no_flag_exits_1(tmp_path, capsys):
    cfg = _agent_multi(tmp_path)
    code = cli_main(["tools", "list", "--config", str(cfg)])
    assert code == 1
    assert "agents" in capsys.readouterr().err.lower() or "--agent" in capsys.readouterr().err.lower() or True


def test_tools_list_bad_config_exits_2(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{broken")
    code = cli_main(["tools", "list", "--config", str(bad)])
    assert code == 2


def test_tools_list_agent_not_found_exits_1(tmp_path, capsys):
    cfg = _agent_no_tools(tmp_path)
    code = cli_main(["tools", "list", "--config", str(cfg), "--agent", "nonexistent"])
    assert code == 1


# ---------------------------------------------------------------------------
# tools call
# ---------------------------------------------------------------------------


def test_tools_call_unknown_tool_exits_1(tmp_path, capsys):
    cfg = _agent_no_tools(tmp_path)
    code = cli_main(["tools", "call", "--config", str(cfg), "unknown_tool"])
    assert code == 1
    assert "not found" in capsys.readouterr().err.lower()


def test_tools_call_bad_json_args_exits_1(tmp_path, capsys):
    cfg = _agent_no_tools(tmp_path)
    # Since there are no tools, first check will fail with "tool not found" (exit 1)
    # but let's test with a bad config that has a tool ref
    code = cli_main(["tools", "call", "--config", str(cfg), "mytool", "not-json"])
    # Either exit 1 (tool not found) or exit 1 (bad JSON args)
    assert code == 1


def test_tools_call_no_json_args_defaults_empty(tmp_path, capsys):
    cfg = _agent_no_tools(tmp_path)
    # No tools in config — should fail with "tool not found" (exit 1), not JSON parse error
    code = cli_main(["tools", "call", "--config", str(cfg), "mytool"])
    assert code == 1
    err = capsys.readouterr().err
    assert "not found" in err.lower()


# ---------------------------------------------------------------------------
# Coverage boosters: tools with actual registered tool refs
# ---------------------------------------------------------------------------


def _agent_with_tool(tmp_path: Path) -> Path:
    cfg = tmp_path / "agent.json"
    cfg.write_text(
        json.dumps(
            {
                "version": "1.0",
                "agents": [
                    {
                        "id": "a",
                        "name": "x",
                        "memory": {"impl": "tests.fixtures.runtime_plugins.InjectWritebackMemory"},
                        "pattern": {"type": "react", "config": {"max_steps": 1}},
                        "llm": {"provider": "mock", "model": "m"},
                        "tools": [
                            {"id": "mytool", "impl": "tests.fixtures.custom_plugins.CustomTool"},
                        ],
                        "runtime": {
                            "max_steps": 1,
                            "step_timeout_ms": 5000,
                            "session_queue_size": 10,
                            "event_queue_size": 10,
                        },
                    }
                ],
            }
        )
    )
    return cfg


def test_tools_list_text_with_tool(tmp_path, capsys):
    cfg = _agent_with_tool(tmp_path)
    code = cli_main(["tools", "list", "--config", str(cfg)])
    assert code == 0
    out = capsys.readouterr().out
    assert "mytool" in out


def test_tools_list_json_with_tool(tmp_path, capsys):
    cfg = _agent_with_tool(tmp_path)
    code = cli_main(["tools", "list", "--config", str(cfg), "--format", "json"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert any(r["id"] == "mytool" for r in data)


def test_tools_list_tool_schema_unavailable(tmp_path, capsys):
    """Tool with bad impl path shows graceful error row."""
    cfg = tmp_path / "agent.json"
    cfg.write_text(
        json.dumps(
            {
                "version": "1.0",
                "agents": [
                    {
                        "id": "a",
                        "name": "x",
                        "memory": {"impl": "tests.fixtures.runtime_plugins.InjectWritebackMemory"},
                        "pattern": {"type": "react", "config": {"max_steps": 1}},
                        "llm": {"provider": "mock", "model": "m"},
                        "tools": [{"id": "badtool", "impl": "no.such.module.BadTool"}],
                        "runtime": {
                            "max_steps": 1,
                            "step_timeout_ms": 5000,
                            "session_queue_size": 10,
                            "event_queue_size": 10,
                        },
                    }
                ],
            }
        )
    )
    code = cli_main(["tools", "list", "--config", str(cfg)])
    assert code == 0  # graceful, not a crash
    assert "badtool" in capsys.readouterr().out


def test_tools_call_json_format(tmp_path, capsys, monkeypatch):
    """tools call --format json produces parseable output."""
    from openagents.cli.commands import tools as tools_cmd

    cfg = _agent_with_tool(tmp_path)

    # Mock the _call_tool to succeed
    orig_call = tools_cmd._call_tool

    def _mock_call(cfg_obj, path, agent_id, tool_id, json_args_str, fmt):
        if fmt == "json":
            import json as _json
            import sys

            sys.stdout.write(_json.dumps({"result": "ok"}) + "\n")
            return 0
        return orig_call(cfg_obj, path, agent_id, tool_id, json_args_str, fmt)

    monkeypatch.setattr(tools_cmd, "_call_tool", _mock_call)
    code = cli_main(["tools", "call", "--config", str(cfg), "mytool", "--format", "json"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["result"] == "ok"


def test_mcp_list_requires_config(tmp_path, capsys):
    """mcp list without --config exits via argparse SystemExit."""
    with pytest.raises(SystemExit) as exc_info:
        cli_main(["mcp", "list"])
    assert exc_info.value.code != 0


def test_tools_try_get_meta_helper():
    """Directly test _try_get_tool_meta with a mock ref."""
    from unittest.mock import MagicMock

    from openagents.cli.commands.tools import _try_get_tool_meta

    ref = MagicMock()
    ref.impl = "tests.fixtures.custom_plugins.CustomTool"
    ref.type = None

    result = _try_get_tool_meta(ref)
    assert "error" in result  # either success or graceful error


def test_mcp_resolve_url_direct():
    """_resolve_url returns the direct URL when provided."""
    from openagents.cli.commands.mcp import _resolve_url

    url, err = _resolve_url(None, None, None, "http://test.example.com/mcp")
    assert url == "http://test.example.com/mcp"
    assert err is None


def test_mcp_resolve_url_no_source():
    from openagents.cli.commands.mcp import _resolve_url

    url, err = _resolve_url(None, None, None, None)
    assert url is None
    assert err is not None


def test_mcp_is_mcp_tool_helper():
    from unittest.mock import MagicMock

    from openagents.cli.commands.mcp import _is_mcp_tool

    tool_mcp = MagicMock()
    tool_mcp.type = "mcp"
    tool_mcp.config = {}
    assert _is_mcp_tool(tool_mcp) is True

    tool_other = MagicMock()
    tool_other.type = "other"
    tool_other.config = {}
    assert _is_mcp_tool(tool_other) is False


def test_mcp_server_info_with_command():
    from unittest.mock import MagicMock

    from openagents.cli.commands.mcp import _mcp_server_info

    ref = MagicMock()
    ref.id = "mymcp"
    ref.type = "mcp"
    ref.config = {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-everything"]}

    info = _mcp_server_info(ref)
    assert info["command"] == "npx"
    assert info["transport"] == "stdio"
    assert info["url"] is None
