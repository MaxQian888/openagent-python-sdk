"""Custom Impl Plugins Demo — demonstrates all 6 Skill capability hooks.

This example shows how a custom Skill can hook into every phase of the
agent lifecycle using a real Anthropic LLM:
  1. get_system_prompt    — injects persona text into pattern prompt
  2. get_tools            — contributes additional tools at load time
  3. get_metadata         — exposes structured metadata to context
  4. augment_context      — mutates ExecutionContext.state
  5. filter_tools         — removes disallowed tools from the set
  6. before_run           — pre-execution hook
  7. after_run            — post-execution hook

Also demonstrates custom Tool (EchoTool) that reads skill metadata from
context.state to prove augment_context ran before tool execution.

Setup:
    cp .env.example .env
    # add MINIMAX_API_KEY

Run:
    uv run python examples/custom_impl/run_demo.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Add project root so 'examples' can be imported as a package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from openagents.runtime.runtime import Runtime


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def verify_hooks(state: dict) -> None:
    """Print verification of every hook that fired."""
    print("\n--- Skill Hook Verification ---")
    log: list = state.get("_hook_log", [])
    print(f"  Hook log (in call order): {log}")

    checks = [
        ("_skill_augmented",  "augment_context fired"),
        ("_skill_name",        "get_metadata / augment_context set skill name"),
        ("_pre_run_ran",     "before_run fired"),
        ("_post_run_ran",    "after_run fired"),
        ("_last_result",       "after_run captured result"),
        ("_filtered_tools",    "filter_tools removed forbidden_tool"),
    ]
    for key, desc in checks:
        val = state.get(key)
        print(f"  {'[OK]' if val else '[FAIL]'} {desc}: {val}")

    filtered: list = state.get("_filtered_tools", [])
    forbidden_gone = "forbidden_tool" not in filtered
    echo_present = "echo_tool" in filtered
    print(f"\n  {'[OK]' if echo_present else '[FAIL]'} echo_tool kept by filter_tools")
    print(f"  {'[OK]' if forbidden_gone else '[FAIL]'} forbidden_tool was filtered out")

    skill_name = state.get("_skill_name", "unknown")
    print(f"\n  EchoTool received skill_name='{skill_name}' from context.state")


async def main() -> None:
    demo_dir = Path(__file__).parent
    load_env(demo_dir / ".env")

    if not os.environ.get("MINIMAX_API_KEY"):
        print("[ERROR] MINIMAX_API_KEY not set!")
        print("        Copy .env.example to .env and add your MiniMax API key.")
        return

    print("[INFO] Using MiniMax LLM (Anthropic-compatible protocol)\n")

    runtime = Runtime.from_config(demo_dir / "agent.json")
    session_id = "skill-demo-session"

    # -- Turn 1: Tool call via /tool prefix ---------------------------------
    print("=" * 60)
    print("Turn 1: /tool echo_tool hello from skill demo")
    print("=" * 60)
    result1 = await runtime.run(
        agent_id="custom-agent",
        session_id=session_id,
        input_text="/tool echo_tool hello from skill demo",
    )
    print(f"Result: {result1}")

    # -- Turn 2: Plain text --------------------------------------------------
    print("\n" + "=" * 60)
    print("Turn 2: What is agent memory injection?")
    print("=" * 60)
    result2 = await runtime.run(
        agent_id="custom-agent",
        session_id=session_id,
        input_text="What is agent memory injection?",
    )
    print(f"Result: {result2[:300]}...")

    # -- Verify all hooks fired ----------------------------------------------
    state = await runtime.session_manager.get_state(session_id)
    verify_hooks(state)

    await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
