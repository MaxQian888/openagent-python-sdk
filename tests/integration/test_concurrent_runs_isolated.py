"""WP3 stress: concurrent runs against different agents do not cross-talk."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

import openagents.llm.registry as llm_registry
from openagents.llm.providers.mock import MockLLMClient
from openagents.runtime.runtime import Runtime


def _build_config(tmp_path: Path) -> Path:
    payload = {
        "version": "1.0",
        "agents": [
            {
                "id": "alice",
                "name": "alice",
                "memory": {"impl": "tests.fixtures.custom_plugins.CustomMemory"},
                "pattern": {"impl": "tests.fixtures.custom_plugins.CustomPattern"},
                "llm": {"provider": "mock"},
                "tools": [],
                "runtime": {"max_steps": 4, "step_timeout_ms": 1000},
            },
            {
                "id": "bob",
                "name": "bob",
                "memory": {"impl": "tests.fixtures.custom_plugins.CustomMemory"},
                "pattern": {"impl": "tests.fixtures.custom_plugins.CustomPattern"},
                "llm": {"provider": "mock"},
                "tools": [],
                "runtime": {"max_steps": 4, "step_timeout_ms": 1000},
            },
        ],
    }
    cfg = tmp_path / "agents.json"
    cfg.write_text(json.dumps(payload), encoding="utf-8")
    return cfg


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_concurrent_runs_two_agents_isolated_state(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(llm_registry, "create_llm_client", lambda llm: MockLLMClient())
    runtime = Runtime.from_config(_build_config(tmp_path))

    async def _alice():
        return await runtime.run(
            agent_id="alice",
            session_id="alice-sess",
            input_text="alice-msg",
        )

    async def _bob():
        return await runtime.run(
            agent_id="bob",
            session_id="bob-sess",
            input_text="bob-msg",
        )

    results = await asyncio.gather(_alice(), _bob(), _alice(), _bob())
    assert all(r == "ok" for r in results), results

    alice_state = await runtime.session_manager.get_state("alice-sess")
    bob_state = await runtime.session_manager.get_state("bob-sess")

    # Sanity: separate sessions do not share keys
    assert alice_state is not bob_state
