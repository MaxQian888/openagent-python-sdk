from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from openagents.errors.exceptions import PluginLoadError
from openagents.plugins.builtin.followup.rule_based import RuleBasedFollowupResolver
from openagents.plugins.registry import get_builtin_plugin_class


def _ctx(input_text: str, history=None):
    return SimpleNamespace(input_text=input_text, memory_view={"history": history} if history is not None else {})


@pytest.mark.asyncio
async def test_rule_match_resolves_with_template():
    resolver = RuleBasedFollowupResolver(config={
        "rules": [{
            "name": "tools",
            "pattern": "which tools",
            "template": "used: {tool_ids}; input: {last_input}",
        }]
    })
    result = await resolver.resolve(context=_ctx("which tools did you use", history=[{
        "input": "hello",
        "output": "world",
        "tool_results": [{"tool_id": "t1"}, {"tool_id": "t2"}],
    }]))
    assert result.status == "resolved"
    assert "t1, t2" in result.output
    assert result.metadata["rule"] == "tools"


@pytest.mark.asyncio
async def test_no_rule_match_returns_none():
    resolver = RuleBasedFollowupResolver(config={"rules": [{"name": "x", "pattern": "zzz", "template": "a"}]})
    assert await resolver.resolve(context=_ctx("hello")) is None


@pytest.mark.asyncio
async def test_rule_match_without_history_abstains():
    resolver = RuleBasedFollowupResolver(config={"rules": [{"name": "x", "pattern": "ping", "template": "a"}]})
    result = await resolver.resolve(context=_ctx("ping", history=[]))
    assert result.status == "abstain"


@pytest.mark.asyncio
async def test_missing_template_key_renders_empty():
    resolver = RuleBasedFollowupResolver(config={
        "rules": [{"name": "x", "pattern": "q", "template": "tools={tool_ids}; unknown={nonexistent}"}]
    })
    result = await resolver.resolve(context=_ctx("q", history=[{"input": "i", "output": "o", "tool_results": []}]))
    assert result.status == "resolved"
    assert "unknown=" in result.output


@pytest.mark.asyncio
async def test_rules_file_loaded(tmp_path: Path):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps([{"name": "f", "pattern": "hi", "template": "hi back"}]), encoding="utf-8")
    resolver = RuleBasedFollowupResolver(config={"rules_file": str(path)})
    result = await resolver.resolve(context=_ctx("hi", history=[{"input": "i", "output": "o"}]))
    assert result.status == "resolved"
    assert result.output == "hi back"


def test_invalid_rules_file_raises_plugin_load_error(tmp_path: Path):
    with pytest.raises(PluginLoadError):
        RuleBasedFollowupResolver(config={"rules_file": str(tmp_path / "missing.json")})


def test_registered_as_builtin():
    assert get_builtin_plugin_class("followup_resolver", "rule_based") is RuleBasedFollowupResolver
