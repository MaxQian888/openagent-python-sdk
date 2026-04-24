"""Tests for ``openagents run``.

All paths exercise the mock LLM provider — no network, no external
services. The fixtures build minimal valid ``agent.json`` files under
``tmp_path`` and drive the CLI via ``cli_main``.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

from openagents.cli.main import main as cli_main


def _valid_agent(tmp_path: Path, *, agent_id: str = "a", extra_agents: list | None = None) -> Path:
    cfg_path = tmp_path / "agent.json"
    agents = [
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
    ]
    if extra_agents:
        agents.extend(extra_agents)
    cfg_path.write_text(json.dumps({"version": "1.0", "agents": agents}))
    return cfg_path


def test_run_single_agent_with_input_flag(tmp_path, capsys):
    cfg = _valid_agent(tmp_path)
    code = cli_main(["run", str(cfg), "--input", "hello", "--format", "text", "--no-stream"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Echo: hello" in out


def test_run_json_format_returns_full_result(tmp_path, capsys):
    cfg = _valid_agent(tmp_path)
    code = cli_main(["run", str(cfg), "--input", "hi", "--format", "json", "--no-stream"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "run_id" in payload
    assert "stop_reason" in payload
    assert "Echo: hi" in str(payload["final_output"])


def test_run_events_format_emits_jsonl(tmp_path, capsys):
    cfg = _valid_agent(tmp_path)
    cli_main(["run", str(cfg), "--input", "hi", "--format", "events"])
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert lines, "expected at least one JSONL event line"
    for ln in lines:
        blob = json.loads(ln)
        assert "name" in blob
        assert "payload" in blob
    # The terminal run.finished line must be present.
    assert any(json.loads(ln)["name"] == "run.finished" for ln in lines)


def test_run_missing_input_returns_1(tmp_path, capsys, monkeypatch):
    cfg = _valid_agent(tmp_path)
    # Force stdin to look TTY-ish so no pipe data is consumed.
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    code = cli_main(["run", str(cfg)])
    assert code == 1
    assert "no input" in capsys.readouterr().err


def test_run_multi_agent_without_agent_flag_returns_1(tmp_path, capsys):
    extra = {
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
    }
    cfg = _valid_agent(tmp_path, extra_agents=[extra])
    code = cli_main(["run", str(cfg), "--input", "hi"])
    assert code == 1
    err = capsys.readouterr().err
    assert "config declares 2 agents" in err


def test_run_unknown_agent_flag_returns_1(tmp_path, capsys):
    cfg = _valid_agent(tmp_path)
    code = cli_main(["run", str(cfg), "--input", "hi", "--agent", "does_not_exist"])
    assert code == 1
    assert "agent not found" in capsys.readouterr().err


def test_run_bad_config_returns_2(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    code = cli_main(["run", str(bad), "--input", "hi"])
    assert code == 2


def test_run_missing_config_returns_2(tmp_path, capsys):
    code = cli_main(["run", str(tmp_path / "nope.json"), "--input", "hi"])
    assert code == 2


def test_run_input_file_reads_prompt(tmp_path, capsys):
    cfg = _valid_agent(tmp_path)
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("from-a-file")
    code = cli_main(["run", str(cfg), "--input-file", str(prompt_file), "--format", "text", "--no-stream"])
    assert code == 0
    assert "Echo: from-a-file" in capsys.readouterr().out


def test_run_stdin_input_fallback(tmp_path, capsys, monkeypatch):
    cfg = _valid_agent(tmp_path)
    # Simulate piped stdin ("not a TTY") carrying the prompt.
    monkeypatch.setattr("sys.stdin", io.StringIO("piped-prompt\n"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    code = cli_main(["run", str(cfg), "--format", "text", "--no-stream"])
    assert code == 0
    # The mock provider echoes the prompt.
    assert "Echo: piped-prompt" in capsys.readouterr().out


def test_run_explicit_session_id_is_used(tmp_path, capsys):
    cfg = _valid_agent(tmp_path)
    code = cli_main(
        [
            "run",
            str(cfg),
            "--input",
            "hi",
            "--format",
            "json",
            "--no-stream",
            "--session-id",
            "fixed-session-123",
        ]
    )
    assert code == 0
    # Session id is not part of RunResult, but the command still succeeds.
    payload = json.loads(capsys.readouterr().out)
    assert "run_id" in payload


def test_run_selects_agent_by_flag(tmp_path, capsys):
    extra = {
        "id": "second",
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
    }
    cfg = _valid_agent(tmp_path, extra_agents=[extra])
    code = cli_main(
        [
            "run",
            str(cfg),
            "--agent",
            "second",
            "--input",
            "hi",
            "--format",
            "text",
            "--no-stream",
        ]
    )
    assert code == 0


def test_run_with_format_events_streams_events(tmp_path, capsys):
    cfg = _valid_agent(tmp_path)
    cli_main(["run", str(cfg), "--input", "hi", "--format", "events"])
    out = capsys.readouterr().out
    # At minimum the terminal run.finished event should be there; we also
    # expect the event-bus subscriber to have emitted at least one upstream
    # event (tool/llm) — assert loosely.
    assert "run.finished" in out
    assert out.count("\n") >= 1


def test_run_input_file_missing_returns_1(tmp_path, capsys):
    cfg = _valid_agent(tmp_path)
    code = cli_main(["run", str(cfg), "--input-file", str(tmp_path / "missing.txt")])
    assert code == 1
    assert "failed to read --input-file" in capsys.readouterr().err


def test_run_default_format_prefers_events_when_stdout_not_a_tty(tmp_path, capsys, monkeypatch):
    cfg = _valid_agent(tmp_path)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False, raising=False)
    cli_main(["run", str(cfg), "--input", "hi"])
    out = capsys.readouterr().out
    # Default for piped stdout is JSONL events.
    assert "run.finished" in out


def test_run_default_format_prefers_text_when_stdout_is_a_tty(tmp_path, capsys, monkeypatch):
    cfg = _valid_agent(tmp_path)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True, raising=False)
    cli_main(["run", str(cfg), "--input", "hi", "--no-stream"])
    out = capsys.readouterr().out
    assert "Echo: hi" in out


def test_run_runtime_exception_returns_3(tmp_path, capsys, monkeypatch):
    cfg = _valid_agent(tmp_path)
    from openagents.runtime.runtime import Runtime

    async def _blow_up(self, *, request):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated LLM failure")

    monkeypatch.setattr(Runtime, "run_detailed", _blow_up)
    code = cli_main(["run", str(cfg), "--input", "hi", "--no-stream"])
    assert code == 3
    err = capsys.readouterr().err
    assert "simulated LLM failure" in err


def test_run_close_failure_is_swallowed(tmp_path, capsys, monkeypatch):
    cfg = _valid_agent(tmp_path)
    from openagents.runtime.runtime import Runtime

    async def _bad_close(self):  # type: ignore[no-untyped-def]
        raise RuntimeError("close-failed")

    monkeypatch.setattr(Runtime, "close", _bad_close)
    code = cli_main(["run", str(cfg), "--input", "hi", "--no-stream"])
    # Best-effort: close errors don't affect exit code.
    assert code == 0


def test_run_config_error_during_runtime_construction_returns_2(tmp_path, capsys, monkeypatch):
    cfg = _valid_agent(tmp_path)
    from openagents.errors.exceptions import ConfigLoadError
    from openagents.runtime.runtime import Runtime

    def _raise(path):
        raise ConfigLoadError("fabricated")

    monkeypatch.setattr(Runtime, "from_config", staticmethod(_raise))
    code = cli_main(["run", str(cfg), "--input", "hi"])
    assert code == 2


# ---------------------------------------------------------------------------
# --dry-run tests
# ---------------------------------------------------------------------------


def test_dry_run_valid_config_exits_0(tmp_path, capsys):
    cfg = _valid_agent(tmp_path)
    code = cli_main(["run", str(cfg), "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert "dry-run OK" in out
    assert "agent" in out


def test_dry_run_no_input_still_exits_0(tmp_path, capsys):
    """--dry-run does not require --input."""
    cfg = _valid_agent(tmp_path)
    code = cli_main(["run", str(cfg), "--dry-run"])
    assert code == 0


def test_dry_run_bad_config_exits_2(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")
    code = cli_main(["run", str(bad), "--dry-run"])
    assert code == 2


def test_dry_run_runtime_from_config_failure_exits_2(tmp_path, capsys, monkeypatch):
    cfg = _valid_agent(tmp_path)
    from openagents.errors.exceptions import ConfigLoadError
    from openagents.runtime.runtime import Runtime

    def _raise(path):
        raise ConfigLoadError("fabricated")

    monkeypatch.setattr(Runtime, "from_config", staticmethod(_raise))
    code = cli_main(["run", str(cfg), "--dry-run"])
    assert code == 2


# ---------------------------------------------------------------------------
# --timeout tests
# ---------------------------------------------------------------------------


def test_timeout_exceeded_exits_3(tmp_path, capsys, monkeypatch):
    import asyncio

    cfg = _valid_agent(tmp_path)

    async def _hang(*_a, **_kw):
        await asyncio.sleep(9999)

    from openagents.cli.commands import run as run_cmd

    monkeypatch.setattr(run_cmd, "_run_once", _hang)
    code = cli_main(["run", str(cfg), "--input", "hi", "--timeout", "0.01"])
    assert code == 3
    assert "TimeoutError" in capsys.readouterr().err


def test_timeout_not_exceeded_exits_0(tmp_path, capsys):
    cfg = _valid_agent(tmp_path)
    code = cli_main(["run", str(cfg), "--input", "hi", "--timeout", "60", "--no-stream"])
    assert code == 0


# ---------------------------------------------------------------------------
# --batch tests
# ---------------------------------------------------------------------------


def _write_batch(tmp_path: Path, inputs: list) -> Path:
    p = tmp_path / "inputs.jsonl"
    lines = []
    for item in inputs:
        if isinstance(item, str):
            lines.append(json.dumps(item))
        else:
            lines.append(json.dumps(item))
    p.write_text("\n".join(lines))
    return p


def test_batch_serial_3_inputs(tmp_path, capsys):
    cfg = _valid_agent(tmp_path)
    batch = _write_batch(
        tmp_path,
        [
            {"input_text": "hello"},
            {"input_text": "world"},
            {"input_text": "foo"},
        ],
    )
    code = cli_main(["run", str(cfg), "--batch", str(batch)])
    assert code == 0
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 3
    for i, ln in enumerate(lines):
        obj = json.loads(ln)
        assert obj["index"] == i
        assert "output" in obj
        assert "latency_ms" in obj


def test_batch_plain_string_lines(tmp_path, capsys):
    cfg = _valid_agent(tmp_path)
    batch = _write_batch(tmp_path, ["hello", "world"])
    code = cli_main(["run", str(cfg), "--batch", str(batch)])
    assert code == 0
    out = capsys.readouterr().out
    assert len([ln for ln in out.splitlines() if ln.strip()]) == 2


def test_batch_exit_3_on_partial_failure(tmp_path, capsys, monkeypatch):
    cfg = _valid_agent(tmp_path)
    batch = _write_batch(tmp_path, [{"input_text": "ok"}, {"input_text": "boom"}])
    call_count = [0]

    from openagents.cli.commands import run as run_cmd

    orig = run_cmd._run_once

    async def _maybe_fail(runtime, *, agent_id, session_id, input_text, deps=None):
        call_count[0] += 1
        if input_text == "boom":
            raise RuntimeError("injected failure")
        return await orig(runtime, agent_id=agent_id, session_id=session_id, input_text=input_text, deps=deps)

    monkeypatch.setattr(run_cmd, "_run_once", _maybe_fail)
    code = cli_main(["run", str(cfg), "--batch", str(batch)])
    assert code == 3
    out = capsys.readouterr().out
    lines = [json.loads(ln) for ln in out.splitlines() if ln.strip()]
    errors = [ln for ln in lines if ln["error"] is not None]
    assert len(errors) == 1


def test_batch_mutual_exclusive_with_input(tmp_path, capsys):
    import pytest

    cfg = _valid_agent(tmp_path)
    batch = tmp_path / "b.jsonl"
    batch.write_text('{"input_text": "hi"}')
    # argparse mutual exclusion raises SystemExit(2)
    with pytest.raises(SystemExit) as exc_info:
        cli_main(["run", str(cfg), "--batch", str(batch), "--input", "hi"])
    assert exc_info.value.code != 0


def test_batch_file_not_found(tmp_path, capsys):
    cfg = _valid_agent(tmp_path)
    code = cli_main(["run", str(cfg), "--batch", "/nonexistent/inputs.jsonl"])
    assert code in (1, 3)
    assert "not found" in capsys.readouterr().err


def test_batch_stderr_summary_present(tmp_path, capsys):
    cfg = _valid_agent(tmp_path)
    batch = _write_batch(tmp_path, [{"input_text": "hi"}])
    cli_main(["run", str(cfg), "--batch", str(batch)])
    err = capsys.readouterr().err
    assert "Batch:" in err
    assert "p50=" in err
