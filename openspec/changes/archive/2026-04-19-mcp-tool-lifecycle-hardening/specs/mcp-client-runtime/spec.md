## ADDED Requirements

### Requirement: Per-call connection mode preserves cancel-scope safety

`McpTool` SHALL accept `connection_mode: "per_call" | "pooled"` in its configuration, defaulting to `"per_call"`. In `per_call` mode the plugin MUST open a fresh `stdio_client` (or SSE/HTTP equivalent) and `ClientSession` on every `invoke()` call, MUST call `ClientSession.initialize()` before any `list_tools`/`call_tool`, and MUST enter and exit both context managers within the same `invoke()` task so that `anyio` cancel scopes cannot outlive the call.

#### Scenario: Default configuration uses per_call mode
- **WHEN** `McpTool` is constructed without specifying `connection_mode`
- **THEN** it selects `per_call` mode and every `invoke()` opens-and-closes a fresh session in a single call frame

#### Scenario: Per_call mode still unwinds on failure in the same task
- **WHEN** `call_tool` raises inside an `invoke()` in `per_call` mode
- **THEN** both the session and the stdio context managers exit, in reverse enter order, on the same event-loop task as the call

#### Scenario: Per_call mode does not leak state between calls
- **WHEN** an `invoke()` in `per_call` mode fails and a subsequent `invoke()` runs
- **THEN** the second call opens a brand-new session, the first call's failure does not cancel the second call, and `_last_available_tools` reflects only the latest successful call

### Requirement: Pooled connection mode reuses one session

When `connection_mode="pooled"`, `McpTool` SHALL lazily open a single long-lived `McpConnection` on the first `invoke()` and reuse it across subsequent calls within the same plugin instance. Concurrent calls MUST be serialized through the same session using an `asyncio.Lock`. The pooled session MUST be drained by `McpTool.close()` before the plugin is discarded.

#### Scenario: Pooled mode opens only one session across multiple calls
- **WHEN** three sequential `invoke()` calls are made against an `McpTool` configured with `connection_mode="pooled"`
- **THEN** only one `stdio_client` context is entered, and `ClientSession.initialize()` is called exactly once

#### Scenario: Pooled mode recovers from a dead subprocess on the next call
- **WHEN** the pooled session's subprocess dies during a call and a subsequent `invoke()` runs on the same tool instance
- **THEN** the dead session is discarded and the next call opens a new session without cancelling the caller

#### Scenario: close() drains the pooled session
- **WHEN** `McpTool.close()` is awaited on a plugin that currently owns a pooled session
- **THEN** the session and stdio contexts are exited cleanly, `_session` is reset to `None`, and a subsequent `close()` is a no-op

### Requirement: MCP tools support pre-flight validation

`McpTool` SHALL implement an optional `preflight(context)` hook on `ToolPlugin` and `DefaultRuntime` SHALL invoke it once per session, before the first agent turn, for every tool bound to the run. Preflight MUST verify that the `mcp` Python SDK is importable, validate the `server` configuration (stdio `command` resolvable via `shutil.which`, or HTTP `url` parseable with a scheme and netloc), and — if `Config.probe_on_preflight=True` — open a throwaway session, call `list_tools()`, and close it. Any preflight failure MUST raise `PermanentToolError` with a message naming the tool id and the specific failure cause; the runtime MUST translate that into a `RunResult` with `StopReason.ERROR` without calling the pattern loop.

#### Scenario: Preflight fails fast when mcp extra is missing
- **WHEN** `McpTool.preflight()` runs and `import mcp` raises `ImportError`
- **THEN** preflight raises `PermanentToolError` with a message that references the failing tool id and the install hint `uv sync --extra mcp`

#### Scenario: Preflight rejects a stdio command not on PATH
- **WHEN** the configured `server.command` is not found by `shutil.which`
- **THEN** preflight raises `PermanentToolError` naming the missing command and the tool id, without forking a subprocess

#### Scenario: Preflight probe surfaces server startup failure before the agent loop
- **WHEN** `Config.probe_on_preflight=True` and the MCP server exits non-zero on startup
- **THEN** preflight raises `PermanentToolError` naming the tool id and the probe result, and `DefaultRuntime.run()` returns a `RunResult` with `StopReason.ERROR` without invoking the pattern

