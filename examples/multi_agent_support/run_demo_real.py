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

from examples.multi_agent_support.scenarios import (  # noqa: E402
    run_refund_scenario,
    run_tech_scenario,
)
from openagents.runtime.runtime import Runtime  # noqa: E402

HERE = Path(__file__).resolve().parent
REQUIRED_ENV = ("LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL")


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


def _banner(title: str) -> None:
    bar = "-" * 72
    print(f"\n{bar}\n{title}\n{bar}")


async def main() -> int:
    _load_env(HERE / ".env")

    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        sys.stderr.write(
            f"missing required environment variable(s): {', '.join(missing)}. "
            f"See examples/multi_agent_support/.env.example.\n"
        )
        return 2

    rt = Runtime.from_config(str(HERE / "agent_real.json"))

    _banner("Scenario 1 — refund flow (LLM-driven)")
    refund = await run_refund_scenario(rt)
    parent = refund["parent_result"]
    print(f"  stop_reason: {parent.stop_reason.value}")
    print(f"  handoff_from: {parent.metadata.get('handoff_from')}")
    print(f"  tickets: {[(t.kind, t.customer_id) for t in refund['tickets']]}")

    _banner("Scenario 2 — tech flow (LLM-driven)")
    tech = await run_tech_scenario(rt)
    parent = tech["parent_result"]
    print(f"  stop_reason: {parent.stop_reason.value}")
    print(f"  handoff_from: {parent.metadata.get('handoff_from')}")
    print(f"  tickets: {[(t.kind, t.customer_id) for t in tech['tickets']]}")

    _banner("Done")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
