# Plugin System Hardening & Observability — Design

- Status: drafted via brainstorm 2026-04-17, autonomous implementation authorized
- Scope: single spec, single implementation plan, single PR-shape
- Position in roadmap: this is **Spec B** of the 3-spec sequence agreed during brainstorm 2026-04-17:
  - **A** (landed 2026-04-17, commits c02ff63 → 9cf1378): cleanup + consistency
  - **B** (this spec): hardening + observability
  - **C** (later): selective new builtins (sqlite session, OTel events bridge)
- Non-goals: kernel protocol changes, new seams, new builtins, breaking event renames, breaking config changes, property-based testing or fuzzing tools, full audit of every builtin's concurrency contract.

## 1. Motivation

Spec A (`2026-04-17-plugin-system-cleanup-design.md`) closed the structural debt that the previous expansion left open. Spec B is what remains to make the plugin layer feel **production-ready** rather than just **structurally correct**:

1. **Errors don't tell users how to fix them.** `PluginLoadError: Unknown memory plugin type: 'bufer'` is correct but unhelpful. The user has to grep the registry to learn that `buffer` exists.
2. **Events have no documented schema.** Subscribers can't know which payload keys they can rely on. Several seams (`memory`, `context_assembler`, `session.run`) emit nothing at all, so observability is patchy.
3. **Concurrency contracts are implicit.** `JsonlFileSessionManager` shares one file per session with no lock. `FileLoggingEventBus` has no IO-failure path. `RetryToolExecutor`'s sleep can hide cancellation. The current test suite never exercises any of these.
4. **Docstrings are inconsistent.** Some plugins (`RetryToolExecutor`) have detailed class-level docs; others (`BufferMemory`) have one line. Pattern authors learn the contract by reading code.
5. **Coverage floor is 90% with 0 buffer.** Any new code lands flush against the floor; the next refactor risks breaking CI without writing a single bug.

This spec addresses all five in one PR-shape, fully backward compatible.

### 1.1 Audit confirmation

Before drafting, the plugin tree was scanned for:
- 132 raise/except occurrences across 21 builtin files; most have no `hint`/`docs_url` companion text.
- Event names exist consistently (dotted form like `tool.called`, `pattern.step_started`) but no schema or required-payload documentation.
- 5 builtins surface candidate concurrency / IO-failure risks: `session/jsonl_file`, `events/file_logging`, `memory/chain`, `tool_executor/retry`, `runtime/default_runtime`.
- Docstring style varies widely; ~40 plugin classes total to align.
- Current overall coverage 90% (floor exactly).

## 2. High-level plan

Five work packages. Mutually independent in code; ordered as below in implementation plan.

| WP | theme | files touched (approx) |
|---|---|---|
| 1 | Error info — `hint` + `docs_url` + `near_match` helper + ~12 high-ROI applications | 4 (errors module) + ~12 (call sites) |
| 2 | Event schema + docs — `EVENT_SCHEMAS` registry + supplemental lifecycle events + `docs/event-taxonomy.md` | 2 (interfaces) + 1 (events bus) + 4-6 (new emit sites) + 1 (new doc) |
| 3 | Concurrency / IO hardening — 7 stress tests + fix only what they expose | 5-8 (depending on what tests catch) |
| 4 | Docstring three-section template — Google-style "What / Usage / Depends on" | ~40 builtin class files |
| 5 | Coverage floor 90 → 92 — pyproject change + targeted backfill where WP3 doesn't cover | 1 (pyproject) + ~5 (test backfills) |

**Approach principles:**

- **Fully backward compatible.** No exception classes change signatures incompatibly; no event name renames; no breaking config; no behavior changes outside what the new tests catch as bugs.
- **No kernel protocol changes.** Stays at the SDK seam layer.
- **Test-driven hardening.** WP3 writes the tests first; only fixes the bugs they actually expose. No preemptive locking.
- **Advisory schema, not enforcement.** Event schema validation logs warnings but never raises. Same posture as Spec A's unknown-config-keys handling.
- **Patch release.** Lands on 0.3.x; no breaking cut.

## 3. Component specs

