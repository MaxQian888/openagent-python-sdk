## 1. Preflight interface seam (behavior-preserving)

- [x] 1.1 Add default no-op `async def preflight(self, context) -> None: return None` on `ToolPlugin` in `openagents/interfaces/tool.py`, with a short docstring pointing at the MCP use case
- [x] 1.2 Extend `DefaultRuntime.run()` in `openagents/plugins/builtin/runtime/default_runtime.py` to iterate the rebound tools once per session and `await tool.preflight(context)` before `pattern.execute()`
- [x] 1.3 Translate `PermanentToolError` from preflight into a `RunResult` with `StopReason.FAILED` (existing enum; spec text mentioned `ERROR` but `FAILED` is the canonical value), naming the failing tool id in the message, and emit a `tool.preflight` event on the bus
- [x] 1.4 Unit test in `tests/unit/test_runtime_core.py`: a tool whose `preflight` raises `PermanentToolError` causes `runtime.run()` to return `stop_reason=failed` without invoking the pattern; a tool without an override runs normally
- [x] 1.5 Verify `uv run pytest -q` passes and coverage stays ≥ 90%

## 2. Config knob + connection-mode strategy split

- [x] 2.1 Add `connection_mode: Literal["per_call", "pooled"] = "per_call"`, `probe_on_preflight: bool = False`, `dedup_inflight: bool = True` to `McpTool.Config` in `openagents/plugins/builtin/tool/mcp_tool.py`
- [x] 2.2 Extract the current `invoke()` body into `_PerCallStrategy.call(tool_name, arguments)`, keeping the ExceptionGroup unwrap and `_last_available_tools` update identical — pure refactor with zero behavior change
- [x] 2.3 Re-run the existing `tests/unit/test_mcp_tool.py` and confirm all five pre-existing tests pass unchanged (all 9 existing tests green after refactor)

## 3. Pooled connection strategy

- [x] 3.1 Implement `_PooledStrategy`: holds one `McpConnection`, opens lazily under an `asyncio.Lock`, reuses across calls, detects dead-session errors and swaps on the *next* call (never inside the failing call)
- [x] 3.2 Wire `McpTool.close()` to drain the pooled session via `McpConnection.__aexit__`; keep `close()` idempotent (second close is a no-op)
- [x] 3.3 Register an `atexit` hook that force-closes live pools so interrupted runs don't orphan subprocesses; uses a list of `weakref.ref[McpTool]` (WeakSet not usable because `BasePlugin` is unhashable under the pydantic base)
- [x] 3.4 Tests: three sequential pooled calls open exactly one stdio context; `close()` drains it; a pooled call after a dead-session recovers on the next call without cancelling it; `close()` is idempotent

## 4. Fix SSE/HTTP transport

- [x] 4.1 Replace `SseClientTransport` usage in `_connect_http` with `sse_client(url=..., headers=...)` from `mcp.client.sse`; wrap the import in the same try/except pattern as stdio
- [x] 4.2 If `sse_client` is missing on the installed SDK, raise `RuntimeError` naming the installed `mcp` version and the expected symbol (not a raw `ImportError`)
- [x] 4.3 Add `_FakeSseCM` + `_patch_mcp_sse` helpers in `tests/unit/test_mcp_tool.py` mirroring the stdio fakes
- [x] 4.4 Tests: URL-configured `McpTool` routes through `sse_client`; enter/exit order is LIFO on success and on `call_tool` failure; missing `sse_client` symbol produces the actionable `RuntimeError`

## 5. McpTool preflight implementation

