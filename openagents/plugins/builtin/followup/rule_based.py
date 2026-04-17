"""Rule-based follow-up resolver."""

from __future__ import annotations

import collections
import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from openagents.errors.exceptions import PluginLoadError
from openagents.interfaces.followup import FollowupResolution, FollowupResolverPlugin


class Rule(BaseModel):
    name: str
    pattern: str
    template: str
    requires_history: bool = True


class RuleBasedFollowupResolver(FollowupResolverPlugin):
    """Resolve follow-ups via user-configured regex to template rules.

    What:
        Loads a list of ``Rule`` entries (regex pattern + response
        template) from config or an external JSON file, matches the
        most recent user message against them, and returns the
        first hit interpolated with capture groups. Skips rules
        marked ``requires_history`` when the transcript is empty.

    Usage:
        ``{"followup_resolver": {"type": "rule_based", "config":
        {"rules": [{"name": "thanks", "pattern": "^thanks?$",
        "template": "You are welcome!", "requires_history":
        false}]}}}`` or set ``"rules_file": "path/to/rules.json"``.

    Depends on:
        - ``RunContext.input_text``
        - optional rules JSON file at ``rules_file``
    """

    class Config(BaseModel):
        rules_file: str | None = None
        rules: list[Rule] = Field(default_factory=list)

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities=set())
        cfg = self.Config.model_validate(self.config)
        file_rules: list[Rule] = []
        if cfg.rules_file:
            path = Path(cfg.rules_file)
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise PluginLoadError(
                    f"rule_based followup_resolver: could not read rules_file '{cfg.rules_file}': {exc}"
                ) from exc
            if not isinstance(raw, list):
                raise PluginLoadError(
                    f"rule_based followup_resolver: rules_file '{cfg.rules_file}' must be a JSON array"
                )
            for item in raw:
                file_rules.append(Rule.model_validate(item))
        self._rules: list[tuple[Rule, re.Pattern[str]]] = []
        for r in (*file_rules, *cfg.rules):
            try:
                compiled = re.compile(r.pattern, re.IGNORECASE)
            except re.error as exc:
                raise PluginLoadError(
                    f"rule_based followup_resolver: invalid pattern in rule '{r.name}': {exc}"
                ) from exc
            self._rules.append((r, compiled))

    async def resolve(self, *, context: Any) -> FollowupResolution | None:
        text = str(getattr(context, "input_text", "") or "")
        for rule, compiled in self._rules:
            if not compiled.search(text):
                continue
            memory_view = getattr(context, "memory_view", {}) or {}
            history = memory_view.get("history") if isinstance(memory_view, dict) else None
            if rule.requires_history and (not isinstance(history, list) or not history):
                return FollowupResolution(status="abstain", reason="no history", metadata={"rule": rule.name})
            last = history[-1] if isinstance(history, list) and history else {}
            last = last if isinstance(last, dict) else {}
            tool_ids: list[str] = []
            raw_tool_results = last.get("tool_results")
            if isinstance(raw_tool_results, list):
                for item in raw_tool_results:
                    if isinstance(item, dict) and isinstance(item.get("tool_id"), str):
                        tool_ids.append(item["tool_id"])
            mapping = collections.defaultdict(str, {
                "tool_ids": ", ".join(tool_ids),
                "last_input": str(last.get("input", "")),
                "last_output": str(last.get("output", "")),
            })
            rendered = rule.template.format_map(mapping)
            return FollowupResolution(status="resolved", output=rendered, metadata={"rule": rule.name})
        return None