### 3.1 WP1 — Error info enrichment

#### 3.1.1 Base class additions (`openagents/errors/exceptions.py`)

Add two optional kwargs to `OpenAgentsError.__init__`:

```python
class OpenAgentsError(Exception):
    """Base exception for SDK errors."""

    # ... existing fields ...
    hint: str | None
    docs_url: str | None

    def __init__(
        self,
        message: str = "",
        *,
        hint: str | None = None,
        docs_url: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        run_id: str | None = None,
        tool_id: str | None = None,
        step_number: int | None = None,
    ) -> None:
        super().__init__(message)
        # ... existing assignments unchanged ...
        self.hint = hint
        self.docs_url = docs_url

    def __str__(self) -> str:
        msg = super().__str__()
        parts = [msg] if msg else []
        if self.hint:
            parts.append(f"  hint: {self.hint}")
        if self.docs_url:
            parts.append(f"  docs: {self.docs_url}")
        return "\n".join(parts)
```

`BudgetExhausted`, `OutputValidationError`, `ToolError`, `ModelRetryError` (subclasses with custom `__init__`) thread `hint` / `docs_url` through to `super().__init__`.

#### 3.1.2 New helper (`openagents/errors/suggestions.py`)

```python
"""Lightweight 'did you mean?' helpers."""

from __future__ import annotations

import difflib
from typing import Iterable


def near_match(needle: str, candidates: Iterable[str], *, cutoff: float = 0.6) -> str | None:
    """Return the closest candidate to ``needle`` (or None)."""
    matches = difflib.get_close_matches(needle, list(candidates), n=1, cutoff=cutoff)
    return matches[0] if matches else None
```

No new exception types.

#### 3.1.3 Application sites

The implementation plan picks the high-ROI sites; the spec lists the floor (~12 sites that demonstrably surface user mistakes):

| file:line | hint added |
|---|---|
| `plugins/loader.py:116` Unknown plugin type | `near_match` against builtin keys + `hint=f"Did you mean '{guess}'? Available: {sorted_keys}"` |
| `plugins/loader.py:64` Invalid impl path | `hint="impl path must be 'module.path:Symbol' or 'module.path.Symbol'"` |
| `plugins/loader.py:115` Module has no symbol | `hint=f"check the spelling of '{attr_name}' in module '{module_name}'"` |
| `config/loader.py:38` Config file does not exist | `hint=f"Run from repo root, or pass an absolute path"` + `docs_url` to plugin-development.md |
| `config/loader.py:26` Env var not set | `hint=f"Set in shell or copy {dirname}/.env.example to {dirname}/.env"` |
| `config/loader.py:54` Invalid JSON | `hint=f"Validate the JSON syntax (e.g. via jq)"` |
| `runtime/runtime.py` AgentNotFoundError | `near_match` against `[a.id for a in self.config.agents]` + `hint` listing available |
| `interfaces/pattern.py:130` Tool not registered | `near_match` against `ctx.tools.keys()` + `hint` |
| `interfaces/typed_config.py` (new validation hint when ValidationError occurs) | `hint=f"Check {plugin_name}'s Config schema with 'openagents schema'"` |
| `plugins/builtin/session/jsonl_file.py` corrupted line | `hint=f"line {n} in {path}: invalid JSON; backup the file or replay-skip"` |
| `plugins/builtin/tool_executor/safe.py` validate_params failed | `hint=f"see tool '{tool_id}' schema()"` |
| `plugins/builtin/skills/local.py` skill not found | `near_match` against discovered skill names |

Implementation plan may add more during scan; floor of 12 must be addressed.

### 3.2 WP2 — Event schema + supplemental lifecycle

#### 3.2.1 New file `openagents/interfaces/event_taxonomy.py`

