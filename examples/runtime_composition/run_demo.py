from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


async def main() -> None:
    example_dir = Path(__file__).resolve().parent
    repo_root = example_dir.parent.parent
    os.chdir(repo_root)
    sys.path.insert(0, str(repo_root))

    from openagents.runtime.runtime import Runtime

    runtime = Runtime.from_config(example_dir / "agent.json")
    target = example_dir / "workspace" / "note.txt"

    first = await runtime.run(
        agent_id="runtime-composition",
        session_id="runtime-composition-demo",
        input_text=str(target),
    )
    second = await runtime.run(
        agent_id="runtime-composition",
        session_id="runtime-composition-demo",
        input_text=str(target),
    )

    print("First run:", first)
    print("Second run:", second)
    await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
