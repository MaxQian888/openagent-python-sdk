"""``openagents run`` — execute an agent against a single prompt.

Input resolution order: ``--input TEXT`` > ``--input-file PATH`` >
non-TTY stdin > error. The command constructs a :class:`Runtime` via
:meth:`Runtime.from_config`, builds a :class:`RunRequest`, and drives
:meth:`Runtime.run_detailed`.

Output format:

* ``text`` (default when stdout is a TTY) — Rich-friendly transcript
  rendered via :class:`openagents.cli._events.EventFormatter`, with the
  final output printed on its own line.
* ``json`` — ``RunResult.model_dump(mode='json')``.
* ``events`` — one JSON line per event using
  :func:`openagents.cli._events.event_to_jsonl_dict` + a terminal
  ``run.finished`` event carrying the final output.

When stdout is not a TTY and ``--format`` wasn't passed explicitly, the
command defaults to ``events`` (JSONL) for pipe-friendliness.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from openagents.cli._events import (
    EventFormatter,
    event_to_jsonl_dict,
)
from openagents.cli._exit import (
    EXIT_OK,
    EXIT_RUNTIME,
    EXIT_USAGE,
    EXIT_VALIDATION,
)
from openagents.cli._rich import get_console
from openagents.config.loader import load_config
from openagents.errors.exceptions import ConfigError
from openagents.interfaces.runtime import RunRequest
from openagents.runtime.runtime import Runtime


def _resolve_input(args: argparse.Namespace) -> str | None:
    """Return the user's prompt, or ``None`` if nothing is available."""
    if args.input:
        return args.input
    if args.input_file:
        try:
            return Path(args.input_file).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"failed to read --input-file: {exc}", file=sys.stderr)
            return None
    if not sys.stdin.isatty():
        data = sys.stdin.read()
        if data:
            return data
    return None


def _select_agent(cfg, requested: str | None) -> tuple[str | None, str | None]:
    """Return ``(agent_id, error_message)``."""
    if requested:
        for agent in cfg.agents:
            if agent.id == requested:
                return agent.id, None
        return None, f"agent not found: {requested}. Available: {[a.id for a in cfg.agents]}"
    if len(cfg.agents) == 1:
        return cfg.agents[0].id, None
    return None, (f"config declares {len(cfg.agents)} agents; pass --agent with one of: {[a.id for a in cfg.agents]}")


def _default_format(explicit: str | None) -> str:
    if explicit:
        return explicit
    return "text" if sys.stdout.isatty() else "events"


class _JsonlSubscriber:
    """Bridge that turns every event into a JSONL line on stdout."""

    def __init__(self) -> None:
        self._stream = sys.stdout

    def handle(self, event: Any) -> None:
        name = getattr(event, "name", None)
        payload = getattr(event, "payload", None) or {}
        if not isinstance(payload, dict):
            try:
                payload = dict(payload)
            except Exception:
                payload = {"raw": repr(payload)}
        self._stream.write(json.dumps(event_to_jsonl_dict(str(name), payload)) + "\n")
        self._stream.flush()


class _TextSubscriber:
    """Bridge that renders events via the shared EventFormatter."""

    def __init__(self) -> None:
        self._formatter = EventFormatter(get_console("stderr"), show_details=True)

    def handle(self, event: Any) -> None:
        name = getattr(event, "name", None)
        payload = getattr(event, "payload", None) or {}
        if not isinstance(payload, dict):
            payload = {"raw": repr(payload)}
        self._formatter.render(str(name), payload)


def _has_rich_console_bus(runtime: Runtime) -> bool:
    """Return True if the runtime event bus is (or wraps) a RichConsoleEventBus."""
    try:
        from openagents.plugins.builtin.events.rich_console import RichConsoleEventBus

        bus = getattr(runtime, "event_bus", None) or getattr(runtime, "events", None)
        return isinstance(bus, RichConsoleEventBus)
    except Exception:
        return False


def _attach_subscriber(runtime: Runtime, handler: Any) -> None:
    """Subscribe *handler* to every interesting event on ``runtime.events``."""
    bus = getattr(runtime, "events", None)
    if bus is None:
        return
    for name in (
        "run.started",
        "run.finished",
        "tool.called",
        "tool.succeeded",
        "tool.failed",
        "llm.called",
        "llm.succeeded",
    ):
        try:
            bus.subscribe(name, handler)
        except Exception:  # pragma: no cover - defensive: subscribe shape varies
            pass


