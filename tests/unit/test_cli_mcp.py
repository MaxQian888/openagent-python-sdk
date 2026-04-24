"""Tests for ``openagents mcp``.

All network calls are mocked — no real MCP server required.
"""

from __future__ import annotations

import json
from pathlib import Path

from openagents.cli.commands import mcp as mcp_cmd
from openagents.cli.main import main as cli_main


def _agent_no_mcp(tmp_path: Path) -> Path:
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


def _agent_with_mcp(tmp_path: Path, url: str = "http://localhost:3000/mcp") -> Path:
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
                        "tools": [{"id": "my-mcp", "type": "mcp", "config": {"url": url}}],
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


# ---------------------------------------------------------------------------
# mcp (no sub-action)
# ---------------------------------------------------------------------------


def test_mcp_no_subaction_exits_1(capsys):
    code = cli_main(["mcp"])
    assert code == 1


# ---------------------------------------------------------------------------
# mcp list
# ---------------------------------------------------------------------------


def test_mcp_list_no_servers(tmp_path, capsys):
    cfg = _agent_no_mcp(tmp_path)
    code = cli_main(["mcp", "list", "--config", str(cfg)])
    assert code == 0
    out = capsys.readouterr().out
    assert "no mcp" in out.lower()


def test_mcp_list_shows_server(tmp_path, capsys):
    cfg = _agent_with_mcp(tmp_path)
    code = cli_main(["mcp", "list", "--config", str(cfg)])
    assert code == 0
    out = capsys.readouterr().out
    assert "my-mcp" in out or "localhost" in out


def test_mcp_list_json_format(tmp_path, capsys):
    cfg = _agent_with_mcp(tmp_path)
    code = cli_main(["mcp", "list", "--config", str(cfg), "--format", "json"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data, list)
    assert len(data) == 1


def test_mcp_list_bad_config_exits_2(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{broken")
    code = cli_main(["mcp", "list", "--config", str(bad)])
    assert code == 2


# ---------------------------------------------------------------------------
# mcp ping (mocked)
# ---------------------------------------------------------------------------


def test_mcp_ping_success(tmp_path, capsys, monkeypatch):
    async def _fake_connect(url, timeout):
        return [{"name": "tool1"}, {"name": "tool2"}, {"name": "tool3"}]

    monkeypatch.setattr(mcp_cmd, "_mcp_connect_list_tools", _fake_connect)
    monkeypatch.setattr(mcp_cmd, "require_or_hint", lambda _: object())  # truthy

    code = cli_main(["mcp", "ping", "http://localhost:3000/mcp"])
    assert code == 0
    out = capsys.readouterr().out
    assert "✓" in out
    assert "tools=3" in out


def test_mcp_ping_connection_error_exits_3(tmp_path, capsys, monkeypatch):
    async def _fail(url, timeout):
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(mcp_cmd, "_mcp_connect_list_tools", _fail)
    monkeypatch.setattr(mcp_cmd, "require_or_hint", lambda _: object())

    code = cli_main(["mcp", "ping", "http://localhost:9999/mcp"])
    assert code == 3
    out = capsys.readouterr().out
    assert "✗" in out


def test_mcp_ping_timeout_exits_3(tmp_path, capsys, monkeypatch):
    import asyncio

    async def _slow(url, timeout):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(mcp_cmd, "_mcp_connect_list_tools", _slow)
    monkeypatch.setattr(mcp_cmd, "require_or_hint", lambda _: object())

    code = cli_main(["mcp", "ping", "http://localhost:3000/mcp"])
    assert code == 3
    assert "✗" in capsys.readouterr().out


def test_mcp_ping_extra_missing_exits_1(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(mcp_cmd, "require_or_hint", lambda _: None)
    code = cli_main(["mcp", "ping", "http://localhost:3000/mcp"])
    assert code == 1


def test_mcp_ping_url_from_config(tmp_path, capsys, monkeypatch):
    cfg = _agent_with_mcp(tmp_path, url="http://mcp-from-config/mcp")
    captured_url = []

    async def _fake(url, timeout):
        captured_url.append(url)
        return []

    monkeypatch.setattr(mcp_cmd, "_mcp_connect_list_tools", _fake)
    monkeypatch.setattr(mcp_cmd, "require_or_hint", lambda _: object())

    code = cli_main(["mcp", "ping", "--config", str(cfg)])
    assert code == 0
    assert captured_url == ["http://mcp-from-config/mcp"]


# ---------------------------------------------------------------------------
# mcp tools (mocked)
# ---------------------------------------------------------------------------


def test_mcp_tools_success_text(tmp_path, capsys, monkeypatch):
    async def _fake(url, timeout):
        return [
            {"name": "search", "description": "search the web", "inputSchema": {"properties": {"q": {}}}},
        ]

    monkeypatch.setattr(mcp_cmd, "_mcp_connect_list_tools", _fake)
    monkeypatch.setattr(mcp_cmd, "require_or_hint", lambda _: object())

    code = cli_main(["mcp", "tools", "http://localhost:3000/mcp"])
    assert code == 0
    out = capsys.readouterr().out
    assert "search" in out


def test_mcp_tools_json_parseable(tmp_path, capsys, monkeypatch):
    async def _fake(url, timeout):
        return [{"name": "t1", "description": "d", "inputSchema": {}}]

    monkeypatch.setattr(mcp_cmd, "_mcp_connect_list_tools", _fake)
    monkeypatch.setattr(mcp_cmd, "require_or_hint", lambda _: object())

    code = cli_main(["mcp", "tools", "http://localhost/mcp", "--format", "json"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data, list)


def test_mcp_tools_empty_server(tmp_path, capsys, monkeypatch):
    async def _fake(url, timeout):
        return []

    monkeypatch.setattr(mcp_cmd, "_mcp_connect_list_tools", _fake)
    monkeypatch.setattr(mcp_cmd, "require_or_hint", lambda _: object())

    code = cli_main(["mcp", "tools", "http://localhost/mcp"])
    assert code == 0
    out = capsys.readouterr().out
    assert "no tools" in out.lower()


def test_mcp_tools_connection_error_exits_3(tmp_path, capsys, monkeypatch):
    async def _fail(url, timeout):
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(mcp_cmd, "_mcp_connect_list_tools", _fail)
    monkeypatch.setattr(mcp_cmd, "require_or_hint", lambda _: object())

    code = cli_main(["mcp", "tools", "http://localhost:9999/mcp"])
    assert code == 3
