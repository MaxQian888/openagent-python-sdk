"""Persistent QA Assistant Demo — file-backed memory with search fallback.

Demonstrates:
  • Custom PersistentMemory plugin (stores history to JSON files)
  • Keyword search across persisted history
  • Multi-turn conversation with persistence across sessions
  • MiniMax LLM via Anthropic-compatible protocol

Setup:
    cp .env.example .env
    # add MINIMAX_API_KEY

Run:
    uv run python examples/persistent_qa/run_demo.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from openagents import Runtime


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


async def show_history(session_id: str) -> None:
    """Show stored history from disk."""
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
    memory_file = Path(".agent_memory") / f"memory_{safe_id}.json"
    if memory_file.exists():
        with open(memory_file, encoding="utf-8") as f:
            history = json.load(f)
        print(f"[HISTORY] {len(history)} items stored:")
        for i, item in enumerate(history, 1):
            inp = item.get("input", "")[:50]
            ts = item.get("timestamp", "")[:19]
            print(f"  {i}. [{ts}] {inp}...")
    else:
        print("[HISTORY] No file found")


async def main() -> None:
    demo_dir = Path(__file__).parent
    load_env(demo_dir / ".env")

    if not os.environ.get("MINIMAX_API_KEY"):
        print("[ERROR] MINIMAX_API_KEY not set!")
        print("        Copy .env.example to .env and add your MiniMax API key.")
        return

    print("[INFO] Using MiniMax LLM (Anthropic-compatible protocol)\n")

    runtime = Runtime.from_config(demo_dir / "agent.json")
    session_id = "qa-demo-001"

    print("=" * 60)
    print("Persistent QA Assistant")
    print("=" * 60)
    print()
    print("Commands:")
    print("  /new      — start a new session")
    print("  /history  — show persisted conversation history")
    print("  /quit     — exit")
    print()

    # Show existing history if any
    await show_history(session_id)

    try:
        while True:
            try:
                user_input = input("[You] ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting...")
                break

            if not user_input:
                continue

            if user_input.startswith("/"):
                cmd = user_input.lower()
                if cmd in ("/quit", "/exit", "/q"):
                    print("Goodbye!")
                    break
                elif cmd == "/new":
                    session_id = f"qa-demo-{hash(user_input) % 100000:05d}"
                    print(f"[INFO] New session: {session_id}")
                    continue
                elif cmd == "/history":
                    await show_history(session_id)
                    continue
                else:
                    print(f"[WARN] Unknown command: {user_input}")
                    continue

            print(f"[Session] {session_id}")
            print("[Agent] ", end="", flush=True)

            try:
                result = await runtime.run(
                    agent_id="qa_assistant",
                    session_id=session_id,
                    input_text=user_input,
                )
                print(result)
                print("  [MEMORY] Saved to .agent_memory/")
            except Exception as e:
                print(f"[ERROR] {e}")

    finally:
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
