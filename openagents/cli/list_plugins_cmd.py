"""`openagents list-plugins` — enumerate registered plugins per seam."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from openagents.decorators import (
    _CONTEXT_ASSEMBLER_REGISTRY,
    _EVENT_REGISTRY,
    _MEMORY_REGISTRY,
    _PATTERN_REGISTRY,
    _RUNTIME_REGISTRY,
    _SESSION_REGISTRY,
    _TOOL_EXECUTOR_REGISTRY,
    _TOOL_REGISTRY,
)
from openagents.plugins.registry import _BUILTIN_REGISTRY

_DECORATOR_REGISTRIES: dict[str, dict[str, Any]] = {
    "memory": _MEMORY_REGISTRY,
    "pattern": _PATTERN_REGISTRY,
    "runtime": _RUNTIME_REGISTRY,
    "session": _SESSION_REGISTRY,
    "events": _EVENT_REGISTRY,
    "tool_executor": _TOOL_EXECUTOR_REGISTRY,
    "context_assembler": _CONTEXT_ASSEMBLER_REGISTRY,
    "tool": _TOOL_REGISTRY,
}


def _collect(seam_filter: str | None, source_filter: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    if source_filter in ("builtin", "all"):
        for seam, plugins in _BUILTIN_REGISTRY.items():
            if seam_filter and seam != seam_filter:
                continue
            for name, cls in plugins.items():
                rows.append(
                    {
                        "seam": seam,
                        "name": name,
                        "source": "builtin",
                        "impl_path": f"{cls.__module__}.{cls.__name__}",
                        "has_config_schema": getattr(cls, "Config", None) is not None,
                    }
                )
    if source_filter in ("decorator", "all"):
        for seam, registry in _DECORATOR_REGISTRIES.items():
            if seam_filter and seam != seam_filter:
                continue
            for name, cls in registry.items():
                # Decorator registry may store classes or factory callables.
                impl_path = f"{getattr(cls, '__module__', '')}.{getattr(cls, '__name__', str(cls))}"
                rows.append(
                    {
                        "seam": seam,
                        "name": name,
                        "source": "decorator",
                        "impl_path": impl_path,
                        "has_config_schema": getattr(cls, "Config", None) is not None,
                    }
                )

    rows.sort(key=lambda r: (r["seam"], r["name"], r["source"]))
    return rows


def _render_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(no plugins registered)"
    headers = ("seam", "name", "source", "has_config_schema")
    widths = {h: len(h) for h in headers}
    for r in rows:
        for h in headers:
            widths[h] = max(widths[h], len(str(r[h])))
    line = "  ".join(h.ljust(widths[h]) for h in headers)
    out = [line, "  ".join("-" * widths[h] for h in headers)]
    for r in rows:
        out.append("  ".join(str(r[h]).ljust(widths[h]) for h in headers))
    return "\n".join(out)


def run(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="openagents list-plugins")
    p.add_argument("--seam", help="filter by seam name")
    p.add_argument(
        "--source",
        choices=["builtin", "decorator", "all"],
        default="all",
    )
    p.add_argument("--format", choices=["table", "json"], default="table")
    args = p.parse_args(argv)

    rows = _collect(args.seam, args.source)

    if args.format == "json":
        sys.stdout.write(json.dumps(rows, indent=2) + "\n")
    else:
        sys.stdout.write(_render_table(rows) + "\n")
    return 0
