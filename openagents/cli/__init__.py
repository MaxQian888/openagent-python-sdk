"""OpenAgents CLI entry points.

Available subcommands (registered in :mod:`openagents.cli.commands`):

    openagents schema        — dump AppConfig / plugin JSON schemas
    openagents validate      — validate an agent.json without running
    openagents list-plugins  — list registered plugins per seam

Each subcommand lives in its own module under
:mod:`openagents.cli.commands` and exposes two public callables:

* ``add_parser(subparsers)`` — attach argparse tree (sets ``func=run``).
* ``run(args) -> int`` — execute and return a process exit code.

The top-level ``openagents/cli/main.py`` is a thin registry dispatcher; to
add a new subcommand, drop a module into ``commands/`` and append its
display name to ``commands.COMMANDS``.

See ``openagents --help`` or ``python -m openagents --help``. Developer
documentation lives at ``docs/cli.md``.
"""
