"""
Research Agent Example - Interactive Mode

A production-ready research agent that uses LongCat API to:
- Search the web for information
- Fetch and parse web pages
- Maintain conversation history
- Handle errors gracefully with fallbacks

Usage:
    # Copy .env.example to .env and add your API key
    cp .env.example .env

    # Run the example (interactive mode)
    python run_demo.py

Commands:
    /help - Show this help message
    /new - Start a new session
    /session - Show current session ID
    /quit or /exit - Exit the program
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from openagents import Runtime
from openagents.config.loader import load_config


def load_env(path: Path) -> None:
    """Load environment variables from .env file."""
    if not path.exists():
        print(f"[WARN] .env file not found at {path}")
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


def build_runtime(config_path: Path) -> Runtime:
    """Build Runtime from config with environment overrides."""
    config = load_config(config_path)

    if config.agents:
        agent = config.agents[0]
        if agent.llm:
            api_key = os.environ.get("LONGCAT_API_KEY")
            if api_key:
                agent.llm.api_key = api_key

    return Runtime(config, _skip_plugin_load=False)


class ResearchAgent:
    """Research Agent with error handling and retry logic."""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.runtime = None
        self._initialize()

    def _initialize(self) -> None:
        """Initialize the runtime."""
        print("[INFO] Initializing Research Agent...")

        env_path = self.config_path.parent / ".env"
        load_env(env_path)

        api_key = os.environ.get("LONGCAT_API_KEY")
        if not api_key:
            print("[WARN] LONGCAT_API_KEY not found!")
            print("[WARN] Set it in .env file or environment")

        try:
            self.runtime = build_runtime(self.config_path)
            print("[INFO] Runtime initialized\n")

            self._setup_event_listeners()

        except Exception as e:
            print(f"[ERROR] Failed to initialize: {e}")
            raise

    def _setup_event_listeners(self) -> None:
        """Set up event listeners for monitoring."""
        if not self.runtime or not self.runtime.event_bus:
            return

        async def on_tool_called(event):
            print(f"  [TOOL] Calling: {event.payload.get('tool_id')}")

        async def on_tool_succeeded(event):
            print(f"  [TOOL] Success: {event.payload.get('tool_id')}")

        async def on_tool_failed(event):
            print(f"  [TOOL] Failed: {event.payload.get('tool_id')} - {event.payload.get('error')}")

        async def on_step_started(event):
            print(f"  [STEP] Starting step {event.payload.get('step')}")

        self.runtime.event_bus.subscribe("tool.called", on_tool_called)
        self.runtime.event_bus.subscribe("tool.succeeded", on_tool_succeeded)
        self.runtime.event_bus.subscribe("tool.failed", on_tool_failed)
        self.runtime.event_bus.subscribe("pattern.step_started", on_step_started)

    async def research(self, query: str, session_id: str) -> str:
        """Run a research query with error handling."""
        if not self.runtime:
            return "[ERROR] Agent not initialized"

        try:
            result = await self.runtime.run(
                agent_id="researcher",
                session_id=session_id,
                input_text=query,
            )
            return result

        except TimeoutError as e:
            return f"[ERROR] Request timed out: {e}"
        except Exception as e:
            return f"[ERROR] Request failed: {e}"

    async def close(self) -> None:
        """Clean up resources."""
        if self.runtime:
            await self.runtime.close()


def print_help() -> None:
    """Print help message."""
    help_text = """
Commands:
  /help         - Show this help message
  /new          - Start a new session
  /session      - Show current session ID
  /sessions     - List all sessions
  /quit or /exit - Exit the program

Tips:
  - Type your question to start researching
  - The agent remembers your conversation within the same session
  - Use /new to start a fresh conversation
"""
    print(help_text)


async def main() -> None:
    """Main interactive loop."""
    base_dir = Path(__file__).parent

    # Initialize agent
    agent = ResearchAgent(base_dir / "agent.json")

    # Session management
    session_id = f"session-{os.getpid()}"
    sessions = set()

    print_help()

    try:
        while True:
            try:
                user_input = input("\n[You] ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nExiting...")
                break

            if not user_input:
                continue

            # Handle commands
            if user_input.startswith("/"):
                cmd = user_input.lower()

                if cmd in ("/quit", "/exit", "/q"):
                    print("Goodbye!")
                    break

                elif cmd == "/help":
                    print_help()
                    continue

                elif cmd == "/new":
                    session_id = f"session-{os.getpid()}-{len(sessions)}"
                    sessions.add(session_id)
                    print(f"[INFO] New session: {session_id}")
                    continue

                elif cmd == "/session":
                    print(f"[INFO] Current session: {session_id}")
                    continue

                elif cmd == "/sessions":
                    print(f"[INFO] Sessions: {list(sessions) if sessions else [session_id]}")
                    continue

                else:
                    print(f"[WARN] Unknown command: {user_input}")
                    print("Type /help for available commands")
                    continue

            # Process research query
            print(f"\n[Session] {session_id}")
            print("[Agent] ", end="", flush=True)

            result = await agent.research(user_input, session_id)
            print(result)

    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
