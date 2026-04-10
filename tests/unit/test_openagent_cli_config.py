from __future__ import annotations

import json
from pathlib import Path


def test_openagent_cli_default_config_prefers_deterministic_tool_use():
    config_path = Path(__file__).resolve().parents[2] / "openagent_cli" / "config" / "agent.json"
    data = json.loads(config_path.read_text(encoding="utf-8"))

    agent = data["agents"][0]
    assert agent["llm"]["temperature"] == 0.0
    assert agent["pattern"]["config"]["empty_stream_retries"] == 2
