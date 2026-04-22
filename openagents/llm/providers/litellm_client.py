"""LiteLLM-backed LLM provider for non-OpenAI protocol backends.

Wraps ``litellm.acompletion`` with the SDK's ``LLMClient`` contract. Covers
AWS Bedrock, Google Vertex AI, Gemini native, Cohere, Azure deployment, and
any other backend LiteLLM supports through ``<prefix>/<model>`` identifiers.

Instantiating this client has process-global side effects: it sets
``litellm.telemetry = False``, clears ``litellm.success_callback`` and
``litellm.failure_callback``, and sets ``litellm.drop_params = True``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from openagents.errors.exceptions import ConfigError
from openagents.llm.base import LLMClient

if TYPE_CHECKING:
    from openagents.config.schema import LLMPricing, LLMRetryOptions

try:
    import litellm  # type: ignore
except ImportError:  # pragma: no cover
    litellm = None

logger = logging.getLogger("openagents.llm.providers.litellm")


_FORWARDABLE_KWARGS: frozenset[str] = frozenset(
    {
        "aws_region_name",
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        "aws_profile_name",
        "vertex_project",
        "vertex_location",
        "vertex_credentials",
        "azure_deployment",
        "api_version",
        "seed",
        "top_p",
        "parallel_tool_calls",
        "response_format",
    }
)


def _derive_provider_name(model: str) -> str:
    if not model or "/" not in model:
        return "litellm"
    prefix = model.split("/", 1)[0].strip()
    return f"litellm:{prefix}" if prefix else "litellm"


class LiteLLMClient(LLMClient):
    """LiteLLM-backed ``LLMClient``. See module docstring."""

    def __init__(
        self,
        *,
        model: str,
        api_base: str | None = None,
        api_key_env: str | None = None,
        timeout_ms: int = 30000,
        default_temperature: float | None = None,
        max_tokens: int = 1024,
        pricing: "LLMPricing | None" = None,
        retry_options: "LLMRetryOptions | None" = None,
        extra_headers: dict[str, str] | None = None,
        extra_kwargs: dict[str, Any] | None = None,
    ) -> None:
        if litellm is None:
            raise ConfigError("provider 'litellm' requires: pip install 'io-openagent-sdk[litellm]'")

        # Process-level telemetry/callbacks lockdown. Idempotent.
        litellm.telemetry = False
        litellm.success_callback = []
        litellm.failure_callback = []
        litellm.drop_params = True

        self.model_id = model or ""
        self.provider_name = _derive_provider_name(self.model_id)

        self._api_base = api_base
        self._api_key_env = api_key_env
        self._timeout_s = max(timeout_ms / 1000.0, 0.1)
        self._default_temperature = default_temperature
        self._max_tokens = max_tokens
        self._pricing = pricing
        self._retry_options = retry_options
        self._extra_headers = dict(extra_headers) if extra_headers else None
        self._extra_kwargs = dict(extra_kwargs) if extra_kwargs else {}

        # Pricing overrides on base class so _compute_cost_for picks them up.
        if pricing is not None:
            self.price_per_mtok_input = pricing.input
            self.price_per_mtok_output = pricing.output
            self.price_per_mtok_cached_read = pricing.cached_read
            self.price_per_mtok_cached_write = pricing.cached_write

    async def aclose(self) -> None:
        session = getattr(litellm, "aclient_session", None) if litellm else None
        if session is None:
            return
        try:
            await session.aclose()
        except Exception:  # pragma: no cover - defensive
            pass
