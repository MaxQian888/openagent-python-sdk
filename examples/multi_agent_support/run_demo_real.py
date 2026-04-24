"""LLM-driven demo for the multi_agent_support example.

Runs the refund and tech scenarios against a real Anthropic-compatible
endpoint (defaults to MiniMax). Does NOT run scenarios 3 and 4 — those
rely on scripted inputs (``/tool ...``) that the mock path can drive
deterministically but a real LLM may not choose to emit.

Usage:
    cp examples/multi_agent_support/.env.example examples/multi_agent_support/.env
    # edit .env with LLM_API_KEY / LLM_API_BASE / LLM_MODEL
    uv run python examples/multi_agent_support/run_demo_real.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from rich import box  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.table import Table  # noqa: E402
from rich.text import Text  # noqa: E402

from examples.multi_agent_support.scenarios import (  # noqa: E402
    run_refund_scenario,
    run_tech_scenario,
)
from openagents.runtime.runtime import Runtime  # noqa: E402

HERE = Path(__file__).resolve().parent
REQUIRED_ENV = ("LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL")

console = Console()

_ISOLATION_STYLE = {
    "shared": "cyan",
    "isolated": "yellow",
    "forked": "magenta",
}
_VIA_STYLE = {
    "delegate": "green",
    "transfer": "blue",
}


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _stop_reason_badge(value: str) -> Text:
    style = "green" if value == "completed" else "red"
    return Text(f"[{value}]", style=f"bold {style}")


def _trace_table(trace: list) -> Table:
    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold dim")
    table.add_column("Via", style="bold", min_width=10)
    table.add_column("Parent Agent", min_width=18)
    table.add_column("→", justify="center", min_width=2)
    table.add_column("Child Agent", min_width=18)
    table.add_column("Isolation", min_width=10)
    table.add_column("Child Session", min_width=28, overflow="fold")
    for e in trace:
        via_style = _VIA_STYLE.get(e.via, "white")
        iso_style = _ISOLATION_STYLE.get(e.isolation, "white")
        sid = e.child_session_id if e.child_session_id is not None else "(runtime-allocated)"
        table.add_row(
            Text(e.via, style=via_style),
            e.parent_agent,
            Text("→", style="dim"),
            e.child_agent,
            Text(e.isolation, style=iso_style),
            Text(sid, style="dim"),
        )
    return table


def _print_scenario_result(title: str, result: dict, border_style: str) -> None:
    parent = result["parent_result"]
    tickets = result["tickets"]
    ticket_strs = [f"{t.kind}  customer={t.customer_id}" for t in tickets]

    info = Table.grid(padding=(0, 2))
    info.add_row("[dim]Stop reason[/]", _stop_reason_badge(parent.stop_reason.value))
    info.add_row("[dim]Handoff from[/]", Text(str(parent.metadata.get("handoff_from")), style="bold"))
    info.add_row("[dim]Tickets[/]", Text(", ".join(ticket_strs) or "(none)", style="green"))

    console.print(Panel(info, title=f"[bold]{title}[/]", border_style=border_style, padding=(0, 1)))
    if result.get("trace"):
        console.print("[dim]Delegation trace:[/]")
        console.print(_trace_table(result["trace"]))


async def main() -> int:
    _load_env(HERE / ".env")

    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        console.print(
            Panel(
                f"[red]Missing required env var(s):[/] [bold]{', '.join(missing)}[/]\n"
                f"[dim]See examples/multi_agent_support/.env.example[/]",
                title="[bold red]Configuration Error[/]",
                border_style="red",
            )
        )
        return 2

    model = os.environ.get("LLM_MODEL", "(unknown)")
    base = os.environ.get("LLM_API_BASE", "(unknown)")
    console.print(
        Panel(
            f"[bold]multi_agent_support[/] — LLM-driven demo\n"
            f"[dim]model=[/][cyan]{model}[/]  [dim]base=[/][cyan]{base}[/]",
            border_style="bright_black",
        )
    )

    rt = Runtime.from_config(str(HERE / "agent_real.json"))

    console.print()
    console.rule("[bold white]Scenario 1[/] — [dim]refund flow (LLM-driven)[/]")
    refund = await run_refund_scenario(rt)
    _print_scenario_result("Refund Result", refund, "green")

    console.print()
    console.rule("[bold white]Scenario 2[/] — [dim]tech flow (LLM-driven)[/]")
    tech = await run_tech_scenario(rt)
    _print_scenario_result("Tech Result", tech, "blue")

    console.print()
    console.rule("[bold green]Done[/]")
    console.print()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
