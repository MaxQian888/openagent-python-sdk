"""Internal rich helpers.

All `rich` imports live here behind import-time guards. Public callers
(configure(), RichConsoleEventBus) use the factories exposed here and
receive RichNotInstalledError if rich is missing.
"""

from __future__ import annotations

from typing import Any, Literal

from openagents.observability.errors import RichNotInstalledError


def _require_rich() -> Any:
    try:
        import rich  # noqa: F401
    except ImportError as exc:
        raise RichNotInstalledError() from exc
    return rich


def make_console(stream: Literal["stdout", "stderr"] = "stderr") -> Any:
    """Return a rich.console.Console writing to the requested stream."""
    _require_rich()
    import sys

    from rich.console import Console

    target = sys.stderr if stream == "stderr" else sys.stdout
    return Console(file=target, force_terminal=True, highlight=False)


def make_rich_handler(*, stream: Literal["stdout", "stderr"], show_time: bool, show_path: bool) -> Any:
    """Return a configured rich.logging.RichHandler."""
    _require_rich()
    from rich.logging import RichHandler

    console = make_console(stream)
    handler = RichHandler(
        console=console,
        show_time=show_time,
        show_level=True,
        show_path=show_path,
        rich_tracebacks=True,
        markup=False,
    )
    handler._openagents_installed = True  # type: ignore[attr-defined]
    return handler


_MAX_STR_LEN = 4000


def _render_value(v: Any, depth: int = 0) -> Any:
    """Recursively render a payload value as a Rich renderable."""
    from rich.table import Table
    from rich.text import Text

    if isinstance(v, dict):
        if not v:
            return Text("{}", style="dim")
        tbl = Table.grid(padding=(0, 1))
        tbl.add_column(justify="right", style="cyan", no_wrap=True)
        tbl.add_column()
        for dk, dv in v.items():
            tbl.add_row(f"{dk}:", _render_value(dv, depth + 1))
        return tbl
    if isinstance(v, list):
        if not v:
            return Text("[]", style="dim")
        tbl = Table.grid(padding=(0, 0))
        tbl.add_column()
        for item in v:
            tbl.add_row(_render_value(item, depth + 1))
        return tbl
    if isinstance(v, str):
        display = v if len(v) <= _MAX_STR_LEN else v[:_MAX_STR_LEN] + f"\n… [{len(v) - _MAX_STR_LEN} chars truncated]"
        if "\n" in display:
            from rich.markdown import Markdown

            return Markdown(display)
        return Text(display)
    return Text(repr(v), style="dim")


_EVENT_NAME_STYLE: dict[str, str] = {
    "session.run.started": "bold cyan",
    "session.run.completed": "bold cyan",
    "llm.called": "bold blue",
    "llm.succeeded": "bold blue",
    "llm.failed": "bold red",
    "tool.called": "bold green",
    "tool.succeeded": "bold green",
    "tool.failed": "bold red",
    "tool.retry_requested": "bold yellow",
    "budget.cost_skipped": "bold yellow",
    "budget.exhausted": "bold red",
    "validation.retry": "bold yellow",
    "artifact.emitted": "bold magenta",
    "usage.updated": "bold blue",
}

_KEY_STYLE = "dim"
_VALUE_STYLE = "white"
_VALUE_TRUNCATE = 60


def _event_name_style(name: str) -> str:
    if name in _EVENT_NAME_STYLE:
        return _EVENT_NAME_STYLE[name]
    prefix = name.split(".")[0]
    return {
        "session": "bold cyan",
        "llm": "bold blue",
        "tool": "bold green",
        "budget": "bold yellow",
        "validation": "bold yellow",
        "artifact": "bold magenta",
        "usage": "bold blue",
    }.get(prefix, "bold white")


def render_event_row(event: Any, *, show_payload: bool) -> Any:
    """Render a RuntimeEvent into a rich Renderable.

    - show_payload=False: single-line Text "name  key=val ..." with per-event colors
    - show_payload=True: Panel with expanded per-field rows; dicts and
      lists are recursively expanded, strings rendered without repr quotes.
    """
    _require_rich()
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    name = event.name
    payload = event.payload or {}

    if not show_payload:
        line = Text()
        line.append(f"{name}", style=_event_name_style(name))
        for k, v in payload.items():
            if k.startswith("_"):
                continue
            if k in ("session_id", "run_id"):
                continue
            if v is None or v == {} or v == []:
                continue
            line.append("  ")
            line.append(f"{k}=", style=_KEY_STYLE)
            raw = repr(v) if not isinstance(v, str) else v
            display = raw if len(raw) <= _VALUE_TRUNCATE else raw[:_VALUE_TRUNCATE] + "…"
            line.append(display, style=_VALUE_STYLE)
        return line

    table = Table.grid(padding=(0, 1))
    table.add_column(justify="right", style="bold", no_wrap=True)
    table.add_column()
    for k, v in payload.items():
        table.add_row(f"{k} =", _render_value(v))
    return Panel(table, title=Text(name, style=_event_name_style(name)), title_align="left")
