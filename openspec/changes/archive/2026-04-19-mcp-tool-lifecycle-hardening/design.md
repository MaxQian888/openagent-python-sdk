## Context

`openagents/plugins/builtin/tool/mcp_tool.py` bridges MCP servers into the SDK as a single `ToolPlugin`. Its current invariant — which we are NOT going to break — is that `stdio_client()` and `ClientSession` install `anyio` task-group cancel scopes on the entering task, so their enter/exit MUST happen inside the same `invoke()` call. Violating that caused the historical "tavily_fallback cancelled mid-DNS" bug, and `tests/unit/test_mcp_tool.py::test_failed_invoke_does_not_leak_into_next_call` is the regression guard.

The downside: heavy MCP servers (node-based tavily-mcp, Python servers with big import graphs, anything that runs a model) are forked once per tool call. A 20-step ReAct loop against the same server means 20 subprocess spawns — seconds of wall-clock each. Interrupting the agent mid-run leaves orphans if pipes drain asynchronously. We also have no way to tell the user "your `mcp` extra isn't installed" or "your command isn't on PATH" until the agent actually picks the tool, which wastes an entire planning round.

Three other weaknesses:

- `_connect_http` imports `SseClientTransport` from `mcp.client.sse` — that symbol isn't a public export in the current MCP Python SDK (the SDK exposes `sse_client()`). This branch almost certainly `ImportError`s today and is uncovered by tests.
- There is no plumbing for concurrent calls. Two in-flight `invoke()` against the same stdio server fork two subprocesses even if the second could have trivially reused the first's session.
- `close()` is a deliberate no-op today because nothing owns state across calls. That is correct *today* and becomes a leak the moment we introduce pooling.

## Goals / Non-Goals

**Goals:**

- Preserve per-call cancel-scope safety as the default. `connection_mode=per_call` must behave exactly as today, down to the ExceptionGroup-unwrapping semantics.
- Provide an opt-in `connection_mode=pooled` that keeps one long-lived session per plugin instance and reuses it across calls. Acceptable trade-off: pooled mode does *not* give the same cancel-scope bound, and the docstring must say so loudly.
- Provide a `preflight()` entry point called once per session before the agent loop starts. It verifies the `mcp` extra is importable, the server config is well-formed, and (best-effort) the server is reachable — without leaving a process running.
- Fix the SSE path so HTTP-transport MCP servers actually work.
- Dedup concurrent `invoke()` calls that target the same tool+arguments so we don't fork N subprocesses in a burst.
- Emit structured events through the existing event bus for preflight/connect/call/close so operators can see what's happening.

**Non-Goals:**

- Multi-agent / multi-session sharing of one MCP process. Pool scope stays per-plugin-instance, which means per-`(session_id, agent_id)` (the plugin cache key — see `runtime.py`). We don't build a global server registry.
- Automatic installation of MCP servers. Preflight reports "not installed", it doesn't `pip install` or `npx install` anything.
- Reimplementing the MCP client protocol. We're a consumer of the `mcp` SDK, not a competitor.
- Changing the `ToolPlugin` base class in any way that requires existing tools to opt in. The new `preflight()` hook is optional with a default no-op.

## Decisions

### D1. Two connection modes, gated by config, with per-call as default

Add `connection_mode: Literal["per_call", "pooled"] = "per_call"` to `McpTool.Config`. Wire behavior through a strategy object (`_PerCallStrategy`, `_PooledStrategy`) selected in `__init__`. Both implement one method: `async def call(tool_name, arguments) -> dict`.

**Why a strategy object instead of branching in `invoke()`:** the per-call path has delicate ExceptionGroup unwrapping that we must not destabilize. Isolating pooled logic in its own class means the per-call code path in `invoke()` is character-identical to today; pooled is a drop-in alternative. Easy to prove "we didn't regress per-call" by diffing.

**Alternatives considered:** one unified connection that sometimes caches — rejected, because "sometimes caches" is exactly how leaky cancel scopes slip back in.

### D2. Pooled mode owns one `McpConnection` for the plugin's lifetime, drained by `close()`

The pool is a single connection, not N. Opened lazily on the first `invoke()`, serialized by an `asyncio.Lock` so two concurrent calls share one session. Drained by `McpTool.close()` which the runtime already calls during session teardown via the plugin loader's close path.

**Why just one session (not a real pool):** MCP stdio servers are effectively single-stream — the protocol multiplexes requests on one stdin/stdout pair, and the SDK's `ClientSession` already handles concurrent request IDs. A second session would mean a second subprocess, which defeats the whole point.

**Pooled-mode cancel scope caveat:** when a pooled session's subprocess dies mid-request, the `anyio` task group's cancel can escape the `invoke()` that triggered it and cancel whatever the caller was about to do. We **document this explicitly** in the docstring and in `docs/plugin-development.md`, and pooled mode adds a try/except around each `session.call_tool()` that swaps a dead session for a fresh one on the *next* call (not the same call — that would keep us inside the cancel scope).

### D3. `preflight()` as an optional `ToolPlugin` hook, called once per session

Add to `openagents/interfaces/tool.py`:

```python
async def preflight(self, context: "RunContext[Any] | None") -> None:
    """Optional one-shot validation before the first tool call.
    Default: no-op. Tools with external dependencies should override."""
    return None
```

Wire it into `DefaultRuntime.run()` right after tool rebinding, before `pattern.execute()`. Each tool's `preflight()` is awaited serially (tools are few; parallel adds complexity for no measurable win). A preflight raising `PermanentToolError` becomes a `RunResult` with `StopReason.ERROR` and a clear message naming the tool id.

