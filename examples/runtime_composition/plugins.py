from __future__ import annotations

from typing import Any

from openagents.interfaces.capabilities import PATTERN_EXECUTE, PATTERN_REACT
from openagents.interfaces.pattern import ExecutionContext


class RuntimeCompositionPattern:
    """Pattern used to demonstrate agent-level runtime seam composition."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.capabilities = {PATTERN_EXECUTE, PATTERN_REACT}
        self.context: ExecutionContext | None = None

    async def setup(
        self,
        agent_id: str,
        session_id: str,
        input_text: str,
        state: dict[str, Any],
        tools: dict[str, Any],
        llm_client: Any,
        llm_options: Any,
        event_bus: Any,
    ) -> None:
        self.context = ExecutionContext(
            agent_id=agent_id,
            session_id=session_id,
            input_text=input_text,
            state=state,
            tools=tools,
            llm_client=llm_client,
            llm_options=llm_options,
            event_bus=event_bus,
        )

    async def react(self) -> dict[str, Any]:
        return {"type": "final", "content": "runtime-composition"}

    async def execute(self) -> Any:
        assert self.context is not None
        result = await self.context.tools["read_file"].invoke(
            {"path": self.context.input_text},
            self.context,
        )
        return {
            "content": result["content"],
            "transcript_count": len(self.context.transcript),
            "artifact_names": [artifact.name for artifact in self.context.session_artifacts],
            "assembly_metadata": dict(self.context.assembly_metadata),
        }
