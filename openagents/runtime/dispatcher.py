"""Capability-based dispatch helpers."""

from __future__ import annotations

from typing import Any

from openagents.interfaces.capabilities import normalize_capabilities


def supports(plugin: Any, capability: str) -> bool:
    capabilities = normalize_capabilities(getattr(plugin, "capabilities", set()))
    return capability in capabilities


