from __future__ import annotations

import pytest

from openagents.runtime.runtime import Runtime


@pytest.mark.asyncio
async def test_runtime_from_repo_custom_impl_example():
    runtime = Runtime.from_config("examples/custom_impl/agent.json")

    result = await runtime.run(
        agent_id="custom-agent",
        session_id="custom-example",
        input_text="hello example",
    )

    assert result.startswith("custom:")
    await runtime.close()
