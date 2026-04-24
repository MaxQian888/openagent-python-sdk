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

# Ensure repo root is on sys.path when the file is launched directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

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


def _banner(title: str) -> None:
    bar = "-" * 72
    print(f"\n{bar}\n{title}\n{bar}")


async def demo_refund() -> None:
    _banner("Scenario 1 — refund flow (transfer + shared delegate)")
    rt = Runtime.from_config(str(HERE / "agent_mock.json"))
    result = await run_refund_scenario(rt)
    assert_refund_outcome(result)
    parent = result["parent_result"]
    print(f"  parent stop_reason:   {parent.stop_reason.value}")
    print(f"  handoff_from child:   {parent.metadata.get('handoff_from')}")
    print(f"  tickets issued:       {len(result['tickets'])} ({result['tickets'][0].kind})")
    print("  delegation trace:")
    for e in result["trace"]:
        print(f"    {e.via:<9} {e.parent_agent:>18} -> {e.child_agent:<16} isolation={e.isolation}")


async def demo_tech() -> None:
    _banner("Scenario 2 — tech flow (forked diagnostic + isolated fallback)")
    rt = Runtime.from_config(str(HERE / "agent_mock.json"))
    result = await run_tech_scenario(rt)
    assert_tech_outcome(result)
    parent = result["parent_result"]
    print(f"  parent stop_reason:   {parent.stop_reason.value}")
    print(f"  handoff_from child:   {parent.metadata.get('handoff_from')}")
    print(f"  tickets issued:       {len(result['tickets'])} ({result['tickets'][0].kind})")
    print("  delegation trace:")
    for e in result["trace"]:
        sid = e.child_session_id if e.child_session_id is not None else "(allocated internally)"
        print(f"    {e.via:<9} {e.parent_agent:>18} -> {e.child_agent:<16} isolation={e.isolation:<9} child_sid={sid}")


async def demo_depth_limit() -> None:
    _banner("Scenario 3 — delegation depth limit (max_delegation_depth=3)")
    rt = Runtime.from_config(str(HERE / "agent_mock_scenario3.json"))
    err = await run_depth_scenario(rt)
    print(f"  caught:               {type(err).__name__}")
    print(f"  depth / limit:        {err.depth} / {err.limit}")
    print(f"  message:              {err}")


async def demo_unknown_agent() -> None:
    _banner("Scenario 4 — unknown agent_id (AgentNotFoundError)")
    rt = Runtime.from_config(str(HERE / "agent_mock_scenario4.json"))
    err = await run_unknown_agent_scenario(rt)
    print(f"  caught:               {type(err).__name__}")
    print(f"  agent_id:             {err.agent_id!r}")
    print(f"  message:              {err}")


async def main() -> None:
    print("multi_agent_support — offline mock demo (no API key, no network)")
    await demo_refund()
    await demo_tech()
    await demo_depth_limit()
    await demo_unknown_agent()
    _banner("All 4 scenarios passed")


if __name__ == "__main__":
    asyncio.run(main())
