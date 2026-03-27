from __future__ import annotations

import asyncio

from openagents.runtime.runtime import Runtime


async def main() -> None:
    runtime = Runtime.from_config("examples/custom_impl/agent.json")
    try:
        result = await runtime.run(
            agent_id="custom-agent",
            session_id="demo",
            input_text="hello from custom impl",
        )
        print(result)
    finally:
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
