"""
File Manager Agent Example - Interactive Mode

A production-ready file manager agent that uses LongCat API to:
- Read, write, list, and delete files
- Search content in files
- Parse and process JSON data
- Handle errors gracefully with fallbacks

Usage:
    # Copy .env.example to .env and add your API key
    cp .env.example .env

    # Run the example (interactive mode)
    python run_demo.py

Commands:
    /help     - Show this help message
    /new      - Start a new session
    /pwd      - Show current working directory
    /cd <dir> - Change working directory
    /ls       - List files in working directory
    /session  - Show current session ID
    /quit     - Exit the program

Tips:
    - The agent can perform file operations in the current directory
    - Use natural language to describe what you want to do
    - Examples:
      * "Read the file named config.json"
      * "Create a new file called notes.txt with content 'Hello World'"
      * "List all Python files in the current directory"
      * "Search for 'TODO' in all .py files"
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
    # Try .env first, then fall back to .env.example
    env_file = path if path.exists() else path.with_name(".env.example")

    if not env_file.exists():
        print(f"[WARN] No .env file found at {path} or {env_file}")
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


class FileManagerAgent:
    """File Manager Agent with error handling and retry logic."""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.runtime = None
        self.working_dir = Path.cwd()
        self._initialize()

    def _initialize(self) -> None:
        """Initialize the runtime."""
        print("[INFO] Initializing File Manager Agent...")

        env_path = self.config_path.parent / ".env"
        load_env(env_path)

        # Allow custom working directory from env
        work_dir = os.environ.get("WORK_DIR")
        if work_dir:
            self.working_dir = Path(work_dir)

        print(f"[INFO] Working directory: {self.working_dir}")

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
            payload = event.payload
            tool_id = payload.get("tool_id")
            params = payload.get("params", {})
            print(f"  [TOOL] Calling: {tool_id}")
            if tool_id in ("read", "grep") and "path" in params:
                print(f"         Path: {params.get('path')}")
            elif tool_id == "write" and "path" in params:
                print(f"         Writing to: {params.get('path')}")
            elif tool_id == "delete":
                print(f"         Deleting: {params.get('path')}")

        async def on_tool_succeeded(event):
            tool_id = event.payload.get("tool_id")
            result = event.payload.get("result", {})

            if tool_id == "read" and "content" in result:
                content = result.get("content", "")
                preview = content[:100] + "..." if len(content) > 100 else content
                print(f"  [TOOL] Read {len(content)} bytes")
                print(f"         Preview: {preview}")

        async def on_tool_failed(event):
            print(f"  [TOOL] Failed: {event.payload.get('tool_id')}")
            print(f"         Error: {event.payload.get('error')}")

        async def on_step_started(event):
            step = event.payload.get("step")
            print(f"\n  --- Step {step} ---")

        self.runtime.event_bus.subscribe("tool.called", on_tool_called)
        self.runtime.event_bus.subscribe("tool.succeeded", on_tool_succeeded)
        self.runtime.event_bus.subscribe("tool.failed", on_tool_failed)
        self.runtime.event_bus.subscribe("pattern.step_started", on_step_started)

    def change_directory(self, path: str) -> str:
        """Change working directory."""
        try:
            new_dir = self.working_dir / path
            if not new_dir.exists():
                return f"[ERROR] Directory does not exist: {new_dir}"
            if not new_dir.is_dir():
                return f"[ERROR] Not a directory: {new_dir}"
            self.working_dir = new_dir.resolve()
            return f"[OK] Changed directory to: {self.working_dir}"
        except Exception as e:
            return f"[ERROR] {e}"

    def list_files(self, path: str = ".") -> str:
        """List files in directory."""
        try:
            target = self.working_dir / path if path != "." else self.working_dir
            if not target.exists():
                return f"[ERROR] Path does not exist: {target}"

            if target.is_file():
                return f"[FILE] {target.name} ({target.stat().st_size} bytes)"

            files = []
            for item in sorted(target.iterdir()):
                prefix = "[DIR] " if item.is_dir() else "[FILE]"
                files.append(f"{prefix} {item.name}")

            return "\n".join(files) if files else "[EMPTY] Directory is empty"

        except Exception as e:
            return f"[ERROR] {e}"

    async def execute(self, query: str, session_id: str) -> str:
        """Execute a file operation with error handling."""
        if not self.runtime:
            return "[ERROR] Agent not initialized"

        # Prepend working directory context to help the agent
        enhanced_query = f"""Working directory: {self.working_dir}

{query}"""

        try:
            result = await self.runtime.run(
                agent_id="file_manager",
                session_id=session_id,
                input_text=enhanced_query,
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
  /help       - Show this help message
  /new        - Start a new session
  /pwd        - Show current working directory
  /cd <dir>   - Change working directory
  /ls [path]  - List files in directory
  /session    - Show current session ID
  /quit       - Exit the program

Available Tools:
  - Read files: "Read file named X"
  - Write files: "Create file X with content Y"
  - List files: "List all .py files"
  - Delete files: "Delete file X"
  - Search: "Search for 'pattern' in .py files"

Tips:
  - Use natural language to describe file operations
  - The agent uses Plan-Execute pattern for complex tasks
"""
    print(help_text)


async def main() -> None:
    """Main interactive loop."""
    base_dir = Path(__file__).parent

    # Initialize agent
    agent = FileManagerAgent(base_dir / "agent.json")

    # Session management
    session_id = f"file-session-{os.getpid()}"

    print_help()
    print(f"Working directory: {agent.working_dir}\n")

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
                parts = user_input.split(maxsplit=1)
                cmd = parts[0].lower()
                arg = parts[1] if len(parts) > 1 else None

                if cmd in ("/quit", "/exit", "/q"):
                    print("Goodbye!")
                    break

                elif cmd == "/help":
                    print_help()
                    continue

                elif cmd == "/new":
                    session_id = f"file-session-{os.getpid()}-{hash(user_input) % 10000}"
                    print(f"[INFO] New session: {session_id}")
                    continue

                elif cmd == "/pwd":
                    print(f"[PWD] {agent.working_dir}")
                    continue

                elif cmd == "/cd":
                    if not arg:
                        print("[ERROR] Usage: /cd <directory>")
                        continue
                    result = agent.change_directory(arg)
                    print(result)
                    continue

                elif cmd == "/ls":
                    result = agent.list_files(arg or ".")
                    print(result)
                    continue

                elif cmd == "/session":
                    print(f"[INFO] Current session: {session_id}")
                    continue

                else:
                    print(f"[WARN] Unknown command: {user_input}")
                    print("Type /help for available commands")
                    continue

            # Process file operation query
            print(f"\n[Session] {session_id}")
            print("[Agent] ", end="", flush=True)

            result = await agent.execute(user_input, session_id)
            print(result)

    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
