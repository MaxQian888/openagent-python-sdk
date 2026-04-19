"""Stable exit-code constants for the ``openagents`` CLI.

Every subcommand SHOULD return one of these values instead of a literal.
Tests assert on these numbers rather than on stderr substrings so the
error surface can evolve without breaking the exit-code contract.
"""

from __future__ import annotations

EXIT_OK = 0
"""Command succeeded."""

EXIT_USAGE = 1
"""User error: missing required arg, unknown subcommand, file not found,
or an ambiguous selection (e.g. multi-agent config without ``--agent``)."""

EXIT_VALIDATION = 2
"""Validation failure: config did not pass ``load_config``, strict-mode
unresolved plugin ``type``, invalid JSON/YAML."""

EXIT_RUNTIME = 3
"""Runtime failure: LLM call raised, plugin raised during setup/execute/
writeback, or persistence failed mid-session."""

__all__ = ["EXIT_OK", "EXIT_USAGE", "EXIT_VALIDATION", "EXIT_RUNTIME"]