```python
"""Declared schema for events emitted by the SDK and built-in plugins.

Schema is **advisory**: ``EventBus.emit`` logs a warning when a declared
event name is emitted with missing required payload keys, but never
raises. Subscribers should not rely on the warning being present.

Custom user events not present in ``EVENT_SCHEMAS`` are emitted unchanged
with no validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EventSchema:
    name: str
    required_payload: tuple[str, ...] = ()
    optional_payload: tuple[str, ...] = ()
    description: str = ""


EVENT_SCHEMAS: dict[str, EventSchema] = {
    # === existing events (carried over verbatim, no rename) ===
    "tool.called":    EventSchema("tool.called",    ("tool_id", "params"), (),
                                  "Pattern is about to invoke a tool."),
    "tool.succeeded": EventSchema("tool.succeeded", ("tool_id", "result"),
                                  ("executor_metadata",),
                                  "Tool returned successfully."),
    "tool.failed":    EventSchema("tool.failed",    ("tool_id", "error"), (),
                                  "Tool raised; final after fallback. Use 'tool.retry_requested' for ModelRetry signal."),
    "tool.retry_requested": EventSchema("tool.retry_requested",
                                  ("tool_id", "attempt", "error"), (),
                                  "Pattern caught ModelRetryError and is retrying."),
    "llm.called":     EventSchema("llm.called",     ("model",), (),
                                  "Pattern is about to call an LLM."),
    "llm.succeeded":  EventSchema("llm.succeeded",  ("model",), (),
                                  "LLM returned successfully."),
    "usage.updated":  EventSchema("usage.updated",  ("usage",), (),
                                  "RunUsage object was updated; emitted after every LLM call."),
    "pattern.step_started":  EventSchema("pattern.step_started",  ("step",), ("plan_step",),
                                  "Pattern began an execution step."),
    "pattern.step_finished": EventSchema("pattern.step_finished", ("step", "action"), (),
                                  "Pattern completed an execution step."),
    "pattern.phase":         EventSchema("pattern.phase",         ("phase",), (),
                                  "Pattern transitioned phases (e.g. planning, executing)."),
    "pattern.plan_created":  EventSchema("pattern.plan_created",  ("plan",), (),
                                  "PlanExecutePattern produced its plan."),

    # === new supplemental lifecycle events ===
    "session.run.started":          EventSchema("session.run.started",
                                  ("agent_id", "session_id"), ("run_id", "input_text"),
                                  "Runtime begins a single run."),
    "session.run.completed":        EventSchema("session.run.completed",
                                  ("agent_id", "session_id", "stop_reason"),
                                  ("run_id", "duration_ms"),
                                  "Runtime finished a single run."),
    "context.assemble.started":     EventSchema("context.assemble.started", (), (),
                                  "context_assembler.assemble() is about to run."),
    "context.assemble.completed":   EventSchema("context.assemble.completed",
                                  ("transcript_size",), ("artifact_count", "duration_ms"),
                                  "context_assembler.assemble() returned."),
    "memory.inject.started":        EventSchema("memory.inject.started", (), (),
                                  "memory.inject() is about to run."),
    "memory.inject.completed":      EventSchema("memory.inject.completed",
                                  (), ("view_size",),
                                  "memory.inject() returned."),
    "memory.writeback.started":     EventSchema("memory.writeback.started", (), (),
                                  "memory.writeback() is about to run."),
    "memory.writeback.completed":   EventSchema("memory.writeback.completed", (), (),
                                  "memory.writeback() returned."),
}
```

#### 3.2.2 Bus enhancement (`openagents/plugins/builtin/events/async_event_bus.py`)

Add advisory schema check inside `emit`:

```python
async def emit(self, event_name: str, **payload) -> RuntimeEvent:
    schema = EVENT_SCHEMAS.get(event_name)
    if schema is not None:
        missing = [k for k in schema.required_payload if k not in payload]
        if missing:
            logger.warning(
                "event '%s' missing required payload keys %s "
                "(declared in event_taxonomy.EVENT_SCHEMAS)",
                event_name, missing,
            )
    # ... existing emit logic unchanged ...
```

`FileLoggingEventBus` and any future combinator inherit by virtue of forwarding to inner.

#### 3.2.3 New emit sites

In `openagents/plugins/builtin/runtime/default_runtime.py`, wrap the existing `Runtime.run` body:

```python
await self._event_bus.emit("session.run.started",
                           agent_id=agent_id, session_id=session_id,
                           run_id=run_id, input_text=input_text)

await self._event_bus.emit("context.assemble.started")
assembly_result = await context_assembler.assemble(...)
await self._event_bus.emit("context.assemble.completed",
                           transcript_size=len(assembly_result.transcript),
                           artifact_count=len(assembly_result.artifacts))

await self._event_bus.emit("memory.inject.started")
await memory.inject(ctx)
await self._event_bus.emit("memory.inject.completed",
                           view_size=len(ctx.memory_view))

# ... pattern.execute() runs (its own events) ...

await self._event_bus.emit("memory.writeback.started")
await memory.writeback(ctx)
await self._event_bus.emit("memory.writeback.completed")

await self._event_bus.emit("session.run.completed",
                           agent_id=agent_id, session_id=session_id,
                           stop_reason=stop_reason, duration_ms=duration_ms)
```

Each new emit is one line, bracketed around the existing call.

#### 3.2.4 New documentation `docs/event-taxonomy.md`

Markdown table generated by a small helper (`openagents/tools/gen_event_doc.py`, also new — small CLI):

```markdown
# Event Taxonomy

Events emitted by the SDK and built-in plugins. Schema is advisory — see
`openagents/interfaces/event_taxonomy.py:EVENT_SCHEMAS`.

| Event | Required payload | Optional payload | Description |
|---|---|---|---|
| `tool.called` | `tool_id`, `params` | — | Pattern is about to invoke a tool. |
| `tool.succeeded` | `tool_id`, `result` | `executor_metadata` | Tool returned successfully. |
| ... | ... | ... | ... |
```

The helper writes this file from `EVENT_SCHEMAS` so the doc never drifts.

### 3.3 WP3 — Concurrency / IO hardening

#### 3.3.1 Tests written first

Seven stress tests:

| file | scenario |
|---|---|
| `tests/unit/test_jsonl_session_concurrent_append.py` | 100 concurrent `append_message` to same session via `asyncio.gather`; reload via fresh manager; transcript order matches submission order. |
| `tests/unit/test_jsonl_session_io_failure_recovery.py` | Monkeypatch `Path.open` to raise `PermissionError` once; assert exception propagates; subsequent `append_message` succeeds. |
| `tests/unit/test_file_logging_io_failure_does_not_break_inner.py` | Monkeypatch the log file write to raise `OSError`; assert inner bus still receives all emits and history is complete. |
| `tests/unit/test_file_logging_high_frequency_emit.py` | 1000 emits via `asyncio.gather`; inner history length == 1000. |
| `tests/unit/test_chain_memory_child_order.py` | ChainMemory with 3 children: assert `inject` called in declared order; `writeback` called in declared order. |
| `tests/unit/test_retry_executor_cancellation.py` | Inner executor sleeps; create task running `RetryToolExecutor.execute`; cancel during backoff; assert `CancelledError` raised in awaiting code. |
| `tests/integration/test_concurrent_runs_isolated.py` | Two `runtime.run` calls on different agent_ids via `asyncio.gather`; each session_state isolated; no cross-talk. |

#### 3.3.2 Fixes (only what tests catch)

Predicted, but applied **only if the corresponding test fails**:

- `JsonlFileSessionManager`: per-session `asyncio.Lock` map (key by sid); `append_message` / `save_artifact` / `create_checkpoint` / `set_state` all serialize on the same lock.
- `FileLoggingEventBus.emit`: wrap file-append in `try/except OSError` and `logger.error("file_logging append failed: %s", exc)`; never raise; inner emit always runs first.
- `RetryToolExecutor.execute`: wrap inner executor call in `asyncio.shield` if cancellation tests reveal partial-state corruption; otherwise just `await asyncio.sleep` already supports cancellation natively.
- `ChainMemory`: enforce declared child order via `for child in self._children` (already correct); test verifies.
- `Runtime.run`: confirm `RunContext` is per-call and not shared; concurrency test verifies.

If a fix is **not** needed (test passes on first run), the spec is silent — no preemptive change.

### 3.4 WP4 — Docstring three-section template

Template (Google-style):