#### Scenario: Default tool plugins do not need to override preflight
- **WHEN** a `ToolPlugin` subclass does not override `preflight`
- **THEN** calling `preflight()` returns `None` without side effects, and runtime behavior for that tool is unchanged

### Requirement: HTTP/SSE transport uses the supported MCP SDK API

`McpTool` SHALL use `mcp.client.sse.sse_client(url=..., headers=...)` — the current MCP Python SDK's supported entry point — for HTTP/SSE-configured servers, instead of any symbol that is not a public export. The SSE path MUST follow the same enter/exit ordering guarantees as the stdio path (initialize inside the same task as the call, exit in reverse enter order on failure). If the installed `mcp` SDK does not expose `sse_client`, `McpTool` MUST raise a `RuntimeError` naming the installed SDK version and the expected symbol, not a raw `ImportError`.

#### Scenario: URL-configured tool routes through sse_client
- **WHEN** `McpTool` is configured with `server.url` and no `server.command`
- **THEN** `sse_client` is called with the URL and headers, and `ClientSession.initialize()` is invoked before any `call_tool`

#### Scenario: SSE path unwinds in the same task on failure
- **WHEN** `call_tool` raises in an SSE-configured `invoke()` call
- **THEN** both the session and the SSE transport contexts exit, in reverse enter order, on the same event-loop task

#### Scenario: Missing sse_client symbol produces an actionable error
- **WHEN** the installed `mcp` SDK does not expose `sse_client`
- **THEN** the tool raises a `RuntimeError` whose message includes the installed SDK version and a hint to upgrade, not a raw `ImportError`

### Requirement: In-flight duplicate call coalescing

`McpTool` SHALL coalesce concurrent `invoke()` calls that share the same `(tool_name, canonicalized-arguments)` key, so only one session is opened per in-flight key. Callers arriving while a matching call is in flight MUST `await` the same result. Coalescing SHALL be disabled when `Config.dedup_inflight=False` or when `connection_mode="pooled"` (pooled already serializes through the session lock). The coalescing map MUST remove the key once the in-flight call resolves, regardless of success or failure.

#### Scenario: Two concurrent identical calls share one session
- **WHEN** two `invoke()` coroutines are scheduled simultaneously with the same tool name and arguments on the same `McpTool` instance
- **THEN** exactly one stdio/SSE session is opened, both awaits return the same result, and the coalescing key is removed after they resolve

#### Scenario: Different arguments do not share
- **WHEN** two concurrent `invoke()` calls differ in any argument value
- **THEN** each call opens its own session and the results are computed independently

#### Scenario: Dedup can be disabled per instance
- **WHEN** `dedup_inflight=False` and two identical concurrent calls run
- **THEN** two separate sessions are opened and neither call awaits the other's future

#### Scenario: Coalescing key is cleared after a failed call
- **WHEN** a coalesced call raises and a subsequent identical call runs
- **THEN** the second call opens a fresh session rather than re-awaiting the failed future

### Requirement: MCP lifecycle emits structured events

`McpTool` SHALL emit the following events through the runtime's event bus when a `RunContext` with an attached event bus is available: `tool.mcp.preflight` (with `tool_id`, `server_identifier`, `result`, `duration_ms`), `tool.mcp.connect` (on session open), `tool.mcp.call` (with `tool_name`, `success`, `duration_ms`), and `tool.mcp.close` (on session drain). Events MUST NOT carry tool arguments or results (privacy), only timing and status. When no event bus is available, emission MUST be skipped silently.

#### Scenario: A successful call emits connect and call events
- **WHEN** a single `invoke()` succeeds against an MCP server with an event bus attached
- **THEN** a `tool.mcp.connect` event precedes a `tool.mcp.call` event with `success=True` and a `duration_ms` field

#### Scenario: Preflight failure emits a preflight event with failure status
- **WHEN** `preflight()` raises `PermanentToolError`
- **THEN** a `tool.mcp.preflight` event is emitted with `result="error"` and the failure cause before the exception propagates

#### Scenario: No event bus means no emission
- **WHEN** `invoke()` is called with a `context` whose event bus is `None`
- **THEN** no exception is raised from the event-emission path and the call completes normally
