"""Persistent QA Assistant Demo.

A persistent question-answering assistant that:
- Remembers past conversations
- Uses LongCat LLM for answering
- Falls back to memory search when LLM fails
- Supports weather and search tools

Usage:
    # Set API key
    export LONGCAT_API_KEY=sk-xxx

    # Run demo
    python run_demo.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from openagents import Runtime
from openagents.config.loader import load_config


def load_env() -> None:
    """Load environment variables."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


async def main() -> None:
    """Run the persistent QA assistant demo."""
    import pathlib

    # Load environment
    load_env()

    # Check API key
    api_key = os.environ.get("LONGCAT_API_KEY")
    if not api_key:
        print("[WARN] LONGCAT_API_KEY not found in environment")
        print("[INFO] Set it via: export LONGCAT_API_KEY=sk-xxx")
        print("[INFO] Or create .env file with LONGCAT_API_KEY=sk-xxx")
        print()

    # Load config
    demo_dir = pathlib.Path(__file__).parent
    config_path = demo_dir / "agent.json"
    config = load_config(config_path)

    # Override API key if provided
    if api_key and config.agents:
        config.agents[0].llm.api_key = api_key

    # Create runtime
    runtime = Runtime(config)

    # Setup event listeners
    async def on_event(event):
        print(f"  [EVENT] {event.name}")

    runtime.event_bus.subscribe("llm.", on_event)
    runtime.event_bus.subscribe("tool.", on_event)
    runtime.event_bus.subscribe("qa.", on_event)

    print("=" * 60)
    print("Persistent QA Assistant Demo")
    print("=" * 60)
    print()
    print("This assistant:")
    print("- Remembers past conversations (persisted to JSON files)")
    print("- Uses LongCat LLM for answering")
    print("- Falls back to memory search when LLM fails")
    print("- Supports weather and search tools")
    print()
    print("Commands:")
    print("  /new     - Start a new session")
    print("  /history - Show conversation history")
    print("  /quit    - Exit")
    print()

    # Session management
    session_id = "qa-session-001"

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
                    session_id = f"qa-session-{hash(user_input) % 100000}"
                    print(f"[INFO] New session: {session_id}")
                    continue

                elif cmd == "/history":
                    # Show stored history
                    import json
                    from pathlib import Path
                    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
                    memory_file = Path(".agent_memory") / f"memory_{safe_id}.json"
                    if memory_file.exists():
                        with open(memory_file, "r", encoding="utf-8") as f:
                            history = json.load(f)
                        print(f"[HISTORY] {len(history)} conversations stored:")
                        for i, item in enumerate(history, 1):
                            print(f"  {i}. Q: {item.get('input', '')[:50]}...")
                    else:
                        print("[HISTORY] No history found")
                    continue

                else:
                    print(f"[WARN] Unknown command: {cmd}")
                    continue

            # Run agent
            print(f"[Session] {session_id}")
            print("[Agent] ", end="", flush=True)

            try:
                result = await runtime.run(
                    agent_id="qa_assistant",
                    session_id=session_id,
                    input_text=user_input,
                )
                print(result)

                # Show memory status
                state = await runtime.session_manager.get_state(session_id)
                memory_view = state.get("_pattern_context", {}).get("memory_view", {})
                if memory_view.get("saved"):
                    print(f"  [MEMORY] Saved to persistent storage")

            except Exception as e:
                print(f"[ERROR] {e}")

    finally:
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
