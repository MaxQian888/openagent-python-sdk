"""Tests for ``openagents chat``.

Drives the REPL headlessly by:

* Feeding prompts through a monkey-patched :func:`input`.
* Forcing ``require_or_hint`` to return ``None`` so ``questionary`` is
  bypassed (``input()`` path taken).
* Using the mock LLM provider for deterministic output.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openagents.cli.commands import chat as chat_cmd
from openagents.cli.main import main as cli_main


def _valid_agent(tmp_path: Path, *, agent_id: str = "a") -> Path:
    cfg_path = tmp_path / "agent.json"
    cfg_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "agents": [
                    {
                        "id": agent_id,
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
    return cfg_path


class _Inputs:
    """Drive the REPL with a scripted sequence of prompts."""

    def __init__(self, lines: list[str]):
        self._queue = list(lines)

    def __call__(self, _prompt: str = "") -> str:
        if not self._queue:
            raise EOFError
        return self._queue.pop(0)


@pytest.fixture
def no_questionary(monkeypatch):
    monkeypatch.setattr(chat_cmd, "require_or_hint", lambda name: None)


def test_chat_exit_cleanly(tmp_path, capsys, monkeypatch, no_questionary):
    cfg = _valid_agent(tmp_path)
    monkeypatch.setattr("builtins.input", _Inputs(["/exit"]))
    code = cli_main(["chat", str(cfg)])
    assert code == 0


def test_chat_single_turn_echoes_via_mock(tmp_path, capsys, monkeypatch, no_questionary):
    cfg = _valid_agent(tmp_path)
    monkeypatch.setattr("builtins.input", _Inputs(["hello", "/exit"]))
    code = cli_main(["chat", str(cfg)])
    assert code == 0
    out = capsys.readouterr().out
    assert "agent>" in out
    assert "Echo: hello" in out


def test_chat_reset_rotates_session_id(tmp_path, capsys, monkeypatch, no_questionary):
    cfg = _valid_agent(tmp_path)
    monkeypatch.setattr("builtins.input", _Inputs(["/reset", "/exit"]))
    code = cli_main(["chat", str(cfg), "--session-id", "fixed-id"])
    assert code == 0
    out = capsys.readouterr().out
    assert "session reset" in out


def test_chat_save_writes_valid_json(tmp_path, monkeypatch, no_questionary):
    cfg = _valid_agent(tmp_path)
    target = tmp_path / "session.json"
    monkeypatch.setattr(
        "builtins.input",
        _Inputs(["hi", f"/save {target}", "/exit"]),
    )
    cli_main(["chat", str(cfg)])
    assert target.exists()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["schema"] == 1
    assert data["session_id"]
    assert len(data["events"]) >= 1


def test_chat_save_without_path_prints_usage(tmp_path, capsys, monkeypatch, no_questionary):
    cfg = _valid_agent(tmp_path)
    monkeypatch.setattr("builtins.input", _Inputs(["/save", "/exit"]))
    code = cli_main(["chat", str(cfg)])
    assert code == 0
    out = capsys.readouterr().out
    assert "usage: /save" in out


def test_chat_context_without_prior_turn(tmp_path, capsys, monkeypatch, no_questionary):
    cfg = _valid_agent(tmp_path)
    monkeypatch.setattr("builtins.input", _Inputs(["/context", "/exit"]))
    cli_main(["chat", str(cfg)])
    out = capsys.readouterr().out
    assert "no previous turn" in out


def test_chat_context_after_turn_shows_final_output(tmp_path, capsys, monkeypatch, no_questionary):
    cfg = _valid_agent(tmp_path)
    monkeypatch.setattr("builtins.input", _Inputs(["hello world", "/context", "/exit"]))
    cli_main(["chat", str(cfg)])
    out = capsys.readouterr().out
    assert "final_output" in out
    assert "Echo: hello world" in out


def test_chat_tools_reports_empty_list(tmp_path, capsys, monkeypatch, no_questionary):
    cfg = _valid_agent(tmp_path)
    monkeypatch.setattr("builtins.input", _Inputs(["/tools", "/exit"]))
    cli_main(["chat", str(cfg)])
    out = capsys.readouterr().out
    # The minimal agent has no tools.
    assert "no tools" in out


def test_chat_eof_exits_cleanly(tmp_path, capsys, monkeypatch, no_questionary):
    cfg = _valid_agent(tmp_path)
    monkeypatch.setattr("builtins.input", _Inputs([]))
    code = cli_main(["chat", str(cfg)])
    assert code == 0


def test_chat_unknown_slash_lists_valid(tmp_path, capsys, monkeypatch, no_questionary):
    cfg = _valid_agent(tmp_path)
    monkeypatch.setattr("builtins.input", _Inputs(["/nope", "/exit"]))
    cli_main(["chat", str(cfg)])
    out = capsys.readouterr().out
    assert "unknown slash command" in out
    assert "/help" in out  # error message now references /help


def test_chat_bad_config_returns_2(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    code = cli_main(["chat", str(bad)])
    assert code == 2


def test_chat_multi_agent_without_flag_returns_1(tmp_path, capsys):
    cfg_path = tmp_path / "agent.json"
    cfg_path.write_text(
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
    code = cli_main(["chat", str(cfg_path)])
    assert code == 1
    assert "config declares 2 agents" in capsys.readouterr().err


def test_chat_empty_line_is_skipped(tmp_path, capsys, monkeypatch, no_questionary):
    cfg = _valid_agent(tmp_path)
    monkeypatch.setattr("builtins.input", _Inputs(["", "hi", "/exit"]))
    cli_main(["chat", str(cfg)])
    out = capsys.readouterr().out
    assert "Echo: hi" in out


def test_last_result_as_events_with_none():
    assert chat_cmd._last_result_as_events(None) == []


# ---------------------------------------------------------------------------
# /help, /history, --history tests
# ---------------------------------------------------------------------------


def test_help_slash_prints_commands(tmp_path, capsys, monkeypatch):
    cfg = _valid_agent(tmp_path)
    monkeypatch.setattr("builtins.input", _Inputs(["/help", "/exit"]))
    monkeypatch.setattr(chat_cmd, "require_or_hint", lambda _: None)
    code = cli_main(["chat", str(cfg)])
    assert code == 0
    out = capsys.readouterr().out
    assert "/exit" in out
    assert "/reset" in out
    assert "/history" in out
    assert "unknown slash command" not in out


def test_history_empty_before_any_turn(tmp_path, capsys, monkeypatch):
    cfg = _valid_agent(tmp_path)
    monkeypatch.setattr("builtins.input", _Inputs(["/history", "/exit"]))
    monkeypatch.setattr(chat_cmd, "require_or_hint", lambda _: None)
    cli_main(["chat", str(cfg)])
    out = capsys.readouterr().out
    assert "no turns" in out.lower()


def test_history_after_one_turn(tmp_path, capsys, monkeypatch):
    cfg = _valid_agent(tmp_path)
    monkeypatch.setattr("builtins.input", _Inputs(["hello", "/history", "/exit"]))
    monkeypatch.setattr(chat_cmd, "require_or_hint", lambda _: None)
    cli_main(["chat", str(cfg)])
    out = capsys.readouterr().out
    assert "turn 1" in out


def test_history_cleared_after_reset(tmp_path, capsys, monkeypatch):
    cfg = _valid_agent(tmp_path)
    monkeypatch.setattr("builtins.input", _Inputs(["hello", "/reset", "/history", "/exit"]))
    monkeypatch.setattr(chat_cmd, "require_or_hint", lambda _: None)
    cli_main(["chat", str(cfg)])
    out = capsys.readouterr().out
    # After reset, /history should show "no turns yet" (not turn 1)
    # Find text after "(session reset"
    reset_idx = out.find("session reset")
    post_reset = out[reset_idx:] if reset_idx >= 0 else out
    assert "no turns" in post_reset.lower()


def test_history_file_load_uses_session_id(tmp_path, capsys, monkeypatch):
    cfg = _valid_agent(tmp_path)
    history = tmp_path / "session.json"
    history.write_text(json.dumps({"schema": 1, "session_id": "myses-abc", "events": []}))
    monkeypatch.setattr("builtins.input", _Inputs(["/exit"]))
    monkeypatch.setattr(chat_cmd, "require_or_hint", lambda _: None)
    code = cli_main(["chat", str(cfg), "--history", str(history)])
    assert code == 0
    err = capsys.readouterr().err
    assert "myses-abc" in err


def test_history_file_not_found_exits_1(tmp_path, capsys):
    cfg = _valid_agent(tmp_path)
    code = cli_main(["chat", str(cfg), "--history", "/nonexistent/session.json"])
    assert code == 1
    assert "not found" in capsys.readouterr().err


def test_history_file_malformed_exits_1(tmp_path, capsys):
    cfg = _valid_agent(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")
    code = cli_main(["chat", str(cfg), "--history", str(bad)])
    assert code == 1


def test_history_file_missing_session_id_exits_1(tmp_path, capsys):
    cfg = _valid_agent(tmp_path)
    f = tmp_path / "nosid.json"
    f.write_text(json.dumps({"schema": 1, "events": []}))
    code = cli_main(["chat", str(cfg), "--history", str(f)])
    assert code == 1
    assert "session_id" in capsys.readouterr().err


def test_history_and_session_id_conflict_exits_1(tmp_path, capsys):
    cfg = _valid_agent(tmp_path)
    f = tmp_path / "h.json"
    f.write_text(json.dumps({"schema": 1, "session_id": "s", "events": []}))
    code = cli_main(["chat", str(cfg), "--history", str(f), "--session-id", "other"])
    assert code == 1
    assert "mutually exclusive" in capsys.readouterr().err
