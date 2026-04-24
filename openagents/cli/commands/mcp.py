"""``openagents mcp`` — inspect and probe MCP servers.

Sub-actions:

* ``list``  — show MCP servers declared in an agent.json (no network).
* ``ping``  — test connectivity to an MCP server and report latency.
* ``tools`` — list tools exposed by an MCP server.

``list`` does not require the ``mcp`` optional extra. ``ping`` and
``tools`` require it and will print an install hint and exit ``1``
when the package is absent.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from typing import Any

from openagents.cli._exit import EXIT_OK, EXIT_RUNTIME, EXIT_USAGE, EXIT_VALIDATION
from openagents.cli._fallback import require_or_hint
from openagents.config.loader import load_config
from openagents.errors.exceptions import ConfigError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _select_agent(cfg: Any, requested: str | None) -> tuple[str | None, str | None]:
    if requested:
        for agent in cfg.agents:
            if agent.id == requested:
                return agent.id, None
        return None, f"agent not found: {requested}. Available: {[a.id for a in cfg.agents]}"
    if len(cfg.agents) == 1:
        return cfg.agents[0].id, None
    return None, f"config declares {len(cfg.agents)} agents; pass --agent with one of: {[a.id for a in cfg.agents]}"


def _is_mcp_tool(tool_ref: Any) -> bool:
    """Return True if this ToolRef points to an MCP tool."""
    type_str = str(getattr(tool_ref, "type", "") or "")
    if type_str == "mcp":
        return True
    cfg = getattr(tool_ref, "config", None) or {}
    if isinstance(cfg, dict):
        return "url" in cfg or "mcp_url" in cfg or "command" in cfg
    return False


def _mcp_server_info(tool_ref: Any) -> dict[str, Any]:
    """Extract connection info from a ToolRef."""
    cfg = getattr(tool_ref, "config", None) or {}
    if not isinstance(cfg, dict):
        try:
            cfg = dict(cfg)
        except Exception:
            cfg = {}
    nested_url: str | None = None
    if isinstance(cfg.get("server"), dict):
        nested_url = cfg["server"].get("url")
    url = cfg.get("url") or cfg.get("mcp_url") or nested_url
    return {
        "id": str(getattr(tool_ref, "id", "") or ""),
        "type": str(getattr(tool_ref, "type", "") or ""),
        "url": url,
        "command": cfg.get("command"),
        "transport": "sse" if url else ("stdio" if cfg.get("command") else "unknown"),
    }


def _resolve_url(
    cfg: Any | None,
    agent_id: str | None,
    server_name: str | None,
    direct_url: str | None,
) -> tuple[str | None, str | None]:
    """Return ``(url, error_message)``."""
    if direct_url:
        return direct_url, None
    if cfg is None or agent_id is None:
        return None, "specify a URL directly or use --config to resolve from agent.json"

    agent = next((a for a in cfg.agents if a.id == agent_id), None)
    if agent is None:
        return None, f"agent not found: {agent_id}"

    mcp_tools = [t for t in (getattr(agent, "tools", []) or []) if _is_mcp_tool(t)]
    if not mcp_tools:
        return None, f"no MCP tools configured for agent {agent_id}"

    if server_name:
        match = next((t for t in mcp_tools if str(getattr(t, "id", "")) == server_name), None)
        if match is None:
            ids = [str(getattr(t, "id", "")) for t in mcp_tools]
            return None, f"MCP server not found: {server_name!r}. Available: {ids}"
        info = _mcp_server_info(match)
    elif len(mcp_tools) == 1:
        info = _mcp_server_info(mcp_tools[0])
    else:
        ids = [str(getattr(t, "id", "")) for t in mcp_tools]
        return None, f"multiple MCP servers configured; use --server with one of: {ids}"

    url = info.get("url")
    if not url:
        return None, "MCP server has no URL (command-based stdio servers are not supported by 'ping'/'tools')"
    return url, None


async def _mcp_connect_list_tools(url: str, timeout: float) -> list[dict[str, Any]]:
    """Connect to an MCP server via SSE/HTTP and return the tool list."""
    from mcp import ClientSession  # type: ignore[import-untyped]
    from mcp.client.sse import sse_client  # type: ignore[import-untyped]

    async with asyncio.timeout(timeout):
        async with sse_client(url=url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                response = await session.list_tools()
                tools = response.tools if hasattr(response, "tools") else []
                return [
                    {
                        "name": getattr(t, "name", str(t)),
                        "description": getattr(t, "description", ""),
                        "inputSchema": getattr(t, "inputSchema", None),
                    }
                    for t in tools
                ]


# ---------------------------------------------------------------------------
# Sub-action implementations
# ---------------------------------------------------------------------------


def _mcp_list(cfg: Any, agent_id: str, fmt: str) -> int:
    agent = next((a for a in cfg.agents if a.id == agent_id), None)
    if agent is None:
        print(f"agent not found: {agent_id}", file=sys.stderr)
        return EXIT_USAGE

    mcp_tools = [t for t in (getattr(agent, "tools", []) or []) if _is_mcp_tool(t)]
    if not mcp_tools:
        print(f"(no MCP servers configured for agent {agent_id})")
        return EXIT_OK

    rows = [_mcp_server_info(t) for t in mcp_tools]
    if fmt == "json":
        sys.stdout.write(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
        return EXIT_OK

    for r in rows:
        url_or_cmd = r.get("url") or r.get("command") or "(unknown)"
        print(f"  {r['id']:<20} {r['transport']:<6} {url_or_cmd}")
    return EXIT_OK


def _run_ping(url: str, timeout: float) -> int:
    if require_or_hint("mcp") is None:
        return EXIT_USAGE  # hint already printed by require_or_hint
    t0 = time.monotonic()
    try:
        tools = asyncio.run(_mcp_connect_list_tools(url, timeout))
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        print(f"✓ {url}  latency={elapsed_ms}ms  tools={len(tools)}")
        return EXIT_OK
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        print(f"✗ {url}  {type(exc).__name__}: {exc}")
        return EXIT_RUNTIME


def _run_tools(url: str, timeout: float, fmt: str) -> int:
    if require_or_hint("mcp") is None:
        return EXIT_USAGE
    try:
        tools = asyncio.run(_mcp_connect_list_tools(url, timeout))
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_RUNTIME

    if not tools:
        print("(no tools exposed by this server)")
        return EXIT_OK

    if fmt == "json":
        sys.stdout.write(json.dumps(tools, indent=2, ensure_ascii=False) + "\n")
        return EXIT_OK

    for t in tools:
        name = t.get("name", "?")
        desc = t.get("description") or ""
        schema = t.get("inputSchema") or {}
        props = list(schema.get("properties", {}).keys()) if isinstance(schema, dict) else []
        params_str = f"({', '.join(props)})" if props else "(no params)"
        print(f"  {name}")
        if desc:
            print(f"    {desc[:100]}")
        print(f"    params: {params_str}")
    return EXIT_OK


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def add_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "mcp",
        help="inspect and probe MCP servers",
        description="List, ping, or list tools from MCP servers configured in an agent.json.",
    )
    nested = p.add_subparsers(dest="mcp_action")

    # mcp list
    lst = nested.add_parser("list", help="list MCP servers declared in an agent.json")
    lst.add_argument("--config", required=True, help="path to an agent.json")
    lst.add_argument("--agent", dest="agent_id", default=None)
    lst.add_argument("--format", choices=["text", "json"], default="text")
    lst.set_defaults(func=run)

    # mcp ping
    ping = nested.add_parser("ping", help="test connectivity to an MCP server")
    ping.add_argument("url", nargs="?", default=None, help="MCP server URL (alternative to --config)")
    ping.add_argument("--config", default=None, help="path to an agent.json")
    ping.add_argument("--agent", dest="agent_id", default=None)
    ping.add_argument("--server", dest="server_name", default=None, help="MCP server id in the config")
    ping.add_argument("--timeout", type=float, default=10.0, metavar="SECONDS")
    ping.set_defaults(func=run)

    # mcp tools
    tools = nested.add_parser("tools", help="list tools exposed by an MCP server")
    tools.add_argument("url", nargs="?", default=None, help="MCP server URL (alternative to --config)")
    tools.add_argument("--config", default=None, help="path to an agent.json")
    tools.add_argument("--agent", dest="agent_id", default=None)
    tools.add_argument("--server", dest="server_name", default=None)
    tools.add_argument("--timeout", type=float, default=10.0, metavar="SECONDS")
    tools.add_argument("--format", choices=["text", "json"], default="text")
    tools.set_defaults(func=run)

    p.set_defaults(func=run)
    return p


def run(args: argparse.Namespace) -> int:
    action = getattr(args, "mcp_action", None)
    if action is None:
        print("usage: openagents mcp <list|ping|tools> [options]", file=sys.stderr)
        return EXIT_USAGE

    if action == "list":
        config_path = getattr(args, "config", None)
        if not config_path:
            print("--config is required for 'mcp list'", file=sys.stderr)
            return EXIT_USAGE
        try:
            cfg = load_config(config_path)
        except ConfigError as exc:
            print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
            return EXIT_VALIDATION
        agent_id, err = _select_agent(cfg, getattr(args, "agent_id", None))
        if err:
            print(err, file=sys.stderr)
            return EXIT_USAGE
        return _mcp_list(cfg, agent_id or "", getattr(args, "format", "text"))

    # ping / tools: resolve URL
    config_path = getattr(args, "config", None)
    cfg: Any | None = None
    agent_id: str | None = None
    if config_path:
        try:
            cfg = load_config(config_path)
        except ConfigError as exc:
            print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
            return EXIT_VALIDATION
        agent_id, err = _select_agent(cfg, getattr(args, "agent_id", None))
        if err:
            print(err, file=sys.stderr)
            return EXIT_USAGE

    url, url_err = _resolve_url(
        cfg,
        agent_id,
        getattr(args, "server_name", None),
        getattr(args, "url", None),
    )
    if url_err:
        print(url_err, file=sys.stderr)
        return EXIT_USAGE

    timeout = getattr(args, "timeout", 10.0)

    if action == "ping":
        return _run_ping(url or "", timeout)

    if action == "tools":
        return _run_tools(url or "", timeout, getattr(args, "format", "text"))

    print(f"unknown mcp action: {action}", file=sys.stderr)  # pragma: no cover
    return EXIT_USAGE
