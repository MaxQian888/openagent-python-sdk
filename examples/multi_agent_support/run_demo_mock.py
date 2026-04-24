"""Offline mock-driven demo for the multi_agent_support example.

Runs all four scenarios end-to-end against builtin mock LLMs, prints
a human-readable summary for each, and exits 0 on success. No network
calls. No API keys. CI-safe.

Usage:
    uv run python examples/multi_agent_support/run_demo_mock.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from rich import box  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.table import Table  # noqa: E402
from rich.text import Text  # noqa: E402

from examples.multi_agent_support.scenarios import (  # noqa: E402
    assert_refund_outcome,
    assert_tech_outcome,
    run_depth_scenario,
    run_refund_scenario,
    run_tech_scenario,
    run_unknown_agent_scenario,
)
from openagents.runtime.runtime import Runtime  # noqa: E402

HERE = Path(__file__).resolve().parent
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


def _scenario_header(number: int, title: str) -> None:
    console.print()
    console.rule(f"[bold white]Scenario {number}[/] — [dim]{title}[/]")


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


async def demo_refund() -> None:
    _scenario_header(1, "refund flow (transfer + shared delegate)")
    rt = Runtime.from_config(str(HERE / "agent_mock.json"))
    result = await run_refund_scenario(rt)
    assert_refund_outcome(result)

    parent = result["parent_result"]
    ticket = result["tickets"][0]

    info = Table.grid(padding=(0, 2))
    info.add_row("[dim]Stop reason[/]", _stop_reason_badge(parent.stop_reason.value))
    info.add_row("[dim]Handoff from[/]", Text(str(parent.metadata.get("handoff_from")), style="bold"))
    info.add_row(
        "[dim]Ticket[/]",
        Text(f"{ticket.kind}  customer={ticket.customer_id}  resolution={ticket.resolution}", style="green"),
    )

    console.print(Panel(info, title="[bold]Refund Result[/]", border_style="green", padding=(0, 1)))
    console.print("[dim]Delegation trace:[/]")
    console.print(_trace_table(result["trace"]))


async def demo_tech() -> None:
    _scenario_header(2, "tech flow (forked diagnostic + isolated fallback)")
    rt = Runtime.from_config(str(HERE / "agent_mock.json"))
    result = await run_tech_scenario(rt)
    assert_tech_outcome(result)

    parent = result["parent_result"]
    ticket = result["tickets"][0]

    info = Table.grid(padding=(0, 2))
    info.add_row("[dim]Stop reason[/]", _stop_reason_badge(parent.stop_reason.value))
    info.add_row("[dim]Handoff from[/]", Text(str(parent.metadata.get("handoff_from")), style="bold"))
    info.add_row(
        "[dim]Ticket[/]",
        Text(f"{ticket.kind}  customer={ticket.customer_id}  resolution={ticket.resolution}", style="green"),
    )

    console.print(Panel(info, title="[bold]Tech Result[/]", border_style="blue", padding=(0, 1)))
    console.print("[dim]Delegation trace:[/]")
    console.print(_trace_table(result["trace"]))


async def demo_depth_limit() -> None:
    _scenario_header(3, "delegation depth limit (max_delegation_depth=3)")
    rt = Runtime.from_config(str(HERE / "agent_mock_scenario3.json"))
    err = await run_depth_scenario(rt)

    info = Table.grid(padding=(0, 2))
    info.add_row("[dim]Exception[/]", Text(type(err).__name__, style="bold red"))
    info.add_row("[dim]Depth / Limit[/]", Text(f"{err.depth} / {err.limit}", style="yellow"))
    info.add_row("[dim]Message[/]", Text(str(err), style="dim"))

    console.print(Panel(info, title="[bold]Depth Limit Enforced[/]", border_style="red", padding=(0, 1)))


async def demo_unknown_agent() -> None:
    _scenario_header(4, "unknown agent_id (AgentNotFoundError)")
    rt = Runtime.from_config(str(HERE / "agent_mock_scenario4.json"))
    err = await run_unknown_agent_scenario(rt)

    info = Table.grid(padding=(0, 2))
    info.add_row("[dim]Exception[/]", Text(type(err).__name__, style="bold red"))
    info.add_row("[dim]Agent ID[/]", Text(repr(err.agent_id), style="yellow"))
    info.add_row("[dim]Message[/]", Text(str(err), style="dim"))

    console.print(Panel(info, title="[bold]Agent Not Found[/]", border_style="red", padding=(0, 1)))


async def main() -> None:
    console.print(
        Panel(
            "[bold]multi_agent_support[/] — offline mock demo\n[dim]No API key required. No network calls. CI-safe.[/]",
            border_style="bright_black",
        )
    )

    await demo_refund()
    await demo_tech()
    await demo_depth_limit()
    await demo_unknown_agent()

    console.print()
    console.rule("[bold green]All 4 scenarios passed[/]")
    console.print()


if __name__ == "__main__":
    asyncio.run(main())
