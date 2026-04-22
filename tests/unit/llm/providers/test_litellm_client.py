"""Tests for LiteLLMClient translation layer."""

from __future__ import annotations

import pytest

# Module-level import; litellm is in dev extras. If missing, skip this file.
litellm = pytest.importorskip("litellm")

from openagents.errors.exceptions import ConfigError  # noqa: E402
from openagents.llm.providers import litellm_client as lc_module  # noqa: E402
from openagents.llm.providers.litellm_client import LiteLLMClient  # noqa: E402


def test_init_without_litellm_raises_config_error(monkeypatch):
    monkeypatch.setattr(lc_module, "litellm", None)
    with pytest.raises(ConfigError) as excinfo:
        LiteLLMClient(model="bedrock/foo")
    assert "pip install" in str(excinfo.value)
    assert "litellm" in str(excinfo.value)


def test_init_disables_telemetry_and_callbacks():
    # Dirty the module state first, then verify __init__ cleans it.
    litellm.telemetry = True
    litellm.success_callback = ["sentinel"]
    litellm.failure_callback = ["sentinel"]
    litellm.drop_params = False

    LiteLLMClient(model="gemini/gemini-1.5-pro")

    assert litellm.telemetry is False
    assert litellm.success_callback == []
    assert litellm.failure_callback == []
    assert litellm.drop_params is True


@pytest.mark.parametrize(
    "model,expected",
    [
        ("bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0", "litellm:bedrock"),
        ("vertex_ai/gemini-1.5-pro", "litellm:vertex_ai"),
        ("gemini/gemini-1.5-pro", "litellm:gemini"),
        ("azure/my-deployment", "litellm:azure"),
        ("just-a-model-name", "litellm"),
    ],
)
def test_provider_name_derives_from_model_prefix(model, expected):
    client = LiteLLMClient(model=model)
    assert client.provider_name == expected


@pytest.mark.asyncio
async def test_aclose_is_idempotent():
    client = LiteLLMClient(model="bedrock/foo")
    await client.aclose()
    await client.aclose()  # must not raise
