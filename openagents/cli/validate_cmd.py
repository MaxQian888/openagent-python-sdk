"""Legacy shim — prefer :mod:`openagents.cli.commands.validate`."""

from __future__ import annotations

import argparse

from openagents.cli.commands import validate as _validate


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="openagents validate")
    sub = parser.add_subparsers(dest="command")
    _validate.add_parser(sub)
    args = parser.parse_args(["validate", *argv])
    return _validate.run(args)
