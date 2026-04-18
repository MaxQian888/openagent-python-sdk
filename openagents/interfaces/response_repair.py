"""Response repair contracts for provider/runtime recovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResponseRepairDecision:
    """Structured decision for repairing a bad or empty model response."""

    status: str = "abstain"
    output: str = ""
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