def _load_dotenv(directory: Path) -> None:
    """Load a .env file from *directory* into os.environ (existing vars win)."""
    env_file = directory / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _load_deps(dotted_path: str) -> Any:
    """Import and call a no-arg factory function given as a dotted Python path.

    Example: ``examples.multi_agent_support.app.deps.build_seeded_deps``
    """
    parts = dotted_path.rsplit(".", 1)
    if len(parts) != 2:
        raise ImportError(f"--deps must be a dotted path to a callable, got: {dotted_path!r}")
    module_path, attr = parts
    import importlib

    module = importlib.import_module(module_path)
    factory = getattr(module, attr, None)
    if factory is None:
        raise ImportError(f"no attribute {attr!r} in module {module_path!r}")
    if not callable(factory):
        raise ImportError(f"{dotted_path!r} is not callable")
    return factory()


async def _run_once(
    runtime: Runtime,
    *,
    agent_id: str,
    session_id: str,
    input_text: str,
    deps: Any = None,
) -> Any:
    return await runtime.run_detailed(
        request=RunRequest(
            agent_id=agent_id,
            session_id=session_id,
            input_text=input_text,
            deps=deps,
        )
    )


def _emit_final_output(result: Any, fmt: str) -> None:
    if fmt == "json":
        sys.stdout.write(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n")
        return
    if fmt == "events":
        sys.stdout.write(
            json.dumps(
                event_to_jsonl_dict(
                    "run.finished",
                    {
                        "run_id": result.run_id,
                        "stop_reason": str(result.stop_reason),
                        "final_output": str(result.final_output) if result.final_output is not None else None,
                        "error": result.error_details.message if result.error_details is not None else None,
                    },
                )
            )
            + "\n"
        )
        return
    # text — render with rich when available
    console = get_console("stdout")
    stop = result.stop_reason.value if hasattr(result.stop_reason, "value") else str(result.stop_reason)
    err = result.error_details
    try:
        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        from openagents.observability._rich import _render_value

        stop_style = "bold green" if stop == "completed" else "bold red"

        # Header row: stop_reason (and optional error)
        header = Table.grid(padding=(0, 2))
        header.add_row(Text("stop_reason", style="dim"), Text(stop, style=stop_style))
        if err is not None:
            header.add_row(Text("error", style="dim"), Text(str(err.message), style="red"))
        console.print(Panel(header, title="[bold]run.finished[/]", border_style="dim"))

        # Output block: try JSON parse → _render_value, otherwise Markdown
        if result.final_output is not None:
            raw = str(result.final_output)
            output_renderable: Any
            try:
                import json as _json

                parsed = _json.loads(raw)
                output_renderable = _render_value(parsed)
            except Exception:
                output_renderable = Markdown(raw)
            console.print(Panel(output_renderable, title="[bold]output[/]", border_style="green"))
    except Exception:
        if result.final_output is not None:
            console.print(str(result.final_output))


def add_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "run",
        help="execute an agent against a single prompt",
        description="Run an agent.json once and print the transcript / final output.",
    )
    p.add_argument("path", help="path to an agent.json")

    # Input group: --batch is mutually exclusive with --input / --input-file
    input_group = p.add_mutually_exclusive_group()
    input_group.add_argument("--input", help="prompt text (takes precedence over --input-file / stdin)")
    input_group.add_argument(
        "--batch",
        dest="batch_file",
        metavar="JSONL",
        help="path to a JSONL file with multiple inputs for batch execution",
    )

    p.add_argument("--input-file", dest="input_file", help="path to a file containing the prompt")
    p.add_argument("--agent", dest="agent_id", help="agent id to run (required for multi-agent configs)")
    p.add_argument(
        "--concurrency",
        dest="concurrency",
        type=int,
        default=1,
        metavar="N",
        help="max concurrent runs in --batch mode (default: 1, serial)",
    )
    p.add_argument(
        "--timeout",
        dest="timeout",
        type=float,
        default=None,
        metavar="SECONDS",
        help="wall-clock timeout per run in seconds (exit 3 on timeout)",
    )
    p.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="validate config and instantiate plugins without calling the LLM (exit 0 = ready to run)",
    )
    p.add_argument(
        "--deps",
        dest="deps_factory",
        default=None,
        metavar="DOTTED_PATH",
        help="dotted path to a no-arg factory that returns the deps object (e.g. myapp.deps.build)",
    )
    p.add_argument(
        "--save-image",
        dest="save_image",
        default=None,
        metavar="PATH",
        help="export the run log as an image (.svg built-in; .png/.jpg requires io-openagent-sdk[screenshot])",
    )
    p.add_argument("--format", choices=["text", "json", "events"], default=None)
    p.add_argument("--no-stream", action="store_true", help="buffer events; print only the final output")
    p.add_argument(
        "--session-id",
        dest="session_id",
        default=None,
        help="reuse an explicit session id (default: auto-generated UUID)",
    )
    p.set_defaults(func=run)
    return p


