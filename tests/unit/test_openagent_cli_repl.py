from __future__ import annotations

import importlib

repl_module = importlib.import_module("openagent_cli.cli.repl")


def test_print_disables_markup_by_default_for_untrusted_strings(monkeypatch):
    seen: dict[str, object] = {}

    class _FakeConsole:
        def print(self, *args, **kwargs):
            seen["args"] = args
            seen["kwargs"] = kwargs

    monkeypatch.setattr(repl_module, "Console", lambda: _FakeConsole())

    repl_module._print("bad [/TOOL_CALL] text")

    assert seen["args"] == ("bad [/TOOL_CALL] text",)
    assert seen["kwargs"] == {"markup": False}


def test_print_error_uses_plain_error_prefix(monkeypatch):
    seen: dict[str, object] = {}

    class _FakeConsole:
        def print(self, *args, **kwargs):
            seen["args"] = args
            seen["kwargs"] = kwargs

    class _FakeText(str):
        def __new__(cls, text: str, style: str | None = None):
            obj = str.__new__(cls, text)
            obj.style = style
            return obj

        def __add__(self, other):
            return _FakeText(str(self) + str(other))

    monkeypatch.setattr(repl_module, "Console", lambda: _FakeConsole())
    monkeypatch.setattr(repl_module, "Text", _FakeText)

    repl_module._print_error("Agent returned empty response")

    assert "Error: Agent returned empty response" == str(seen["args"][0])