```python
class FooBar(...):
    """One-line summary ending with a period.

    What:
        2-4 sentences describing what this plugin does and why
        (the user-facing behavior).

    Usage:
        Configuration shape and a 1-2 line example:
        ``{"type": "foobar", "config": {"key": "value"}}``

    Depends on:
        - ``RunContext.state`` for X
        - sibling plugin ``baz``
        - external resource Y
    """
```

**Scope** — every plugin class in `openagents/plugins/builtin/**/*.py`:
- 4 memory builtins
- 3 pattern builtins
- 4 context_assembler builtins
- 2 tool_executor builtins
- 3 execution_policy builtins
- 2 followup_resolver builtins
- 2 response_repair_policy builtins
- 2 session builtins
- 2 events builtins
- 1 skills builtin
- 1 runtime builtin
- 25 tool builtins (some can have 1-line Usage / Depends)

Total ~40 classes. Pure text edits, no logic touch.

**Lint test** — `tests/unit/test_builtin_docstrings_are_three_section.py`:

```python
def test_every_builtin_class_has_three_section_docstring():
    classes = list(_collect_builtin_plugin_classes())
    missing = []
    for cls in classes:
        doc = (cls.__doc__ or "").strip()
        if not doc:
            missing.append(f"{cls.__name__}: missing docstring")
            continue
        for header in ("What:", "Usage:", "Depends on:"):
            if header not in doc:
                missing.append(f"{cls.__name__}: missing '{header}'")
    assert not missing, "\n".join(missing)
```

This test is the enforcement; once green, future builtins must follow.

### 3.5 WP5 — Coverage floor 90 → 92

#### 3.5.1 Mechanical change

`pyproject.toml`:
```toml
[tool.coverage.report]
fail_under = 92  # was 90
```

#### 3.5.2 Backfill candidates

After WP3 lands and runtime/default_runtime.py + hotreload.py + chain.py + retry.py coverage rises naturally, run `coverage report` and target any file <90%:

| file (current %) | candidate test |
|---|---|
| `runtime/default_runtime.py` (87) | covered by WP3 concurrent runs test + new lifecycle emit branches |
| `utils/hotreload.py` (82) | add `test_hotreload_real_aiohttp_lifecycle.py` binding to port 0 |
| `plugins/builtin/skills/local.py` (86) | add edge-case tests for skill discovery / IO errors |
| `plugins/builtin/tool/datetime_tools.py` (84) | minor coverage backfill for invalid input branches |
| `plugins/builtin/tool/math_tools.py` (83) | minor coverage backfill for clamp / overflow paths |

Plan reads coverage report after WP3 to decide which backfills are needed.

#### 3.5.3 Fallback clause

If after all backfills the suite reports 91.x%, accept it: revert pyproject change to `fail_under = 91` and document in PR description. **Coverage is a tool, not a goal.** Do not write meaningless tests.

## 4. Data flow

### 4.1 WP1 (no runtime data flow change)

Only `Exception.__str__` output format changes. Catch blocks see the same exception types and fields; multi-line `str(exc)` may surprise log scrapers parsing single-line errors.

### 4.2 WP2 (event flow is purely additive)

`Runtime.run()` now emits 8 new lifecycle events bracketing existing operations. Existing event names and payloads are unchanged. Wildcard `*` subscribers receive ~8 more events per run.

### 4.3 WP3 (potential concurrency primitives)

`JsonlFileSessionManager` likely gains per-session asyncio.Lock; cross-session writes still parallel. `FileLoggingEventBus.emit` likely gains try/except around the file write; inner emit unaffected. Other 5 stress tests probably pass without code changes — silence in those means no flow change.

## 5. Error handling and migration

### 5.1 New exception types

None.

### 5.2 New optional fields on `OpenAgentsError`

`hint: str | None = None`, `docs_url: str | None = None`. Default None preserves byte-identical state for code not opting in.

### 5.3 Warning behaviors

