from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from openagents.config.loader import load_config_dict
from openagents.runtime import Runtime


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def build_runtime(config_path: Path) -> Runtime:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    agent: dict[str, Any] = payload["agents"][0]
    llm: dict[str, Any] = agent.get("llm", {})
    llm["model"] = os.getenv("OPENAI_MODEL", llm.get("model", "gpt-4o-mini"))
    llm["api_base"] = os.getenv("OPENAI_BASE_URL", llm.get("api_base", ""))
    llm["api_key_env"] = "OPENAI_API_KEY"
    agent["llm"] = llm
    return Runtime(load_config_dict(payload))


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

