"""``openagents version`` — report SDK + environment versions.

Default output is a single line suitable for bug reports:

    openagents 0.4.0 python 3.12.3 extras [rich, yaml]

``--verbose`` produces a Rich table (or plain-text fallback) that also
lists per-seam builtin plugin counts. ``--format json`` emits a stable
JSON object ``{sdk, python, extras, builtin_plugin_counts}`` for
programmatic consumers.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import platform
import sys
from typing import Any

from openagents.cli._exit import EXIT_OK
from openagents.plugins.registry import _BUILTIN_REGISTRY

_DIST_NAME = "io-openagent-sdk"

_KNOWN_EXTRAS = (
    "rich",
    "questionary",
    "yaml",
    "watchdog",
    "anthropic",
    "mcp",
    "mem0ai",
    "tiktoken",
    "aiosqlite",
    "opentelemetry",
)


def _sdk_version() -> str:
    try:
        return importlib.metadata.version(_DIST_NAME)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _python_version() -> str:
    return platform.python_version()


def _detected_extras() -> list[str]:
    return [name for name in _KNOWN_EXTRAS if importlib.util.find_spec(name) is not None]


def _builtin_plugin_counts() -> dict[str, int]:
    return {seam: len(plugins) for seam, plugins in _BUILTIN_REGISTRY.items()}


def _summary_dict() -> dict[str, Any]:
    return {
        "sdk": _sdk_version(),
        "python": _python_version(),
        "extras": _detected_extras(),
        "builtin_plugin_counts": _builtin_plugin_counts(),
    }


def _render_plain(data: dict[str, Any], *, verbose: bool) -> str:
    if not verbose:
        extras = ", ".join(data["extras"]) or "(none)"
        return f"openagents {data['sdk']} python {data['python']} extras [{extras}]"
    lines = [
        f"openagents   {data['sdk']}",
        f"python       {data['python']}",
        f"extras       {', '.join(data['extras']) or '(none)'}",
        "builtin plugin counts:",
    ]
    for seam, count in sorted(data["builtin_plugin_counts"].items()):
        lines.append(f"  {seam:<24}{count}")
    return "\n".join(lines)


def _render_rich(data: dict[str, Any]) -> Any | None:
    if importlib.util.find_spec("rich") is None:
        return None
    from rich.console import Console
    from rich.table import Table

    console = Console(file=sys.stdout, force_terminal=False, highlight=False)
    table = Table(show_header=True, header_style="bold", title="openagents")
    table.add_column("field", style="cyan", no_wrap=True)
    table.add_column("value")
    table.add_row("sdk", data["sdk"])
    table.add_row("python", data["python"])
    table.add_row("extras", ", ".join(data["extras"]) or "(none)")
    for seam, count in sorted(data["builtin_plugin_counts"].items()):
        table.add_row(f"plugins/{seam}", str(count))
    console.print(table)
    return True


def add_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "version",
        help="print SDK, Python, and extras versions",
        description="Report SDK version, Python version, detected optional extras, and builtin plugin counts.",
    )
    p.add_argument("--verbose", action="store_true", help="include per-seam plugin counts")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.set_defaults(func=run)
    return p


def run(args: argparse.Namespace) -> int:
    data = _summary_dict()
    if args.format == "json":
        sys.stdout.write(json.dumps(data, indent=2) + "\n")
        return EXIT_OK
    if args.verbose and _render_rich(data) is not None:
        return EXIT_OK
    sys.stdout.write(_render_plain(data, verbose=args.verbose) + "\n")
    return EXIT_OK
