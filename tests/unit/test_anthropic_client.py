from openagents.llm.providers.anthropic import AnthropicClient


def test_messages_endpoint_adds_v1_when_base_is_root():
    client = AnthropicClient(api_base='https://api.anthropic.com', model='claude-test')
    assert client._messages_endpoint() == 'https://api.anthropic.com/v1/messages'


def test_messages_endpoint_preserves_existing_v1_prefix():
    client = AnthropicClient(api_base='https://api.minimaxi.com/anthropic/v1', model='MiniMax-M2.5')
    assert client._messages_endpoint() == 'https://api.minimaxi.com/anthropic/v1/messages'


def test_build_payload_uses_x_api_key_without_authorization_header(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    client = AnthropicClient(api_base="https://api.minimaxi.com/anthropic", model="MiniMax-M2.7")

    _, headers = client._build_payload(
        messages=[{"role": "user", "content": "hello"}],
        stream=True,
    )

    assert headers["x-api-key"] == "test-key"
    assert "Authorization" not in headers
