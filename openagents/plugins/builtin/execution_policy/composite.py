"""Composite execution policy (AND/OR combinator)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from openagents.interfaces.tool import (
    ExecutionPolicyPlugin,
    PolicyDecision,
    ToolExecutionRequest,
)


class CompositeExecutionPolicy(ExecutionPolicyPlugin):
    """Combine multiple execution policies with AND (``all``) or OR (``any``) semantics.

    What:
        Loads each child policy via the plugin loader and combines
        their decisions. ``mode='all'`` denies if any child denies;
        ``mode='any'`` allows if any child allows. Useful for
        layering filesystem + network + custom policies.

    Usage:
        ``{"execution_policy": {"type": "composite", "config":
        {"mode": "all", "policies": [{"type": "filesystem", "config":
        {...}}, {"type": "network_allowlist", "config": {...}}]}}}``

    Depends on:
        - :func:`openagents.plugins.loader.load_plugin` for child
          policies
    """

    class Config(BaseModel):
        policies: list[dict[str, Any]]
        mode: Literal["all", "any"] = "all"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities=set())
        cfg = self.Config.model_validate(self.config)
        self._mode = cfg.mode
        self._children = [self._load_child(ref) for ref in cfg.policies]

    def _load_child(self, ref: dict[str, Any]) -> Any:
        from openagents.config.schema import ExecutionPolicyRef
        from openagents.plugins.loader import load_plugin

        return load_plugin("execution_policy", ExecutionPolicyRef(**ref), required_methods=("evaluate",))

    async def evaluate(self, request: ToolExecutionRequest) -> PolicyDecision:
        child_metadata: list[dict[str, Any]] = []
        if not self._children:
            return PolicyDecision(
                allowed=True,
                metadata={"policy": "composite", "children": [], "decided_by": "default"},
            )
        for index, child in enumerate(self._children):
            try:
                decision = await child.evaluate(request)
            except Exception as exc:
                return PolicyDecision(
                    allowed=False,
                    reason=f"child {index} raised: {exc}",
                    metadata={
                        "policy": "composite",
                        "error_type": type(exc).__name__,
                        "decided_by": index,
                        "children": child_metadata,
                    },
                )
            child_metadata.append({
                "index": index,
                "allowed": decision.allowed,
                "reason": decision.reason,
                "metadata": dict(decision.metadata),
            })
            if self._mode == "all" and not decision.allowed:
                return PolicyDecision(
                    allowed=False,
                    reason=decision.reason,
                    metadata={"policy": "composite", "decided_by": index, "children": child_metadata},
                )
            if self._mode == "any" and decision.allowed:
                return PolicyDecision(
                    allowed=True,
                    reason=decision.reason,
                    metadata={"policy": "composite", "decided_by": index, "children": child_metadata},
                )
        if self._mode == "all":
            return PolicyDecision(
                allowed=True,
                metadata={"policy": "composite", "decided_by": "all_passed", "children": child_metadata},
            )
        last_reason = child_metadata[-1]["reason"] if child_metadata else "no policies allowed"
        return PolicyDecision(
            allowed=False,
            reason=last_reason,
            metadata={"policy": "composite", "decided_by": "none_allowed", "children": child_metadata},
        )
