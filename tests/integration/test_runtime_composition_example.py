from __future__ import annotations

import pytest

from openagents.runtime.runtime import Runtime


@pytest.mark.asyncio
async def test_runtime_from_runtime_composition_example():
    runtime = Runtime.from_config("examples/runtime_composition/agent.json")

    result = await runtime.run(
        agent_id="runtime-composition",
        session_id="runtime-composition-test",
        input_text="examples/runtime_composition/workspace/note.txt",
    )

    assert result["content"].strip() == "runtime composition example"
    assert result["assembly_metadata"]["assembler"] == "summarizing"
    await runtime.close()
