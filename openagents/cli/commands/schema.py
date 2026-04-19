"""``openagents schema`` — dump AppConfig or per-plugin JSON schemas."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from openagents.config.schema import AppConfig
from openagents.plugins.registry import _BUILTIN_REGISTRY


def _iter_plugins(seam: str | None, name: str | None):
    seams = list(_BUILTIN_REGISTRY.keys()) if seam is None else [seam]
    for s in seams:
        for n, cls in _BUILTIN_REGISTRY.get(s, {}).items():
            if name is None or n == name:
                yield s, n, cls


def _plugin_schema(cls: Any) -> dict[str, Any] | None:
    config_cls = getattr(cls, "Config", None)
    if config_cls is None:
        return None
    try:
        return config_cls.model_json_schema()
    except AttributeError:
        return None


def _dump(data: Any, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(data, indent=2)
    if fmt == "yaml":
        try:
            import yaml  # type: ignore
        except ImportError:
            print(
                "yaml output requires PyYAML; install with: pip install io-openagent-sdk[yaml]",
                file=sys.stderr,
            )
            raise SystemExit(2)
        return yaml.safe_dump(data, sort_keys=False)
    raise SystemExit(f"unknown format: {fmt}")


def add_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "schema",
        help="dump JSON/YAML schema for AppConfig or plugins",
        description="Dump AppConfig or per-plugin JSON schemas.",
    )
    p.add_argument("--plugin", help="dump a single plugin's config schema by name")
    p.add_argument("--seam", help="restrict to a given seam (e.g. context_assembler)")
    p.add_argument("--format", choices=["json", "yaml"], default="json")
    p.add_argument("--out", help="write schema to a file instead of stdout")
    p.set_defaults(func=run)
    return p


def run(args: argparse.Namespace) -> int:
    if args.plugin is None and args.seam is None:
        data: Any = AppConfig.model_json_schema()
    elif args.plugin is not None:
        found_cls: Any = None
        for _s, _n, cls in _iter_plugins(args.seam, args.plugin):
            found_cls = cls
            break
        if found_cls is None:
            print(f"plugin not found: {args.plugin}", file=sys.stderr)
            return 2
        schema = _plugin_schema(found_cls)
        if schema is None:
            print(
                f"plugin '{args.plugin}' does not declare a config schema",
                file=sys.stderr,
            )
            return 2
        data = schema
    else:
        out: dict[str, Any] = {}
        for s, n, cls in _iter_plugins(args.seam, None):
            schema = _plugin_schema(cls)
            if schema is not None:
                out.setdefault(s, {})[n] = schema
        data = out

    text = _dump(data, args.format)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + ("\n" if not text.endswith("\n") else ""))
    else:
        sys.stdout.write(text + ("\n" if not text.endswith("\n") else ""))
    return 0
