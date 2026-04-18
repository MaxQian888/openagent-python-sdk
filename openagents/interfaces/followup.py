"""Follow-up resolution contracts for multi-turn semantic recovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FollowupResolution:
    """Structured result for resolving a follow-up question locally."""

    status: str = "abstain"
    output: Any = None
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
