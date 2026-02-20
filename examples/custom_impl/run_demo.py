from __future__ import annotations

import asyncio
from pathlib import Path

from openagents.runtime import Runtime


async def main() -> None:
    config_path = Path(__file__).with_name("agent.json")
    runtime = Runtime.from_config(config_path)

    out1 = await runtime.run(
        agent_id="assistant_custom",
        session_id="custom-demo",
        input_text="hello custom plugin",
    )
    print("RUN 1:", out1)

    out2 = await runtime.run(
        agent_id="assistant_custom",
        session_id="custom-demo",
        input_text="/weather shanghai",
    )
    print("RUN 2:", out2)


if __name__ == "__main__":
    asyncio.run(main())

