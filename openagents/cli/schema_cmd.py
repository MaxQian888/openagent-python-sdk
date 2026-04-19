"""Legacy shim — prefer :mod:`openagents.cli.commands.schema`.

Kept so existing imports (``from openagents.cli.schema_cmd import run``) and
test helpers that pass an ``argv`` list keep working while the new
``add_parser`` / ``run(args)`` shape is the canonical one.
"""

from __future__ import annotations

import argparse

from openagents.cli.commands import schema as _schema

# Re-export internals so callers that imported them directly still resolve.
_iter_plugins = _schema._iter_plugins
_plugin_schema = _schema._plugin_schema
_dump = _schema._dump


def run(argv: list[str]) -> int:
    """Legacy ``argv``-based entry point.

    Builds a single-command parser via :func:`openagents.cli.commands.schema.add_parser`
    and delegates to :func:`openagents.cli.commands.schema.run`.
    """
    parser = argparse.ArgumentParser(prog="openagents schema")
    sub = parser.add_subparsers(dest="command")
    _schema.add_parser(sub)
    args = parser.parse_args(["schema", *argv])
    return _schema.run(args)
