"""``openagents dev`` — hot-reload wrapper around ``Runtime.reload()``.

Watches the config file for changes and calls
:meth:`openagents.runtime.runtime.Runtime.reload` on each burst of file
events. Uses :mod:`watchdog` when available; degrades cleanly to a
polling loop (``--poll-interval SECONDS``, default ``1.0``) otherwise.

Invariants preserved from ``CLAUDE.md``:

* ``Runtime.reload()`` re-parses config and invalidates LLM clients for
  changed agents, but does NOT hot-swap top-level ``runtime`` / ``session``
  / ``events`` plugins. ``dev`` therefore does not attempt to do so
  either — a change that would require top-level swap still needs a
  full process restart.

``--no-watch`` performs exactly one ``reload()`` and exits, which is the
mode tests use to exercise the debounce + reload wiring without a file
watcher.
"""

from __future__ import annotations

import argparse
import asyncio
import glob as _glob_module
import importlib.util
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any

from openagents.cli._exit import EXIT_OK, EXIT_VALIDATION
from openagents.cli._fallback import require_or_hint
from openagents.config.loader import load_config
from openagents.errors.exceptions import ConfigError
from openagents.interfaces.runtime import RunRequest
from openagents.runtime.runtime import Runtime

_DEBOUNCE_MS = 150
_WATCH_ALSO_WARN_THRESHOLD = 1000


async def _probe(
    runtime: Runtime,
    agent_id: str,
    test_prompt: str,
    *,
    timeout: float = 30.0,
) -> tuple[bool, str]:
    """Run a probe request against the runtime after reload.

    Returns ``(success, message)`` where message is suitable for the
    reload log line suffix.
    """
    t0 = time.monotonic()
    try:
        coro = runtime.run_detailed(
            request=RunRequest(
                agent_id=agent_id,
                session_id="dev-probe",
                input_text=test_prompt,
            )
        )
        result = await asyncio.wait_for(coro, timeout=timeout)
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        preview = str(result.final_output or "")[:60]
        return True, f"probe {elapsed_ms}ms: {preview}"
    except asyncio.TimeoutError:
        return False, f"TimeoutError: probe exceeded {timeout}s"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _reload_with_log(
    runtime: Runtime,
    *,
    stderr=None,
    test_prompt: str | None = None,
    agent_id: str | None = None,
) -> None:
    """Call ``Runtime.reload()`` and log success / failure to stderr.

    ``Runtime.reload`` is ``async`` on the real class but tests inject
    non-coroutine stubs; tolerate both. *stderr* is resolved at call time
    when omitted so that pytest's ``capsys`` (which rewraps
    ``sys.stderr`` per test) still sees the log line.

    If *test_prompt* is non-empty, runs a probe request after a successful
    reload and appends the result to the log line.
    """
    if stderr is None:
        stderr = sys.stderr
    try:
        result = runtime.reload()
        if asyncio.iscoroutine(result):
            asyncio.run(result)
    except ConfigError as exc:
        stderr.write(f"[reload skipped] {type(exc).__name__}: {exc}\n")
        return
    except Exception as exc:  # pragma: no cover - defensive
        stderr.write(f"[reload failed] {type(exc).__name__}: {exc}\n")
        return

    if test_prompt and agent_id:
        try:
            ok, msg = asyncio.run(_probe(runtime, agent_id, test_prompt))
        except Exception as exc:
            ok, msg = False, f"{type(exc).__name__}: {exc}"
        if ok:
            stderr.write(f"✓ reload OK | {msg}\n")
        else:
            stderr.write(f"✗ probe failed: {msg}\n")
    else:
        stderr.write("[reload] runtime reloaded\n")


def _debounced(
    runtime: Runtime,
    *,
    debounce_ms: int,
    stderr=None,
    test_prompt: str | None = None,
    agent_id: str | None = None,
) -> Any:
    """Return a function that collapses multiple fires within *debounce_ms*.

    Uses a single :class:`threading.Timer` whose deadline is reset on
    every call, so a burst of filesystem events (save/replace/truncate)
    results in exactly one :func:`_reload_with_log` call once the burst
    settles.
    """
    lock = threading.Lock()
    state: dict[str, Any] = {"timer": None}

    def _fire() -> None:
        _reload_with_log(runtime, stderr=stderr, test_prompt=test_prompt, agent_id=agent_id)

    def _schedule() -> None:
        with lock:
            existing = state["timer"]
            if existing is not None:
                existing.cancel()
            t = threading.Timer(debounce_ms / 1000.0, _fire)
            t.daemon = True
            state["timer"] = t
            t.start()

    return _schedule


def _expand_watch_globs(watch_globs: list[str], *, stderr=None) -> tuple[set[Path], set[Path]]:
    """Expand glob patterns into (all_files, unique_dirs).

    Emits a warning if the total file count exceeds the threshold.
    """
    if stderr is None:
        stderr = sys.stderr
    all_files: set[Path] = set()
    for pattern in watch_globs:
        matched = _glob_module.glob(pattern, recursive=True)
        for m in matched:
            p = Path(m)
            if p.is_file():
                all_files.add(p.resolve())
    if len(all_files) > _WATCH_ALSO_WARN_THRESHOLD:
        stderr.write(f"[watch] warning: --watch-also matches {len(all_files)} files; consider a narrower glob\n")
    unique_dirs: set[Path] = {f.parent for f in all_files}
    return all_files, unique_dirs


