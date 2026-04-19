"""Subcommand modules for the ``openagents`` CLI.

Each module in this package exports exactly two public callables:

* ``add_parser(subparsers) -> argparse.ArgumentParser`` — attach the
  subcommand's argparse tree to the given ``_SubParsersAction``. The
  returned parser is also mutated to set ``func=<module's run>`` so the
  dispatcher can invoke it uniformly.
* ``run(args) -> int`` — execute the subcommand against an already-parsed
  ``argparse.Namespace`` and return a process exit code.

The ordered list below is the dispatch registry the top-level CLI walks.
New subcommands should append their name here and add a matching module
file in this package; no other edit to ``openagents.cli.main`` is needed.
"""

from __future__ import annotations

COMMANDS: list[str] = [
    "schema",
    "validate",
    "list-plugins",
    "version",
    "doctor",
    "config",
    "completion",
    "new",
    "replay",
    "init",
    "run",
    "chat",
    "dev",
]
"""Ordered list of registered subcommand names (``-`` in display names is
translated to ``_`` when locating the module)."""


def module_name_for(command: str) -> str:
    """Return the Python module name backing *command*.

    ``"list-plugins"`` → ``"list_plugins"``.
    """
    return command.replace("-", "_")