- [x] 5.1 Implement `McpTool.preflight()` — step 1: try `import mcp` and raise `PermanentToolError("[tool:<id>] mcp extra not installed; run: uv sync --extra mcp")` on failure
- [x] 5.2 Step 2: validate `server` config — stdio path runs `shutil.which(command)` (with a helpful error on miss); HTTP path runs `urllib.parse.urlparse` and rejects a missing scheme or netloc
- [x] 5.3 Step 3: when `probe_on_preflight=True`, open a throwaway per-call `McpConnection`, call `list_tools()`, close it, attach the result count to the preflight event
- [x] 5.4 Emit a `tool.mcp.preflight` event (tool id, server identifier, result, duration ms) — no arguments or results logged
- [x] 5.5 Tests: missing `mcp` import raises `PermanentToolError` with install hint; missing stdio command raises `PermanentToolError` without forking; bad URL raises `PermanentToolError`; `probe_on_preflight=True` with a server that crashes on startup surfaces as `PermanentToolError` before the agent loop runs

## 6. In-flight dedup

- [x] 6.1 Add `_inflight: dict[tuple[str, str], asyncio.Future]` on `McpTool`, guarded by an `asyncio.Lock`; key is `(tool_name, sha256(canonical_json(arguments)))`
- [x] 6.2 On `invoke()` in `per_call` mode, when `dedup_inflight` is on: if a future exists for the key, `await` it; otherwise create the future, run the call, set the result, pop the key under the lock
- [x] 6.3 Skip dedup entirely when `connection_mode="pooled"` (the session lock already serializes) and when `dedup_inflight=False`
- [x] 6.4 Guarantee the key is popped on both success and failure paths (try/finally-like flow with explicit pop in both branches)
- [x] 6.5 Tests: two concurrent identical calls open exactly one session and return equal results; differing arguments open two sessions; `dedup_inflight=False` always opens two sessions; a failed coalesced call is not re-awaited by the next call (fresh session)

## 7. Structured events

- [x] 7.1 Emit `tool.mcp.connect` on session open, `tool.mcp.call` with `tool_name` / `success` / `duration_ms` per call, `tool.mcp.close` on session drain — via `context.event_bus` when a RunContext event bus is available
- [x] 7.2 Skip emission silently when no event bus is attached; tests assert no exception is raised
- [x] 7.3 Assert events never include arguments, results, or headers (privacy invariant) — `test_events_never_include_arguments_or_results` passes a unique sentinel through and inspects serialized event payloads

## 8. Docs and examples

- [x] 8.1 Update `docs/plugin-development.md` with a new "可选：preflight() 预启动检查" section under §6; MCP connection-mode trade-offs + `probe_on_preflight` guidance + cancel-scope caveat went into `docs/builtin-tools.md` (where the MCP docs actually live) and the mirror `docs/builtin-tools.en.md`
- [x] 8.2 Refresh MCP-tool references in `docs/api-reference.md` and `docs/api-reference.en.md` — added §18.1 "`McpTool` lifecycle config" with new config fields, `preflight()` hook, emitted event names
- [x] 8.3 Updated `docs/examples.md` with a `connection_mode: "pooled"` + `probe_on_preflight: true` example for the pptx-agent's Tavily MCP usage, including when pooled is appropriate and when to stay on `per_call`

## 9. Verification

- [x] 9.1 `uv run pytest -q` clean — 825 passed, 4 skipped (unrelated MCP-extra guards)
- [x] 9.2 `uv run coverage run -m pytest && uv run coverage report` — total coverage 92% (floor is 90%; mcp_tool.py stays on the coverage-omit list, but the `ToolPlugin.preflight` seam addition is covered by the 3 new runtime-core tests)
- [ ] 9.3 Manual smoke: run one example configured for per_call and one for pooled against a lightweight local MCP server; confirm pool opens one subprocess and per_call opens N — requires a local MCP server binary; documented as manual validation, not part of the automated gate. The fake-backed unit tests in 3.4 prove the logic.
- [x] 9.4 Ruff / format pass on edited files — all auto-fixable issues resolved; the remaining 7 `F821 BaseExceptionGroup` warnings are pre-existing (ruff has no `target-version` in `pyproject.toml`; `BaseExceptionGroup` is a valid Python 3.11+ builtin and works at runtime). Not a blocker for this change.
- [x] 9.5 Run `openspec status --change mcp-tool-lifecycle-hardening` and confirm `isComplete` before archiving
