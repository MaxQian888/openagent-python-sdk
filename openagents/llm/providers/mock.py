"""Deterministic mock LLM provider for local development/tests."""

from __future__ import annotations

import json
from typing import Any

from openagents.llm.base import LLMClient


class MockLLMClient(LLMClient):
    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        _ = (model, temperature, max_tokens)
        user_text = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_text = msg.get("content", "")
                break

        parsed = self._parse_prompt(user_text)
        input_text = parsed.get("input", "")
        history_count = parsed.get("history_count", 0)

        if input_text.startswith("/tool"):
            rest = input_text[len("/tool") :].strip()
            if not rest:
                return json.dumps(
                    {"type": "final", "content": "Usage: /tool <tool_id> <query>"},
                    ensure_ascii=True,
                )
            parts = rest.split(maxsplit=1)
            tool_id = parts[0]
            query = parts[1] if len(parts) == 2 else ""
            return json.dumps(
                {"type": "tool_call", "tool": tool_id, "params": {"query": query}},
                ensure_ascii=True,
            )

        return json.dumps(
            {
                "type": "final",
                "content": f"Echo: {input_text} (history={history_count})",
            },
            ensure_ascii=True,
        )

    def _parse_prompt(self, text: str) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for line in text.splitlines():
            if line.startswith("INPUT:"):
                values["input"] = line[len("INPUT:") :].strip()
            elif line.startswith("HISTORY_COUNT:"):
                raw = line[len("HISTORY_COUNT:") :].strip()
                try:
                    values["history_count"] = int(raw)
                except ValueError:
                    values["history_count"] = 0
        values.setdefault("input", "")
        values.setdefault("history_count", 0)
        return values

