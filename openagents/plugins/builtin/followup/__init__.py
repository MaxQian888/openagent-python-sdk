"""Builtin follow-up resolver implementations."""

from .basic import BasicFollowupResolver
from .rule_based import RuleBasedFollowupResolver

__all__ = ["BasicFollowupResolver", "RuleBasedFollowupResolver"]
