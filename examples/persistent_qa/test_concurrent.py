"""Concurrent test for Session isolation."""

import asyncio
import os
from pathlib import Path
from openagents import Runtime


def load_env():
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


async def main():
    load_env()
    print("=" * 60)
    print("Concurrent Session Test")
    print("=" * 60)

    runtime = Runtime.from_config("examples/persistent_qa/agent_test.json")

    async def run_session(session_id, msg):
        print(f"  Starting {session_id}...")
        result = await runtime.run(
            agent_id="test_agent",
            session_id=session_id,
            input_text=msg,
        )
        print(f"  {session_id} done: {result[:50]}...")
        return session_id, result

    print("\n[1] Test 3 sessions in PARALLEL:")
    results = await asyncio.gather(
        run_session("session_A", "My name is Alice"),
        run_session("session_B", "My name is Bob"),
        run_session("session_C", "My name is Charlie"),
    )

    print("\n[2] Check if memory is isolated:")
    for sid in ["session_A", "session_B", "session_C"]:
        state = await runtime.session_manager.get_state(sid)
        mv = state.get("memory_view", {})
        print(f"    {sid}: {mv.get('history', [])}")

    print("\n[3] Ask each session about their name:")
    results = await asyncio.gather(
        run_session("session_A", "What is my name?"),
        run_session("session_B", "What is my name?"),
        run_session("session_C", "What is my name?"),
    )

    print(f"\n[4] Active sessions: {runtime.get_session_count()}")

    await runtime.close()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
