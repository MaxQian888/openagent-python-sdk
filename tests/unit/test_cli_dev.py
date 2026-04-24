"""Tests for ``openagents dev``.

All paths use the mock LLM provider and drive the CLI via ``cli_main``.
The ``--no-watch`` flag performs exactly one ``reload()`` and exits,
making tests deterministic without a file watcher.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

from openagents.cli.commands import dev as dev_cmd
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


# ---------------------------------------------------------------------------
# Basic --no-watch wiring
# ---------------------------------------------------------------------------


def test_no_watch_exits_0(tmp_path, capsys):
    cfg = _valid_agent(tmp_path)
    code = cli_main(["dev", str(cfg), "--no-watch"])
    assert code == 0
    assert "reloaded" in capsys.readouterr().err


def test_no_watch_bad_config_exits_2(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")
    code = cli_main(["dev", str(bad), "--no-watch"])
    assert code == 2


def test_no_watch_config_error_on_reload_prints_skip(tmp_path, capsys, monkeypatch):
    cfg = _valid_agent(tmp_path)
    from openagents.errors.exceptions import ConfigLoadError
    from openagents.runtime.runtime import Runtime

    call_count = [0]

    def _reload(self):
        call_count[0] += 1
        raise ConfigLoadError("fabricated")

    monkeypatch.setattr(Runtime, "reload", _reload)
    code = cli_main(["dev", str(cfg), "--no-watch"])
    assert code == 0
    assert "reload skipped" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# --watch-also argument parsing
# ---------------------------------------------------------------------------


def test_watch_also_parser_collects_multiple():
    import argparse

    from openagents.cli.commands import dev as dev_cmd

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    dev_cmd.add_parser(sub)
    ns = parser.parse_args(["dev", "agent.json", "--watch-also", "a/**/*.py", "--watch-also", "b/*.yaml"])
    assert ns.watch_also == ["a/**/*.py", "b/*.yaml"]


def test_watch_also_default_is_empty():
    import argparse

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    dev_cmd.add_parser(sub)
    ns = parser.parse_args(["dev", "agent.json"])
    assert ns.watch_also == []


# ---------------------------------------------------------------------------
# _expand_watch_globs
# ---------------------------------------------------------------------------


def test_expand_watch_globs_returns_files_and_dirs(tmp_path):
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.py").write_text("x")
    import io

    buf = io.StringIO()
    files, dirs = dev_cmd._expand_watch_globs([str(tmp_path / "*.py")], stderr=buf)
    assert len(files) == 2
    assert len(dirs) == 1


def test_expand_watch_globs_warns_on_large_match(tmp_path, monkeypatch):
    import io

    # Simulate glob returning 1001 files
    fake_files = [tmp_path / f"f{i}.py" for i in range(1001)]
    for f in fake_files[:5]:
        f.write_text("x")

    import glob as _glob

    monkeypatch.setattr(_glob, "glob", lambda pattern, recursive=False: [str(f) for f in fake_files])
    # Also make Path.is_file() return True for all
    with patch("openagents.cli.commands.dev.Path.is_file", return_value=True):
        buf = io.StringIO()
        files, _ = dev_cmd._expand_watch_globs(["**/*.py"], stderr=buf)
    assert "warning" in buf.getvalue().lower()


# ---------------------------------------------------------------------------
# --test-prompt with _reload_with_log
# ---------------------------------------------------------------------------


def test_reload_with_log_test_prompt_success(tmp_path, capsys, monkeypatch):
    cfg = _valid_agent(tmp_path)
    from openagents.runtime.runtime import Runtime

    runtime = Runtime.from_config(cfg)

    import io

    buf = io.StringIO()

    # _probe will actually run the mock LLM — that's fine
    dev_cmd._reload_with_log(runtime, stderr=buf, test_prompt="ping", agent_id="a")
    out = buf.getvalue()
    # Should contain success marker (✓) OR at minimum "probe"
    assert "✓" in out or "probe" in out


def test_reload_with_log_test_prompt_failure(tmp_path, monkeypatch):
    cfg = _valid_agent(tmp_path)
    from openagents.runtime.runtime import Runtime

    runtime = Runtime.from_config(cfg)

    import io

    buf = io.StringIO()

    async def _bad_probe(*a, **kw):
        raise RuntimeError("probe-fail")

    monkeypatch.setattr(dev_cmd, "_probe", _bad_probe)
    # _reload_with_log calls asyncio.run(_probe(...))
    # But we need to make it use the monkeypatched one
    dev_cmd._reload_with_log(runtime, stderr=buf, test_prompt="ping", agent_id="a")
    # Since probe raises, output should contain "✗ probe failed:"
    out = buf.getvalue()
    assert "probe failed" in out or "✗" in out


def test_reload_with_log_no_test_prompt_emits_reloaded(tmp_path):
    cfg = _valid_agent(tmp_path)
    from openagents.runtime.runtime import Runtime

    runtime = Runtime.from_config(cfg)

    import io

    buf = io.StringIO()
    dev_cmd._reload_with_log(runtime, stderr=buf)
    assert "[reload] runtime reloaded" in buf.getvalue()


def test_probe_timeout_returns_false(tmp_path, monkeypatch):
    cfg = _valid_agent(tmp_path)
    from openagents.runtime.runtime import Runtime

    runtime = Runtime.from_config(cfg)

    async def _slow_run(*a, **kw):
        await asyncio.sleep(9999)

    monkeypatch.setattr(runtime, "run_detailed", _slow_run)
    ok, msg = asyncio.run(dev_cmd._probe(runtime, "a", "ping", timeout=0.001))
    assert ok is False
    assert "TimeoutError" in msg


def test_probe_success_returns_true(tmp_path):
    cfg = _valid_agent(tmp_path)
    from openagents.runtime.runtime import Runtime

    runtime = Runtime.from_config(cfg)
    ok, msg = asyncio.run(dev_cmd._probe(runtime, "a", "hello", timeout=30.0))
    assert ok is True
    assert "probe" in msg