| trigger | mechanism |
|---|---|
| Event emitted with a name in `EVENT_SCHEMAS` but missing required payload key(s) | `logger.warning("event '%s' missing required payload keys %s")` (per emit; intentional) |
| Custom event name not in `EVENT_SCHEMAS` | no validation, no warning |
| `_load_plugin` deprecated alias | unchanged from Spec A |

### 5.4 Migration documentation

Append to `docs/migration-0.2-to-0.3.md`:

```markdown
## 0.3.x hardening pass: error hints, event taxonomy, concurrency

- All exceptions now support optional `hint=` and `docs_url=` kwargs;
  built-in error sites use them where appropriate. ``str(exc)`` now
  formats over multiple lines when these are set. If you parse error
  text, switch to reading ``exc.hint`` / ``exc.docs_url`` directly.

- Event taxonomy is now documented in ``docs/event-taxonomy.md`` with a
  declared schema for each builtin event. The schema is advisory
  (warning, not error). New supplemental lifecycle events
  (``session.run.started/completed``, ``memory.inject.*``,
  ``memory.writeback.*``, ``context.assemble.*``) are emitted from the
  default runtime. Existing events are unchanged.

- ``JsonlFileSessionManager`` now serializes IO per session via an
  asyncio.Lock (added if concurrency tests caught corruption).
  Cross-session writes remain parallel.

- ``FileLoggingEventBus`` no longer raises on log-file write errors;
  the inner bus emit always runs first and errors are logged via
  ``logger.error`` (added if IO failure tests caught propagation).
```

### 5.5 Compatibility matrix

| affected surface | impact |
|---|---|
| `except OpenAgentsError as e: ...` | unchanged (new fields default None) |
| `str(exc)` parsers expecting single-line errors | may see multi-line; recommend reading attributes |
| Existing event subscribers | unchanged (no event renamed, no payload key removed) |
| Wildcard `*` event subscribers | receive ~8 additional lifecycle events per run |
| Strict event-payload schema validators | unchanged (no payload key removed; `executor_metadata` already added in Spec A) |
| `JsonlFileSessionManager` users | possible serialization within a single session (no API change; throughput effectively unchanged for single-writer workloads) |
| `FileLoggingEventBus` users | log-file IO failures no longer raise (inner bus always runs first) |
| Custom plugin authors | may opt in to `hint=` / `docs_url=` when raising errors |

## 6. Testing plan

### 6.1 New unit test files

| file | coverage |
|---|---|
| `tests/unit/test_error_hint_format.py` | `OpenAgentsError(msg, hint=..., docs_url=...)`; `str()` formatting; None-fallback |
| `tests/unit/test_near_match_helper.py` | exact match, fuzzy match, no match, empty candidates, threshold behavior |
| `tests/unit/test_loader_unknown_type_hint.py` | `PluginLoadError` for unknown type contains "Did you mean" + sibling list |
| `tests/unit/test_loader_invalid_impl_path_hint.py` | `PluginLoadError` for malformed `impl=` contains the format guidance |
| `tests/unit/test_config_loader_env_var_hint.py` | `ConfigLoadError` for missing env var contains the .env hint |
| `tests/unit/test_event_schema_warns_on_missing_payload.py` | event with missing required payload → caplog has warning; emit succeeds |
| `tests/unit/test_event_taxonomy_schemas_match_emit_calls.py` | every key in `EVENT_SCHEMAS` is grep-able as `emit("name"` somewhere in `openagents/` (drift guard) |
| `tests/unit/test_event_taxonomy_doc_synced.py` | `docs/event-taxonomy.md` parses to the exact event-name set in `EVENT_SCHEMAS` |
| `tests/unit/test_builtin_docstrings_are_three_section.py` | every builtin plugin class has `What:` / `Usage:` / `Depends on:` headers |

### 6.2 New stress / concurrency tests (WP3 core)

| file | scenario |
|---|---|
| `tests/unit/test_jsonl_session_concurrent_append.py` | 100-task concurrent append, order preserved on reload |
| `tests/unit/test_jsonl_session_io_failure_recovery.py` | OSError during open propagates; subsequent appends recover |
| `tests/unit/test_file_logging_io_failure_does_not_break_inner.py` | log write fails; inner emit completes; history complete |
| `tests/unit/test_file_logging_high_frequency_emit.py` | 1000 concurrent emits; no loss |
| `tests/unit/test_chain_memory_child_order.py` | child-order contract |
| `tests/unit/test_retry_executor_cancellation.py` | cancel during backoff propagates |
| `tests/integration/test_concurrent_runs_isolated.py` | parallel `runtime.run` calls; isolated state |