`McpTool.preflight()` does three things:
1. Try importing `mcp` — fail fast with "install: `uv sync --extra mcp`".
2. Validate `server.command` exists on PATH (stdio) or `server.url` parses and resolves (HTTP) — use `shutil.which` / `urllib.parse.urlparse`, no network call required.
3. If `Config.probe_on_preflight=True` (default `False`), open a throwaway per-call connection, call `list_tools()`, close it. This costs one extra subprocess spawn per session but catches "server crashes on startup" before the agent loop starts. Default off to preserve current UX.

**Alternative considered:** a separate `TooLifecyclePlugin` mixin. Rejected — one optional method on the existing interface is lower friction and discoverable from the base class.

### D4. Fix SSE/HTTP via `sse_client()` plus tests

Replace:
```python
from mcp.client.sse import SseClientTransport
transport = SseClientTransport(url=..., headers=...)
reader, writer = await stack.enter_async_context(transport)
```
with the SDK's actual API:
```python
from mcp.client.sse import sse_client
reader, writer = await stack.enter_async_context(
    sse_client(url=self.config.url, headers=self.config.headers or {})
)
```

Add a `_FakeSseCM` fake mirroring `_FakeStdioCM` in `tests/unit/test_mcp_tool.py`, plus a test that a URL-configured `McpTool` routes through SSE and still honors the same enter/exit ordering guarantees.

Gate by trying the import and falling back with a clear error if the installed `mcp` version has a different SSE API — pinning the exact SDK version is out of scope here.

### D5. In-flight dedup via a per-instance coalescing map

Add an `asyncio.Lock`-protected dict on the plugin instance: `_inflight: dict[_CallKey, asyncio.Future]`. `_CallKey` = `(tool_name, canonical_json(arguments))`. On `invoke()`, check the map; if a future is already in flight for this key, `await` it instead of opening a new connection. First caller opens a connection, completes, sets the future, pops the key.

**Why canonical-JSON argument hash:** MCP calls with identical arguments genuinely return the same answer in the usual case (file reads, lookups). This dedup covers the "ReAct decided to call `list_files` twice in one turn" pattern without changing behavior semantics. It does **not** cover side-effecting calls — and that's fine, because LLMs rarely issue identical side-effecting calls in rapid succession, and we can document it.

**Opt-out:** `Config.dedup_inflight: bool = True`. Off for users whose MCP server has time-varying results (clock, RNG).

**Alternatives considered:** global dedup map across tool instances — rejected, cross-instance state invites ordering bugs. Cache the *result* for some TTL — rejected, that's a memory plugin's job, not a tool's.

### D6. Events through the existing event bus

Emit `tool.mcp.preflight`, `tool.mcp.connect`, `tool.mcp.call`, `tool.mcp.close` events with the tool id, server identifier (command or host), and duration. Consumers (`rich_console`, `file_logging`) already render structured events.

Use existing `RunContext.events` when `context` is passed to `invoke()`. Preflight emits through the runtime's event bus directly since it runs before the pattern loop.

## Risks / Trade-offs

- **Pooled mode cancel-scope leaks.** If a pooled session's subprocess dies, the anyio cancel can escape the call that triggered it. → **Mitigation**: default stays per-call; pooled mode documents the trade-off; dead-session detection swaps on the *next* call, not inside the failing call. Add a test that pooled mode with a killed subprocess does not cancel the *next* tool invocation on the same task.
- **Preflight adds per-session latency.** Loading `mcp` and `shutil.which` is cheap, but `probe_on_preflight=True` forks a subprocess before the agent runs. → **Mitigation**: probe is opt-in.
- **In-flight dedup leaks state across unrelated argument values.** If canonical-json collides (shouldn't, but) two unrelated calls share a result. → **Mitigation**: dedup map is keyed on `(tool_name, sha256-of-canonical-json)`; tests assert different-arg calls open separate connections.
- **SSE fix may encounter yet-another MCP SDK API rename.** → **Mitigation**: wrap the SSE import in the same try/except that stdio already uses; fall back to a clear error naming the installed SDK version, not a raw `ImportError`.
- **Adding `preflight()` to `ToolPlugin`** could be interpreted as breaking the interface. → **Mitigation**: default no-op implementation on the base class, so existing tools and user-authored tools compile unchanged. Coverage stays ≥ 90% because the default is one `return None`.
- **Orphaned pooled subprocesses on interrupt.** If the runtime is hard-killed without `close()`, pooled subprocesses are orphaned. → **Mitigation**: register an `atexit` hook that force-closes any live pools. Per-call mode is unaffected.

## Migration Plan

1. Land `preflight()` on `ToolPlugin` as a no-op first. Ship. No behavior change. (Step 1 in tasks.)
2. Add `connection_mode` config (default `per_call`), introduce strategy objects without changing per-call behavior, update tests to cover both strategies. (Steps 2–3.)
3. Fix SSE path and add SSE tests. (Step 4.)
4. Add `McpTool.preflight()` and wire into `DefaultRuntime`. (Step 5.)
5. Add in-flight dedup with tests. (Step 6.)
6. Update docs; add an example in `examples/` showing pooled mode + preflight. (Step 7.)

**Rollback**: each step is independently revertable. The default remains `per_call` with no preflight probe, so the worst case of a bad release is "tests break, revert that PR". There is no on-disk state to migrate.

## Open Questions

- Should pooled mode auto-downgrade to per-call when it detects repeated subprocess crashes in one session? Leaning no — an agent should surface the error, not paper over it. Flag for review in tasks.
- Do we want preflight results cached for `Runtime.reload()` hot-reload? Leaning no — reload means "assume config changed", so re-validate. Document.
