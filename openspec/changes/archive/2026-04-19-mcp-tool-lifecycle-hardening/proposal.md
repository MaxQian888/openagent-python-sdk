## Why

The built-in MCP tool (`openagents/plugins/builtin/tool/mcp_tool.py`) opens a brand-new stdio subprocess (or HTTP/SSE session) on every single `invoke()` call. That design was chosen to keep anyio cancel scopes bounded to one call frame (see the class docstring and `test_failed_invoke_does_not_leak_into_next_call`), and we must not regress that invariant. But it has grown three real problems in production usage:

1. **Resource blow-up.** A ReAct loop that calls the same MCP server 20 times fork/execs the server 20 times. For heavyweight servers (node-based tavily-mcp, python servers with slow imports) this dominates wall-clock time and leaves orphan processes when the agent is interrupted.
2. **Failures surface late.** If the `mcp` extra isn't installed, or the `command` doesn't exist on PATH, or the SSE URL is unreachable, the user only learns about it mid-run when the LLM picks the tool. There's no pre-flight "is this configured correctly?" path before the agent loop starts.
3. **SSE path is untested and looks stale.** `_connect_http` imports `SseClientTransport` from `mcp.client.sse`, which is not a public export of the current MCP SDK (the SDK exposes `sse_client()`). No test exercises this branch. It probably throws `ImportError` today.

The goal is to keep the per-call cancel-scope safety as the default, but add **opt-in** reuse and up-front validation so heavy workloads don't have to pay per-call-fork overhead, and misconfiguration is caught before the agent loop runs.

## What Changes

- Add a new capability `mcp-client-runtime` that owns the lifecycle contract for MCP-backed tools: connection modes, pre-flight checks, session reuse, and shutdown.
- Introduce a configurable `connection_mode` on `McpTool.Config`: `per_call` (current behavior, default — preserves the cancel-scope invariant) and `pooled` (one long-lived session reused across `invoke()` calls, scoped to the plugin's lifetime).
- Add a `preflight()` method on `McpTool` (and a matching optional hook on `ToolPlugin`) that the `Runtime` invokes once per session before the first agent turn. For MCP tools it: verifies the `mcp` extra is importable, validates the server config, and (optionally) probes connectivity without leaving a session open. Surfaces actionable error messages naming the failing server id.
- Fix the SSE/HTTP path: replace the broken `SseClientTransport` import with the supported `sse_client()` API, and cover it with tests mirroring the stdio tests (using fakes, no real network).
- Add a process-level **in-flight dedup** so concurrent `invoke()` calls that target the same `(tool_id, tool_name, arguments-hash)` reuse one outstanding session instead of forking N subprocesses. Duration-bounded; opt-out via config.
- Add structured events (`mcp.preflight`, `mcp.connect`, `mcp.call`, `mcp.close`) emitted through the existing event bus so operators can see startup/teardown instead of guessing from log noise.
- Ship a `close()` that actually drains the pooled session (current implementation is a no-op; that's correct today but becomes a leak once pooling exists).
- Update `docs/plugin-development.md` with the new config knobs and the pre-flight contract. Refresh the MCP example in `docs/examples.md` to show `connection_mode: pooled` when it's appropriate.

No BREAKING changes — every new config field defaults to current behavior.

## Capabilities

### New Capabilities
- `mcp-client-runtime`: Lifecycle, connection-mode selection, pre-flight installation/connectivity checks, in-flight dedup, and event emission for MCP-backed tools. Owned by `openagents/plugins/builtin/tool/mcp_tool.py` and tested via `tests/unit/test_mcp_tool.py`.

### Modified Capabilities
<!-- None. `openspec/specs/` is currently empty; this change introduces the first spec. -->

## Impact

- **Code**: `openagents/plugins/builtin/tool/mcp_tool.py` (main implementation); `openagents/interfaces/tool.py` (optional `preflight` hook on `ToolPlugin` — default no-op, so existing tools are unaffected); `openagents/plugins/builtin/runtime/default_runtime.py` (call `preflight()` once per session before the first pattern turn).
- **Tests**: `tests/unit/test_mcp_tool.py` (extend — pooled mode, preflight, SSE path, dedup); per repo rule, tests land in the same change as the source.
- **Deps**: no new runtime deps. Still behind the optional `mcp` extra. Preflight must not require the extra to be installed when the tool isn't configured.
- **Coverage**: `mcp_tool.py` remains on the coverage-omit list (`pyproject.toml`). Preflight hook additions on `tool.py` are in scope and must keep coverage ≥ 90%.
- **Docs**: `docs/plugin-development.md`, `docs/examples.md`, MCP-related sections of `docs/api-reference.md` / `docs/api-reference.en.md`.
- **Backwards compatibility**: default `connection_mode=per_call` keeps every existing config working unchanged, including the tavily-mcp cancel-scope regression guard.