def run(args: argparse.Namespace) -> int:
    # --dry-run: validate config + plugin instantiation, no LLM call
    if getattr(args, "dry_run", False):
        return _run_dry_run(args)

    _load_dotenv(Path(args.path).resolve().parent)

    try:
        cfg = load_config(args.path)
    except ConfigError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_VALIDATION

    agent_id, agent_err = _select_agent(cfg, args.agent_id)
    if agent_err is not None:
        print(agent_err, file=sys.stderr)
        return EXIT_USAGE

    # --batch mode: skip single-run input resolution
    batch_file = getattr(args, "batch_file", None)
    if batch_file:
        try:
            runtime = Runtime.from_config(args.path)
        except ConfigError as exc:
            print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
            return EXIT_VALIDATION
        fmt = _default_format(args.format)
        try:
            return asyncio.run(
                _run_batch(
                    runtime,
                    agent_id=agent_id or "",
                    batch_file=batch_file,
                    concurrency=getattr(args, "concurrency", 1),
                    timeout=getattr(args, "timeout", None),
                    fmt=fmt,
                )
            )
        finally:
            try:
                asyncio.run(runtime.close())
            except Exception:  # pragma: no cover
                pass

    prompt = _resolve_input(args)
    if prompt is None:
        print("no input provided. Pass --input, --input-file, or pipe text on stdin.", file=sys.stderr)
        return EXIT_USAGE

    fmt = _default_format(args.format)
    session_id = args.session_id or f"cli-{uuid.uuid4().hex[:8]}"

    deps: Any = None
    if getattr(args, "deps_factory", None):
        try:
            deps = _load_deps(args.deps_factory)
        except (ImportError, AttributeError) as exc:
            print(f"--deps: {exc}", file=sys.stderr)
            return EXIT_USAGE

    try:
        runtime = Runtime.from_config(args.path)
    except ConfigError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_VALIDATION

    subscriber: Any | None = None
    if not args.no_stream:
        if fmt == "events":
            subscriber = _JsonlSubscriber()
        elif fmt == "text" and not _has_rich_console_bus(runtime):
            subscriber = _TextSubscriber()
    if subscriber is not None:
        _attach_subscriber(runtime, subscriber.handle)

    timeout = getattr(args, "timeout", None)
    try:
        coro = _run_once(
            runtime,
            agent_id=agent_id or "",
            session_id=session_id,
            input_text=prompt,
            deps=deps,
        )
        if timeout is not None:

            async def _with_timeout() -> Any:
                return await asyncio.wait_for(coro, timeout=timeout)

            result = asyncio.run(_with_timeout())
        else:
            result = asyncio.run(coro)
    except asyncio.TimeoutError:
        print(f"TimeoutError: run exceeded {timeout}s", file=sys.stderr)
        try:
            asyncio.run(runtime.close())
        except Exception:  # pragma: no cover
            pass
        return EXIT_RUNTIME
    except ConfigError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        try:
            asyncio.run(runtime.close())
        except Exception:  # pragma: no cover - best-effort cleanup
            pass
        return EXIT_RUNTIME

    _emit_final_output(result, fmt)

    if getattr(args, "save_image", None):
        _save_image(result, runtime, args.save_image)

    try:
        asyncio.run(runtime.close())
    except Exception:  # pragma: no cover - best-effort cleanup
        pass
    if result.error_details is not None:
        return EXIT_RUNTIME
    return EXIT_OK