### 6.3 Modified tests

- Any existing assertion of the form `assert str(err) == "<exact text>"` → switch to `assert "<key phrase>" in str(err)` for forward compat with hint lines.
- Any existing test counting events on `*` wildcard subscribers → either filter to specific event names or bump expected counts to include the 8 new lifecycle events.

### 6.4 Coverage

- `pyproject.toml`: bump `fail_under = 92`.
- Run `uv run coverage run -m pytest && uv run coverage report`.
- If 92% not met, backfill per §3.5.2; if still not met, fall back to 91% in PR with rationale.

### 6.5 Regression run

- `uv run pytest -q` (full suite must be green)
- `uv run python examples/quickstart/run_demo.py` (ZhiPu glm-5.1)
- `uv run python examples/research_analyst/run_demo.py`
- `uv run python examples/production_coding_agent/run_demo.py`
- All within 5 minutes.

## 7. Documentation updates

| file | change |
|---|---|
| `docs/event-taxonomy.md` | new — generated from `EVENT_SCHEMAS` |
| `docs/plugin-development.md` | append "Three-section docstring" + "Error hints" + "Event taxonomy" subsections |
| `docs/migration-0.2-to-0.3.md` | append the cleanup-pass section from §5.4 |
| `docs/api-reference.md` | add `hint` / `docs_url` kwargs on `OpenAgentsError`; add `near_match`; add `EVENT_SCHEMAS` |

## 8. Out of scope (explicit deferrals)

- Event renames (e.g., `tool.failed` → `tool.errored`) — deferred to ≥0.4.0 breaking cut.
- Adding new builtins (sqlite session, OTel events bridge) — Spec C.
- Strict schema enforcement (raise instead of warn on schema violations) — future cleanup.
- Property-based testing or fuzzing tools — not introduced.
- Vector memory, approval-gate policy, structured streaming — pre-deferred by kernel-completeness spec.
- Full audit of every builtin's concurrency contract — only the 7 stress tests in §3.3.

## 9. Risks and mitigations

| risk | mitigation |
|---|---|
| Multi-line `str(exc)` breaks log-aggregator regexes | Keep first line identical to old format; `hint:` / `docs:` lines indented; document the change in migration doc |
| New lifecycle events flood wildcard subscribers | Document in compatibility matrix; subscribers should filter by name |
| `EVENT_SCHEMAS` drifts from emit call sites | Drift-guard test (§6.1) greps every schema key against `openagents/` source |
| `docs/event-taxonomy.md` drifts from `EVENT_SCHEMAS` | Doc-sync test (§6.1) parses the markdown table and compares |
| Per-session asyncio.Lock on `JsonlFileSessionManager` introduces deadlock | Lock is per-key (sid); never held across awaits beyond the IO; integration test exercises concurrent runs |
| Coverage 92% target unreachable | Spec authorizes fallback to 91% with PR rationale (§3.5.3) |
| Three-section docstring lint test rejects pre-existing acceptable docs | Implementation plan completes WP4 before enabling the test; test is the **last** thing turned on for that WP |

## 10. Rollout

Single PR-shape, single implementation plan. Order:

1. **WP1 errors** — base class + helper + ~12 sites + tests. Independent.
2. **WP2 event taxonomy** — schema module + bus warning + new lifecycle emits + doc generator + tests. Independent.
3. **WP3 stress tests** — write all 7 tests; run; fix only what fails; commit fixes alongside.
4. **WP4 docstrings** — mechanical rewrite of ~40 classes; turn on lint test last.
5. **WP5 coverage** — bump pyproject; run coverage; backfill or fall back to 91% as needed.
6. **Documentation** — update 4 doc files.

Each WP commits independently. Final commit: full regression sweep + examples.
