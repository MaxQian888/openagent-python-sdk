"""Legacy shim — prefer :mod:`openagents.cli.commands.list_plugins`."""

from __future__ import annotations

import argparse

from openagents.cli.commands import list_plugins as _list_plugins

# Re-export internals used by tests and third-party scripts.
_DECORATOR_REGISTRIES = _list_plugins._DECORATOR_REGISTRIES
_collect = _list_plugins._collect
_render_table = _list_plugins._render_table


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="openagents list-plugins")
    sub = parser.add_subparsers(dest="command")
    _list_plugins.add_parser(sub)
    args = parser.parse_args(["list-plugins", *argv])
    return _list_plugins.run(args)
