from openagents.llm.providers.anthropic import AnthropicClient


def test_messages_endpoint_adds_v1_when_base_is_root():
    client = AnthropicClient(api_base='https://api.anthropic.com', model='claude-test')
    assert client._messages_endpoint() == 'https://api.anthropic.com/v1/messages'


def test_messages_endpoint_preserves_existing_v1_prefix():
    client = AnthropicClient(api_base='https://api.minimaxi.com/anthropic/v1', model='MiniMax-M2.5')
    assert client._messages_endpoint() == 'https://api.minimaxi.com/anthropic/v1/messages'