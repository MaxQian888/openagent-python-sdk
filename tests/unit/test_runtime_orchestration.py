import asyncio
import time

import pytest

from openagents.config.loader import load_config_dict
from openagents.runtime.runtime import Runtime


def _payload(memory_impl: str, pattern_impl: str, *, on_error: str = "continue") -> dict:
    return {
        "version": "1.0",
        "agents": [
            {
                "id": "assistant",
                "name": "runtime-test-agent",
                "memory": {"impl": memory_impl, "on_error": on_error},
                "pattern": {"impl": pattern_impl},
                "llm": {"provider": "mock"},
                "tools": [],
                "runtime": {
                    "max_steps": 8,
                    "step_timeout_ms": 1000,
                    "session_queue_size": 100,
                    "event_queue_size": 100,
                },
            }
        ],
    }


@pytest.mark.asyncio
async def test_runtime_inject_react_writeback_flow():
    config = load_config_dict(
        _payload(
            "tests.fixtures.runtime_plugins.InjectWritebackMemory",
            "tests.fixtures.runtime_plugins.FinalPattern",
        )
    )
    runtime = Runtime(config)

    result = await runtime.run(
        agent_id="assistant",
        session_id="s1",
        input_text="hello",
    )

    assert result == "injected=True"
    session_state = await runtime.session_manager.get_state("s1")
    assert session_state.get("memory_written") is True


@pytest.mark.asyncio
async def test_runtime_memory_error_continue():
    config = load_config_dict(
        _payload(
            "tests.fixtures.runtime_plugins.FailingInjectMemory",
            "tests.fixtures.runtime_plugins.FinalPattern",
            on_error="continue",
        )
    )
    runtime = Runtime(config)

    result = await runtime.run(
        agent_id="assistant",
        session_id="s1",
        input_text="hello",
    )

    assert result == "injected=False"
    assert any(evt.name == "memory.inject_failed" for evt in runtime.event_bus.history)


@pytest.mark.asyncio
async def test_runtime_memory_error_fail():
    config = load_config_dict(
        _payload(
            "tests.fixtures.runtime_plugins.FailingInjectMemory",
            "tests.fixtures.runtime_plugins.FinalPattern",
            on_error="fail",
        )
    )
    runtime = Runtime(config)

    with pytest.raises(RuntimeError, match="inject failed"):
        await runtime.run(agent_id="assistant", session_id="s1", input_text="hello")


@pytest.mark.asyncio
async def test_runtime_same_session_serial_execution():
    payload = _payload(
        "tests.fixtures.runtime_plugins.InjectWritebackMemory",
        "tests.fixtures.runtime_plugins.SlowFinalPattern",
    )
    payload["agents"][0]["pattern"]["config"] = {"delay": 0.05}
    config = load_config_dict(payload)
    runtime = Runtime(config)

    start = time.perf_counter()
    await asyncio.gather(
        runtime.run(agent_id="assistant", session_id="same", input_text="1"),
        runtime.run(agent_id="assistant", session_id="same", input_text="2"),
    )
    elapsed = time.perf_counter() - start

    assert elapsed >= 0.09

