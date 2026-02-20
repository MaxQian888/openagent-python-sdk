"""Capability constants and helpers."""

from __future__ import annotations

from typing import Iterable

MEMORY_INJECT = "memory.inject"
MEMORY_WRITEBACK = "memory.writeback"
PATTERN_REACT = "pattern.react"
TOOL_INVOKE = "tool.invoke"

KNOWN_CAPABILITIES = {
    MEMORY_INJECT,
    MEMORY_WRITEBACK,
    PATTERN_REACT,
    TOOL_INVOKE,
}


def normalize_capabilities(values: Iterable[str] | None) -> set[str]:
    if values is None:
        return set()
    normalized: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        item = value.strip()
        if item:
            normalized.add(item)
    return normalized

