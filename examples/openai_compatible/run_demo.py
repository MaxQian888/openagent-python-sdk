from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

# from openagents.config.loader import load_config_dict
# from openagents.runtime import Runtime
from openagents.utils.build import load_dotenv, build_runtime




async def main() -> None:
    base_dir = Path(__file__).parent
    load_dotenv(base_dir / ".env")
    runtime = build_runtime(base_dir / "agent.json")

    out1 = await runtime.run(
        agent_id="assistant_openai",
        session_id="openai-demo",
        input_text="请简单介绍一下memory inject和writeback",
    )
    print("RUN 1:", out1)

    out2 = await runtime.run(
        agent_id="assistant_openai",
        session_id="openai-demo",
        input_text="/tool search session concurrency",
    )
    print("RUN 2:", out2)


if __name__ == "__main__":
    asyncio.run(main())