def _watch_with_watchdog(
    path: Path,
    runtime: Runtime,
    *,
    debounce_ms: int,
    watch_globs: list[str] | None = None,
    stderr=None,
    test_prompt: str | None = None,
    agent_id: str | None = None,
) -> None:
    if stderr is None:
        stderr = sys.stderr
    from watchdog.events import FileSystemEventHandler  # type: ignore
    from watchdog.observers import Observer  # type: ignore

    schedule = _debounced(
        runtime,
        debounce_ms=debounce_ms,
        stderr=stderr,
        test_prompt=test_prompt,
        agent_id=agent_id,
    )

    # Expand extra watch globs
    extra_files: set[Path] = set()
    extra_dirs: set[Path] = set()
    if watch_globs:
        extra_files, extra_dirs = _expand_watch_globs(watch_globs, stderr=stderr)

    resolved_config = path.resolve()

    class _Handler(FileSystemEventHandler):
        def on_any_event(self, event):  # noqa: D401 - watchdog callback
            src = Path(getattr(event, "src_path", "") or "")
            src_resolved = src.resolve()
            if src_resolved == resolved_config:
                schedule()
                return
            if src_resolved in extra_files:
                stderr.write(f"[watch] change: {src}\n")
                schedule()

    observer = Observer()
    observer.schedule(_Handler(), str(path.parent), recursive=False)
    for d in extra_dirs:
        try:
            observer.schedule(_Handler(), str(d), recursive=True)
        except Exception:  # pragma: no cover - directory may not exist
            pass

    observer.start()
    stderr.write(f"[watch] watching {path} (press Ctrl+C to exit)\n")
    stop_event = threading.Event()

    def _sigint(_sig, _frame) -> None:
        stop_event.set()

    try:
        signal.signal(signal.SIGINT, _sigint)
    except ValueError:  # pragma: no cover - not on main thread
        pass
    try:
        while not stop_event.is_set():
            time.sleep(0.1)
    finally:
        observer.stop()
        observer.join(timeout=2.0)


def _watch_polling(
    path: Path,
    runtime: Runtime,
    *,
    poll_interval: float,
    watch_globs: list[str] | None = None,
    stderr=None,
    test_prompt: str | None = None,
    agent_id: str | None = None,
) -> None:
    if stderr is None:
        stderr = sys.stderr
    stderr.write(f"[watch] watchdog not installed; polling {path} every {poll_interval}s (Ctrl+C to exit)\n")

    # Build initial mtime map: config file + extra glob files
    mtime_map: dict[Path, float | None] = {}
    try:
        mtime_map[path] = path.stat().st_mtime
    except OSError:
        mtime_map[path] = None

    if watch_globs:
        extra_files, _ = _expand_watch_globs(watch_globs, stderr=stderr)
        for f in extra_files:
            try:
                mtime_map[f] = f.stat().st_mtime
            except OSError:
                mtime_map[f] = None

    try:
        while True:
            time.sleep(poll_interval)
            for watched_path, last_mtime in list(mtime_map.items()):
                try:
                    mtime = watched_path.stat().st_mtime
                except OSError:
                    continue
                if last_mtime is None or mtime != last_mtime:
                    mtime_map[watched_path] = mtime
                    if watched_path != path:
                        stderr.write(f"[watch] change: {watched_path}\n")
                    _reload_with_log(runtime, stderr=stderr, test_prompt=test_prompt, agent_id=agent_id)
                    break  # one reload per poll tick is enough
    except KeyboardInterrupt:
        return


def add_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "dev",
        help="hot-reload runtime on config change",
        description="Watch a config file and call Runtime.reload() on each change.",
    )
    p.add_argument("path", help="path to an agent.json")
    p.add_argument(
        "--poll-interval",
        dest="poll_interval",
        type=float,
        default=1.0,
        help="polling interval in seconds when watchdog isn't available (default: 1.0)",
    )
    p.add_argument(
        "--no-watch",
        action="store_true",
        help="call Runtime.reload() once and exit (for tests / one-shot smoke)",
    )
    p.add_argument(
        "--watch-also",
        dest="watch_also",
        action="append",
        default=[],
        metavar="GLOB",
        help="additional glob pattern to watch (repeatable, e.g. 'plugins/**/*.py')",
    )
    p.add_argument(
        "--test-prompt",
        dest="test_prompt",
        default=None,
        metavar="TEXT",
        help="after each reload, run a probe request with this text and report success/failure",
    )
    p.set_defaults(func=run)
    return p


def run(args: argparse.Namespace) -> int:
    path = Path(args.path)
    try:
        cfg = load_config(path)
    except ConfigError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_VALIDATION

    try:
        runtime = Runtime.from_config(path)
    except ConfigError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_VALIDATION

    # Resolve agent_id for probe
    test_prompt: str | None = getattr(args, "test_prompt", None)
    probe_agent_id: str | None = None
    if test_prompt:
        agents = getattr(cfg, "agents", [])
        probe_agent_id = agents[0].id if len(agents) == 1 else getattr(args, "agent_id", None)

    watch_globs: list[str] = getattr(args, "watch_also", []) or []

    try:
        if args.no_watch:
            _reload_with_log(runtime, test_prompt=test_prompt, agent_id=probe_agent_id)
            return EXIT_OK

        watchdog = importlib.util.find_spec("watchdog")
        if watchdog is not None and require_or_hint("watchdog") is not None:
            _watch_with_watchdog(
                path,
                runtime,
                debounce_ms=_DEBOUNCE_MS,
                watch_globs=watch_globs,
                test_prompt=test_prompt,
                agent_id=probe_agent_id,
            )
        else:
            _watch_polling(
                path,
                runtime,
                poll_interval=args.poll_interval,
                watch_globs=watch_globs,
                test_prompt=test_prompt,
                agent_id=probe_agent_id,
            )
        return EXIT_OK
    finally:
        try:
            asyncio.run(runtime.close())
        except Exception:  # pragma: no cover - best-effort cleanup
            pass
