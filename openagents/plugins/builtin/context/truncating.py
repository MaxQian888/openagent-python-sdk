"""Truncating context assembler (count-based, no LLM involved)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from openagents.interfaces.context import ContextAssemblerPlugin, ContextAssemblyResult


class TruncatingContextAssembler(ContextAssemblerPlugin):
    """Builtin context assembler that trims transcript and artifact history.

    Pure count-based truncation. Keeps the last ``max_messages`` entries of
    the transcript and the last ``max_artifacts`` session artifacts. Does
    NOT call an LLM; inserted system message is a plain count summary.

    Renamed from ``SummarizingContextAssembler`` in 0.3.0 because the
    previous name misled users into expecting LLM-driven summarization.
    """

    class Config(BaseModel):
        max_messages: int = 20
        max_artifacts: int = 10
        include_summary_message: bool = True

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities=set())
        cfg = self.Config.model_validate(self.config)
        self._max_messages = cfg.max_messages
        self._max_artifacts = cfg.max_artifacts
        self._include_summary_message = cfg.include_summary_message

    async def assemble(
        self,
        *,
        request: Any,
        session_state: dict[str, Any],
        session_manager: Any,
    ) -> ContextAssemblyResult:
        transcript = await session_manager.load_messages(request.session_id)
        artifacts = await session_manager.list_artifacts(request.session_id)

        omitted_messages = max(0, len(transcript) - self._max_messages)
        if omitted_messages:
            transcript = transcript[-self._max_messages :]
            if self._include_summary_message:
                transcript = [
                    {
                        "role": "system",
                        "content": f"Summary: omitted {omitted_messages} older message(s)",
                    }
                ] + transcript

        omitted_artifacts = max(0, len(artifacts) - self._max_artifacts)
        if omitted_artifacts:
            artifacts = artifacts[-self._max_artifacts :]

        return ContextAssemblyResult(
            transcript=transcript,
            session_artifacts=artifacts,
            metadata={
                "assembler": "truncating",
                "strategy": "truncating",
                "omitted_messages": omitted_messages,
                "omitted_artifacts": omitted_artifacts,
                "token_counter": "none",
            },
        )

    async def finalize(
        self,
        *,
        request: Any,
        session_state: dict[str, Any],
        session_manager: Any,
        result: Any,
    ) -> Any:
        return result
