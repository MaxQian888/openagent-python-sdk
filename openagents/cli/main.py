"""Argparse-based CLI dispatcher for ``openagents``."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openagents",
        description="OpenAgents SDK command-line utilities.",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("schema", help="dump JSON/YAML schema for AppConfig or plugins")
    sub.add_parser("validate", help="validate an agent.json without running")
    sub.add_parser("list-plugins", help="list registered plugins per seam")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args, extra = parser.parse_known_args(argv)
    if args.command is None:
        parser.print_help(sys.stderr)
        return 1
    if args.command == "schema":
        from openagents.cli.schema_cmd import run as schema_run
        return schema_run(extra)
    if args.command == "validate":
        from openagents.cli.validate_cmd import run as validate_run
        return validate_run(extra)
    if args.command == "list-plugins":
        from openagents.cli.list_plugins_cmd import run as list_run
        return list_run(extra)
    print(f"unknown subcommand: {args.command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
