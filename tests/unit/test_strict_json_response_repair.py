from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from openagents.plugins.builtin.response_repair.strict_json import StrictJsonResponseRepairPolicy
from openagents.plugins.registry import get_builtin_plugin_class


def _ctx():
    return SimpleNamespace(input_text="", memory_view={}, tools={})


async def _call(policy: StrictJsonResponseRepairPolicy, blocks: list[dict]):
    return await policy.repair_empty_response(
        context=_ctx(), messages=[], assistant_content=blocks, stop_reason=None, retries=0,
    )


@pytest.mark.asyncio
async def test_fenced_json_salvage():
    policy = StrictJsonResponseRepairPolicy()
    blocks = [{"type": "text", "text": "pre\n```json\n{\"ok\": true}\n```\npost"}]
    decision = await _call(policy, blocks)
    assert decision.status == "repaired"
    text = decision.output[0]["text"]
    assert json.loads(text) == {"ok": True}
    assert decision.metadata["salvaged_from"] == "fenced_code"


@pytest.mark.asyncio
async def test_bare_json_salvage():
    policy = StrictJsonResponseRepairPolicy()
    blocks = [{"type": "text", "text": "garbage {\"x\": 1, \"y\": [1,2]} trailing"}]
    decision = await _call(policy, blocks)
    assert decision.status == "repaired"
    assert json.loads(decision.output[0]["text"]) == {"x": 1, "y": [1, 2]}
    assert decision.metadata["salvaged_from"] == "bare_json"


@pytest.mark.asyncio
async def test_non_json_fallback_to_basic():
    policy = StrictJsonResponseRepairPolicy(config={"fallback_to_basic": True})
    decision = await _call(policy, [{"type": "text", "text": "no json here at all"}])
    assert decision is not None
    assert decision.status in {"error", "abstain"}


@pytest.mark.asyncio
async def test_non_json_abstain_when_flag_false():
    policy = StrictJsonResponseRepairPolicy(config={"fallback_to_basic": False})
    decision = await _call(policy, [{"type": "text", "text": "no json here at all"}])
    assert decision.status == "abstain"


@pytest.mark.asyncio
async def test_min_text_length_floor():
    policy = StrictJsonResponseRepairPolicy(config={"min_text_length": 200, "fallback_to_basic": False})
    decision = await _call(policy, [{"type": "text", "text": "{\"x\":1}"}])
    assert decision.status == "abstain"


@pytest.mark.asyncio
async def test_bare_fence_without_language_tag_salvages():
    policy = StrictJsonResponseRepairPolicy()
    blocks = [{"type": "text", "text": "pre\n```\n{\"a\": 1}\n```\npost"}]
    decision = await _call(policy, blocks)
    assert decision.status == "repaired"
    assert json.loads(decision.output[0]["text"]) == {"a": 1}
    assert decision.metadata["salvaged_from"] == "fenced_code"


@pytest.mark.asyncio
async def test_mixed_case_json_fence_salvages():
    policy = StrictJsonResponseRepairPolicy()
    blocks = [{"type": "text", "text": "```Json\n{\"b\": 2}\n```"}]
    decision = await _call(policy, blocks)
    assert decision.status == "repaired"
    assert json.loads(decision.output[0]["text"]) == {"b": 2}
    assert decision.metadata["salvaged_from"] == "fenced_code"


def test_registered_as_builtin():
    assert get_builtin_plugin_class("response_repair_policy", "strict_json") is StrictJsonResponseRepairPolicy
