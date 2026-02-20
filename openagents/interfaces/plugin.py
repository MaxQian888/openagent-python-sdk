"""Base plugin contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .capabilities import normalize_capabilities


@dataclass
class BasePlugin:
    """Convenience base plugin with config and capability helpers."""

    config: dict[str, Any] = field(default_factory=dict)
    capabilities: set[str] = field(default_factory=set)

    def capability_set(self) -> set[str]:
        return normalize_capabilities(self.capabilities)

    def supports(self, capability: str) -> bool:
        return capability in self.capability_set()

    @classmethod
    def from_capabilities(
        cls,
        *,
        config: dict[str, Any] | None = None,
        capabilities: Iterable[str] | None = None,
    ) -> "BasePlugin":
        return cls(
            config=config or {},
            capabilities=normalize_capabilities(capabilities),
        )

