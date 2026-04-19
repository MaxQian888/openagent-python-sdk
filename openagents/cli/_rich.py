"""Rich-or-plaintext console factory shared by every ``openagents`` CLI command.

``get_console(stream)`` returns an object with the minimal API the CLI
commands use (``print``, ``rule``, ``out``). When Rich is installed, it
is a :class:`rich.console.Console`; otherwise it's a tiny
:class:`_PlainConsole` stub that writes to the same stream without
formatting so commands don't have to branch on availability.
"""

from __future__ import annotations

import importlib.util
import sys
from typing import Any, Literal, TextIO


def _rich_available() -> bool:
    return importlib.util.find_spec("rich") is not None


class _PlainConsole:
    """Plain-text stand-in for :class:`rich.console.Console`.

    Supports the tiny subset of the Rich API the CLI uses. Any Rich
    renderables passed to :meth:`print` are coerced to ``str`` so calling
    code doesn't have to branch on whether Rich is installed.
    """

    def __init__(self, file: TextIO):
        self._file = file

    def print(self, *objs: Any, **_: Any) -> None:
        self._file.write(" ".join(_coerce(o) for o in objs) + "\n")

    def rule(self, title: str = "", **_: Any) -> None:
        bar = "-" * 60
        label = f" {title} " if title else ""
        self._file.write(f"{bar}{label}{bar}\n".rstrip() + "\n")

    @property
    def file(self) -> TextIO:
        return self._file


def _coerce(obj: Any) -> str:
    """Best-effort string conversion that keeps Rich renderables readable."""
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    plain = getattr(obj, "plain", None)
    if isinstance(plain, str):
        return plain
    text = getattr(obj, "renderable", None)
    if isinstance(text, str):
        return text
    return str(obj)


def get_console(stream: Literal["stdout", "stderr"] = "stderr") -> Any:
    """Return a Rich Console when available, else a plain-text stub.

    *stream* selects whether output goes to stdout or stderr (CLI
    convention: diagnostic chatter goes to stderr so piping to ``jq``
    stays clean).
    """
    target: TextIO = sys.stderr if stream == "stderr" else sys.stdout
    if not _rich_available():
        return _PlainConsole(target)
    from rich.console import Console

    return Console(file=target, force_terminal=True, highlight=False)
