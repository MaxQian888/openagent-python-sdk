"""App-layer pattern: consult followup_resolver before running ReAct.

This pattern mirrors the idiom established in
``examples/production_coding_agent/app/plugins.py`` (see the ``execute`` method
around lines 261–271). The builtin ``react`` pattern does not itself invoke
``ctx.followup_resolver``; doing so is deliberately an app-layer choice so
different applications can pick their own short-circuit semantics.
"""

from __future__ import annotations

from typing import Any

from openagents.interfaces.pattern import PatternPlugin
from openagents.plugins.builtin.pattern.react import ReActPattern


class FollowupFirstReActPattern(PatternPlugin):
    """Consult ``ctx.followup_resolver`` before delegating to ``ReActPattern``.

    If the resolver returns ``FollowupResolution(status="resolved", ...)``, the
    pattern returns that output directly without invoking the inner ReAct loop
    (and therefore without calling the LLM). Any other outcome — ``None``,
    ``"abstain"``, or ``"error"`` — falls through to the inner pattern, which
    runs normally.
    """

    def __init__(self, config: dict[str, Any] | None = None, inner: Any | None = None):
        super().__init__(config=config or {}, capabilities={"pattern.execute", "pattern.react"})
        self._inner = inner if inner is not None else ReActPattern(config=self.config)

    # Proxy `context` to the inner pattern so the runtime's `setup()` (which
    # assigns `self.context = RunContext(...)`) propagates correctly into the
    # delegate, and downstream attribute reads see the same object.
    @property
    def context(self) -> Any:
        return getattr(self._inner, "context", None)

    @context.setter
    def context(self, value: Any) -> None:
        self._inner.context = value

    async def execute(self) -> Any:
        ctx = self._inner.context
        resolver = getattr(ctx, "followup_resolver", None) if ctx is not None else None
        if resolver is not None:
            try:
                resolution = await resolver.resolve(context=ctx)
            except Exception:
                resolution = None
            if resolution is not None and resolution.status == "resolved":
                if ctx is not None and hasattr(ctx, "state") and ctx.state is not None:
                    ctx.state["_runtime_last_output"] = resolution.output
                    ctx.state["resolved_by"] = "followup_resolver"
                return resolution.output
        return await self._inner.execute()

    async def react(self) -> dict[str, Any]:
        return await self._inner.react()