def _count_seams(cfg: Any) -> int:
    seam_names = ("memory", "pattern", "tool_executor", "context_assembler")
    count = 0
    for agent in getattr(cfg, "agents", []):
        for s in seam_names:
            if getattr(agent, s, None) is not None:
                count += 1
    return count


def _run_dry_run(args: argparse.Namespace) -> int:
    _load_dotenv(Path(args.path).resolve().parent)
    try:
        cfg = load_config(args.path)
    except ConfigError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    try:
        Runtime.from_config(args.path)
    except ConfigError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    n_agents = len(getattr(cfg, "agents", []))
    n_seams = _count_seams(cfg)
    print(f"dry-run OK: {n_agents} agent(s), {n_seams} seam(s) configured")
    return EXIT_OK


async def _run_batch(
    runtime: Any,
    *,
    agent_id: str,
    batch_file: str,
    concurrency: int,
    timeout: float | None,
    fmt: str,
) -> int:
    path = Path(batch_file)
    if not path.exists():
        print(f"batch file not found: {path}", file=sys.stderr)
        return EXIT_USAGE
    try:
        lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except OSError as exc:
        print(f"failed to read batch file: {exc}", file=sys.stderr)
        return EXIT_USAGE

    records: list[dict[str, Any]] = []
    for ln in lines:
        try:
            parsed = json.loads(ln)
        except json.JSONDecodeError as exc:
            print(f"invalid JSON in batch file: {exc}", file=sys.stderr)
            return EXIT_USAGE
        if isinstance(parsed, str):
            records.append({"input_text": parsed})
        elif isinstance(parsed, dict) and "input_text" in parsed:
            records.append(parsed)
        else:
            print(f"batch line must be a JSON string or object with 'input_text': {ln!r}", file=sys.stderr)
            return EXIT_USAGE

    sem = asyncio.Semaphore(max(1, concurrency))
    latencies: list[float] = []
    any_error = False

    async def _execute_one(index: int, rec: dict[str, Any]) -> None:
        nonlocal any_error
        session_id = rec.get("session_id") or f"batch-{uuid.uuid4().hex[:8]}"
        input_text = rec["input_text"]
        t0 = time.monotonic()
        error_str: str | None = None
        output: Any = None
        stop_reason: str = ""
        async with sem:
            try:
                coro = _run_once(runtime, agent_id=agent_id, session_id=session_id, input_text=input_text)
                if timeout is not None:
                    result = await asyncio.wait_for(coro, timeout=timeout)
                else:
                    result = await coro
                output = str(result.final_output) if result.final_output is not None else None
                stop_reason = str(result.stop_reason) if result.stop_reason is not None else ""
                if result.error_details is not None:
                    error_str = str(result.error_details.message)
                    any_error = True
            except asyncio.TimeoutError:
                error_str = f"TimeoutError: run exceeded {timeout}s"
                any_error = True
            except Exception as exc:
                error_str = f"{type(exc).__name__}: {exc}"
                any_error = True
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        latencies.append(elapsed_ms / 1000.0)
        line = json.dumps(
            {
                "index": index,
                "input": input_text,
                "output": output,
                "stop_reason": stop_reason,
                "latency_ms": elapsed_ms,
                "error": error_str,
            },
            ensure_ascii=False,
        )
        sys.stdout.write(line + "\n")
        sys.stdout.flush()

    await asyncio.gather(*[_execute_one(i, rec) for i, rec in enumerate(records)])

    # Summary to stderr
    sorted_lat = sorted(latencies)
    n = len(sorted_lat)
    p50 = sorted_lat[int(n * 0.50)] if n > 0 else 0.0
    p95 = sorted_lat[min(int(n * 0.95), n - 1)] if n > 0 else 0.0
    sys.stderr.write(f"Batch: {len(records)} inputs | p50={p50:.1f}s p95={p95:.1f}s\n")
    return EXIT_RUNTIME if any_error else EXIT_OK


def _save_image(result: Any, runtime: Any, path_str: str) -> None:
    from openagents.cli._screenshot import save_run_image

    dest = Path(path_str)
    try:
        save_run_image(result, runtime, dest)
        print(f"saved: {dest.resolve()}", file=sys.stderr)
    except ImportError as exc:
        print(f"--save-image: {exc}", file=sys.stderr)
    except Exception as exc:
        print(f"--save-image failed: {exc}", file=sys.stderr)
