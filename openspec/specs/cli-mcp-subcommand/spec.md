## ADDED Requirements

### Requirement: `openagents mcp` is a registered top-level subcommand

`openagents/cli/commands/mcp.py` SHALL be added to the `COMMANDS` registry in `openagents/cli/commands/__init__.py`. The command SHALL use nested subparsers for its `list`, `ping`, and `tools` sub-actions. Invoking `openagents mcp` without a sub-action SHALL print usage help to stderr and exit `1`.

`list` does not require the `mcp` optional extra. `ping` and `tools` require it; if absent, they SHALL use `require_or_hint("mcp")` to print an install hint and exit `1`.

#### Scenario: `openagents mcp --help` shows all sub-actions

- **WHEN** `openagents mcp --help` is invoked
- **THEN** help text includes `list`, `ping`, and `tools` as sub-actions

#### Scenario: `openagents mcp` without sub-action exits 1

- **WHEN** `openagents mcp` is invoked without a sub-action
- **THEN** the process exits `1` and stderr includes usage guidance

---

### Requirement: `openagents mcp list` enumerates MCP servers declared in the config

`openagents mcp list --config <path> [--agent <id>] [--format text|json]` SHALL:
1. Load config and select agent.
2. Find tool refs where `type` is `"mcp"` or the ref contains an `mcp_url` / `mcp_server` field (matching the shape used by the `mcp_tool` builtin plugin).
3. For each MCP server, display: server name/id, URL, transport type (if known).
4. Exit `0` even if no MCP tools are configured (print `(no MCP servers configured for agent <id>)`).
5. Exit `2` on `ConfigError`.

This command makes no network connections.

#### Scenario: Lists MCP servers from config

- **WHEN** `openagents mcp list --config agent-with-mcp.json` is invoked
- **THEN** output lists the MCP server URLs and exit code is `0`

#### Scenario: No MCP tools configured

- **WHEN** the agent has no MCP tool refs
- **THEN** output contains `(no MCP servers configured` and exit code is `0`

#### Scenario: JSON format is parseable

- **WHEN** `openagents mcp list --config agent.json --format json` is invoked
- **THEN** stdout is a valid JSON array

---

### Requirement: `openagents mcp ping` tests connectivity to an MCP server

`openagents mcp ping (--config <path> [--agent <id>] [--server <name>] | <url>) [--timeout N]` SHALL:
1. Resolve the target URL either from config (by server name or index; if a single MCP server exists, auto-select) or from a direct URL positional argument.
2. Connect to the MCP server (using the `mcp` library's client) and call `list_tools()`.
3. Measure wall-clock latency from connection open to `list_tools()` response.
4. On success: print `✓ <url>  latency={N}ms  tools={M}` to stdout; exit `0`.
5. On failure (connection refused, timeout, protocol error): print `✗ <url>  <ErrorType>: <message>` to stdout; exit `3`.

`--timeout N` (float seconds, default `10.0`) sets a hard connection + response timeout.

If the `mcp` extra is not installed, the command SHALL exit `1` via `require_or_hint`.

#### Scenario: Successful ping prints latency and tool count

- **WHEN** `openagents mcp ping http://localhost:3000/mcp` is invoked against a running MCP server
- **THEN** stdout contains `✓` with a latency annotation and tool count; exit code is `0`

#### Scenario: Unreachable server exits 3

- **WHEN** the MCP server URL is unreachable (connection refused)
- **THEN** stdout contains `✗` with the error reason; exit code is `3`

#### Scenario: Timeout exits 3

- **WHEN** `--timeout 0.001` is set and the server does not respond within 1 ms
- **THEN** stdout contains `✗` with `TimeoutError` and exit code is `3`

#### Scenario: `mcp` extra missing exits 1 with install hint

- **WHEN** `openagents mcp ping <url>` is invoked without the `mcp` package installed
- **THEN** the process exits `1` and stderr contains an install hint mentioning `mcp`

#### Scenario: URL from config when single MCP server

- **WHEN** `openagents mcp ping --config agent.json` is invoked and the config has exactly one MCP tool
- **THEN** that server's URL is used without requiring `--server`

---

### Requirement: `openagents mcp tools` lists tools exposed by an MCP server

`openagents mcp tools (--config <path> [--agent <id>] [--server <name>] | <url>) [--format text|json] [--timeout N]` SHALL:
1. Connect to the MCP server (same resolution logic as `mcp ping`).
2. Call `list_tools()` and collect the full tool list.
3. For each tool: display name, description, and a summary of `inputSchema` (parameter names + types).
4. `text` format (default): one tool per block with name, description, params.
5. `json` format: the raw `list_tools()` response as JSON.
6. Exit `0` on success; exit `3` on connection/protocol failure; exit `1` on missing `mcp` extra.

#### Scenario: Prints all tool names and descriptions

- **WHEN** `openagents mcp tools http://localhost:3000/mcp` is invoked against a running server with 3 tools
- **THEN** stdout contains 3 tool entries with names and descriptions

#### Scenario: JSON format returns raw server response

- **WHEN** `openagents mcp tools <url> --format json` is invoked
- **THEN** stdout is valid JSON that can be parsed by `json.loads`

#### Scenario: No tools on server prints informative message

- **WHEN** the MCP server returns an empty tools list
- **THEN** stdout contains `(no tools exposed by this server)` and exit code is `0`

#### Scenario: Connection failure exits 3

- **WHEN** the server URL is unreachable
- **THEN** stdout contains the error reason and exit code is `3`
