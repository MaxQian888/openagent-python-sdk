"""``openagents tools`` — inspect and invoke registered tools.

Sub-actions:

* ``list``  — enumerate tools declared for an agent (no LLM, no full Runtime).
* ``call``  — invoke a single tool directly (bypasses LLM; requires full Runtime).

Both sub-actions accept ``--config <path>`` and ``--agent <id>`` (required
for multi-agent configs; auto-selected for single-agent configs).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from openagents.cli._exit import EXIT_OK, EXIT_RUNTIME, EXIT_USAGE, EXIT_VALIDATION
from openagents.config.loader import load_config
from openagents.errors.exceptions import ConfigError


def _select_agent(cfg: Any, requested: str | None) -> tuple[str | None, str | None]:
    if requested:
        for agent in cfg.agents:
            if agent.id == requested:
                return agent.id, None
        return None, f"agent not found: {requested}. Available: {[a.id for a in cfg.agents]}"
    if len(cfg.agents) == 1:
        return cfg.agents[0].id, None
    return None, f"config declares {len(cfg.agents)} agents; pass --agent with one of: {[a.id for a in cfg.agents]}"


def _try_get_tool_meta(tool_ref: Any) -> dict[str, Any]:
    """Attempt to instantiate the tool plugin and extract description + params."""
    try:
        from openagents.plugins.loader import load_plugin

        plugin = load_plugin("tool", tool_ref, required_methods=("invoke",))
        description = getattr(plugin, "description", "") or ""
        schema_fn = getattr(plugin, "schema", None)
        params: Any = None
        if callable(schema_fn):
            try:
                params = schema_fn()
            except Exception:
                pass
        return {"description": str(description), "params": params, "error": None}
    except Exception as exc:
        return {"description": "", "params": None, "error": f"(schema unavailable: {exc})"}


def _list_tools(cfg: Any, agent_id: str, fmt: str) -> int:
    agent = next((a for a in cfg.agents if a.id == agent_id), None)
    if agent is None:
        print(f"agent not found: {agent_id}", file=sys.stderr)
        return EXIT_USAGE

    tools = getattr(agent, "tools", []) or []
    rows: list[dict[str, Any]] = []
    for tool_ref in tools:
        meta = _try_get_tool_meta(tool_ref)
        rows.append(
            {
                "id": str(getattr(tool_ref, "id", "") or ""),
                "type": str(getattr(tool_ref, "type", "") or ""),
                "description": meta["description"],
                "params_schema": meta["params"],
                "error": meta["error"],
            }
        )

    if fmt == "json":
        sys.stdout.write(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
        return EXIT_OK

    if not rows:
        print(f"(no tools registered for agent {agent_id})")
        return EXIT_OK

    # text: aligned columns
    id_w = max((len(r["id"]) for r in rows), default=4)
    type_w = max((len(r["type"]) for r in rows), default=4)
    for r in rows:
        note = r["error"] or r["description"] or ""
        print(f"  {r['id']:<{id_w}}  {r['type']:<{type_w}}  {note[:80]}")
    return EXIT_OK


def _call_tool(cfg: Any, path: str, agent_id: str, tool_id: str, json_args_str: str, fmt: str) -> int:
    agent = next((a for a in cfg.agents if a.id == agent_id), None)
    if agent is None:
        print(f"agent not found: {agent_id}", file=sys.stderr)
        return EXIT_USAGE

    tools = getattr(agent, "tools", []) or []
    tool_ids = [str(getattr(t, "id", "")) for t in tools]
    if tool_id not in tool_ids:
        print(f"tool not found: {tool_id!r}. Available: {tool_ids}", file=sys.stderr)
        return EXIT_USAGE

    try:
        params = json.loads(json_args_str or "{}")
    except json.JSONDecodeError as exc:
        print(f"JSON parse error in args: {exc}", file=sys.stderr)
        return EXIT_USAGE

    from openagents.runtime.runtime import Runtime

    try:
        runtime = Runtime.from_config(path)
    except ConfigError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_VALIDATION

    async def _execute() -> Any:
        tool_executor = getattr(runtime, "tool_executor", None)
        if tool_executor is None:
            # Try to get it from the agent's plugin bundle
            bundle = getattr(runtime, "_agent_plugins", {}).get(agent_id)
            if bundle is not None:
                tool_executor = getattr(bundle, "tool_executor", None)
        if tool_executor is None:
            raise RuntimeError(
                "tool_executor not available on runtime; ensure the agent config includes a tool_executor seam"
            )

        # Find the tool plugin instance — look in the agent plugin bundle
        tool_plugin = None
        bundle = getattr(runtime, "_agent_plugins", {}).get(agent_id)
        if bundle is not None:
            tool_plugins = getattr(bundle, "tools", None) or {}
            tool_plugin = tool_plugins.get(tool_id)

        if tool_plugin is None:
            # Fall back: load tool plugin directly from config ref
            tool_ref = next((t for t in tools if str(getattr(t, "id", "")) == tool_id), None)
            if tool_ref is not None:
                from openagents.plugins.loader import load_plugin

                tool_plugin = load_plugin("tool", tool_ref, required_methods=("invoke",))

        if tool_plugin is None:
            raise RuntimeError(f"could not resolve tool plugin for id {tool_id!r}")

        from openagents.interfaces.tool import ToolExecutionRequest

        req = ToolExecutionRequest(tool_id=tool_id, tool=tool_plugin, params=params)
        return await tool_executor.execute(req)

    try:
        result = asyncio.run(_execute())
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        try:
            asyncio.run(runtime.close())
        except Exception:  # pragma: no cover
            pass
        return EXIT_RUNTIME

    try:
        asyncio.run(runtime.close())
    except Exception:  # pragma: no cover
        pass

    data = getattr(result, "data", result)
    if fmt == "json":
        try:
            sys.stdout.write(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n")
        except Exception:
            sys.stdout.write(repr(data) + "\n")
        return EXIT_OK

    # text: try _render_value, fallback to repr
    try:
        from openagents.cli._rich import get_console
        from openagents.observability._rich import _render_value

        console = get_console("stdout")
        console.print(_render_value(data))
    except Exception:
        print(data)
    return EXIT_OK


def add_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "tools",
        help="inspect and invoke registered tools",
        description="List tools registered for an agent or invoke one directly.",
    )
    nested = p.add_subparsers(dest="tools_action")

    # tools list
    lst = nested.add_parser("list", help="list tools registered for an agent")
    lst.add_argument("--config", required=True, help="path to an agent.json")
    lst.add_argument("--agent", dest="agent_id", default=None, help="agent id (required for multi-agent configs)")
    lst.add_argument("--format", choices=["text", "json"], default="text")
    lst.set_defaults(func=run)

    # tools call
    call = nested.add_parser("call", help="invoke a tool directly without LLM")
    call.add_argument("--config", required=True, help="path to an agent.json")
    call.add_argument("--agent", dest="agent_id", default=None, help="agent id (required for multi-agent configs)")
    call.add_argument("tool_id", help="id of the tool to invoke")
    call.add_argument("json_args", nargs="?", default="{}", help="JSON object of tool parameters (default: {})")
    call.add_argument("--format", choices=["text", "json"], default="text")
    call.set_defaults(func=run)

    p.set_defaults(func=run)
    return p


def run(args: argparse.Namespace) -> int:
    action = getattr(args, "tools_action", None)
    if action is None:
        print("usage: openagents tools <list|call> --config <path> [options]", file=sys.stderr)
        return EXIT_USAGE

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_VALIDATION

    agent_id, err = _select_agent(cfg, args.agent_id)
    if err is not None:
        print(err, file=sys.stderr)
        return EXIT_USAGE

    if action == "list":
        return _list_tools(cfg, agent_id or "", args.format)

    if action == "call":
        return _call_tool(
            cfg,
            args.config,
            agent_id or "",
            args.tool_id,
            getattr(args, "json_args", "{}") or "{}",
            args.format,
        )

    print(f"unknown tools action: {action}", file=sys.stderr)  # pragma: no cover
    return EXIT_USAGE
