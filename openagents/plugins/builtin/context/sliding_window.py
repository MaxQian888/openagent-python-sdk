"""Sliding-window token-budget context assembler."""

from __future__ import annotations

from typing import Any

from openagents.plugins.builtin.context.base import TokenBudgetContextAssembler


class SlidingWindowContextAssembler(TokenBudgetContextAssembler):
    """Keep as many trailing messages as fit within the token budget.

    What:
        Older messages are dropped first. Suited to dialog-style
        agents where recency dominates and system instructions are
        injected by the pattern through a separate channel.

    Usage:
        ``{"context_assembler": {"type": "sliding_window", "config":
        {"max_input_tokens": 8000, "reserve_for_response": 2000,
        "max_artifacts": 10}}}``

    Depends on:
        - :class:`TokenBudgetContextAssembler` (parent class) for
          token counting via the LLM client
    """

    def _trim_by_budget(
        self,
        llm_client: Any,
        msgs: list[dict[str, Any]],
        budget: int,
    ) -> tuple[list[dict[str, Any]], int]:
        kept: list[dict[str, Any]] = []
        remaining = budget
        for m in reversed(msgs):
            cost = self._measure(llm_client, m)
            if cost > remaining:
                break
            kept.append(m)
            remaining -= cost
        kept.reverse()
        return kept, max(0, len(msgs) - len(kept))
