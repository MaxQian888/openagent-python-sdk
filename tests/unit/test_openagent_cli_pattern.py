from __future__ import annotations

import os

from openagent_cli.plugins.patterns.claude_code_pattern import ClaudeCodePattern


def test_build_llm_messages_preserves_structured_content_blocks():
    pattern = ClaudeCodePattern()

    messages = [
        {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_1", "name": "read", "input": {"path": "README.md"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "README contents"}]},
    ]

    llm_messages = pattern._build_llm_messages(messages)

    assert llm_messages == messages


def test_build_system_prompt_includes_working_directory_and_tool_guidance(monkeypatch):
    pattern = ClaudeCodePattern()

    class _Ctx:
        system_prompt_fragments = []

    pattern.context = _Ctx()
    monkeypatch.chdir(r"C:\code\openagent\openagent-py-sdk\openagent_cli")

    prompt = pattern._build_system_prompt()

    assert "Current working directory:" in prompt
    assert os.getcwd() in prompt
    assert "Prefer built-in file tools" in prompt
