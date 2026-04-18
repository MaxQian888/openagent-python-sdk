# Plugin System New Builtins — Selective Additions — Design

- Status: drafted via brainstorm 2026-04-17, autonomous implementation authorized ("按你意思")
- Scope: single spec, single implementation plan, single PR-shape
- Position in roadmap: **Spec C** — final piece of the 3-spec sequence agreed during brainstorm 2026-04-17:
  - **A** (landed 2026-04-17, commits c02ff63 → 9cf1378): cleanup + consistency
  - **B** (landed 2026-04-17, commits 7e980ab → 9731a45): hardening + observability
  - **C** (this spec): selective new builtins
- Non-goals: kernel protocol changes, new seams, breaking changes to existing builtins, additional persistence backends (Postgres/MySQL), OpenTelemetry SDK configuration, OTel logs/metrics support, multi-process OTel context propagation, schema-versioning tooling for SQLite.

## 1. Motivation

After A and B, the plugin system is structurally clean and observably hardened, but two seams still ship a single in-process default that limits real production use:

1. **`session/jsonl_file` is the only persistent option.** It works, but for any agent that needs:
   - Cross-process inspection (analytics tooling reading session state without a Python interpreter)
   - Concurrent reads from many writer processes
   - Indexed lookup by event type / timestamp
   ...users have to write a custom plugin. SQLite is the obvious next backend: stable stdlib bindings, WAL mode for concurrent reads, queryable from any tool.

2. **`events/file_logging` is the only event-export option.** Production observability platforms (Grafana, Honeycomb, Datadog, Tempo) consume OpenTelemetry, not NDJSON. Without a built-in OTel bridge, every team that wants to deploy openagents into a real environment has to write the same span-mapping code.

Both fit the existing seam contract perfectly; both are bounded; both are common enough that the next user encountering the gap shouldn't have to reinvent them. Adding them rounds out 0.3.x as **deployment-ready**, not just **structurally complete**.

### 1.1 What is intentionally **not** here

- The kernel-completeness spec deliberately deferred vector memory, approval-gate execution policy, full LLM-driven summarizing context assembler, and a Postgres session backend. None of those moved to C — they remain Phase 2/3 territory. C is **only** the two builtins listed above.

## 2. High-level plan

Two new builtins. Each ships independently — they share no code path.

| # | seam | new builtin | optional extra | behavior |
|---|---|---|---|---|
| 1 | `session` | `SqliteSessionManager` | `sqlite` (`aiosqlite>=0.20.0`) | WAL-mode SQLite persistence per session_id; per-session asyncio.Lock; replay on first access |
| 2 | `events` | `OtelEventBusBridge` | `otel` (`opentelemetry-api>=1.25.0`) | Wraps inner bus; one OTel span per event; payload flattened to span attributes; OTel-failure swallowed |

**Approach principles:**

- **Optional extras only.** Neither is added to the base install. `aiosqlite` and `opentelemetry-api` are extras under `[project.optional-dependencies]`, matching the existing posture for `mem0` and `mcp`.
- **Coverage exempt.** Both files are added to the existing `[tool.coverage.report] omit` list (alongside `mem0_memory.py` and `mcp_tool.py`). The 92% floor stays intact.
- **Sibling-pattern conformance.** Each new builtin follows the conventions established by Spec A and Spec B: `TypedConfigPluginMixin` + nested `class Config(BaseModel)`, three-section docstring, `unwrap_tool_result` / `EVENT_SCHEMAS` compatibility, hint-bearing errors via Spec B's `OpenAgentsError` extensions.
- **Zero behavior change for non-adopters.** A user who never opts into the extras sees no diff in any existing test, demo, or runtime path.
- **Patch release.** Lands on 0.3.x; no breaking cut.

## 3. Component specs

### 3.1 `session/sqlite` — `SqliteSessionManager`

#### 3.1.1 New file `openagents/plugins/builtin/session/sqlite_backed.py`

```python
"""SQLite-backed session manager (optional extra: 'sqlite')."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from openagents.errors.exceptions import PluginLoadError, SessionError
from openagents.interfaces.session import (
    SESSION_ARTIFACTS,
    SESSION_CHECKPOINTS,
    SESSION_MANAGE,
    SESSION_STATE,
    SESSION_TRANSCRIPT,
    SessionArtifact,
    SessionCheckpoint,
    SessionManagerPlugin,
    _ARTIFACTS_KEY,
    _CHECKPOINTS_KEY,
    _TRANSCRIPT_KEY,
)
from openagents.interfaces.typed_config import TypedConfigPluginMixin

try:
    import aiosqlite
    _HAS_AIOSQLITE = True
except ImportError:
    aiosqlite = None  # type: ignore[assignment]
    _HAS_AIOSQLITE = False

logger = logging.getLogger("openagents.session.sqlite")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    sid TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    sid TEXT NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    ts TEXT NOT NULL,
    FOREIGN KEY (sid) REFERENCES sessions(sid)
);

CREATE INDEX IF NOT EXISTS idx_events_sid_seq ON events(sid, seq);
"""


class SqliteSessionManager(TypedConfigPluginMixin, SessionManagerPlugin):
    """SQLite-backed session manager.

    What:
        Each mutation INSERTs one row into ``events`` with type
        ('transcript' | 'artifact' | 'checkpoint' | 'state'), JSON
        payload, and ISO timestamp. WAL mode + per-session asyncio.Lock
        gives concurrent reads safely while serializing writes per
        session. On first access prior rows are replayed to rebuild
        in-memory state.

    Usage:
        ``{"session": {"type": "sqlite", "config": {"db_path":
        ".sessions/agent.db", "wal": true, "synchronous": "NORMAL"}}}``
        Requires the ``sqlite`` extra: ``uv sync --extra sqlite``.

    Depends on:
        - the optional ``aiosqlite`` PyPI package
        - filesystem at ``db_path`` (parent dir created on init)
    """

    class Config(BaseModel):
        db_path: str
        wal: bool = True
        synchronous: Literal["OFF", "NORMAL", "FULL"] = "NORMAL"
        busy_timeout_ms: int = 5_000

    def __init__(self, config: dict[str, Any] | None = None):
        if not _HAS_AIOSQLITE:
            raise PluginLoadError(
                "session 'sqlite' requires the 'aiosqlite' package",
                hint="Install the 'sqlite' extra: uv sync --extra sqlite",
            )
        super().__init__(
            config=config or {},
            capabilities={
                SESSION_MANAGE,
                SESSION_STATE,
                SESSION_TRANSCRIPT,
                SESSION_ARTIFACTS,
                SESSION_CHECKPOINTS,
            },
        )
        self._init_typed_config()
        self._db_path = Path(self.cfg.db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, asyncio.Lock] = {}
        self._states: dict[str, dict[str, Any]] = {}
        self._loaded: set[str] = set()
        self._init_lock = asyncio.Lock()
        self._initialized = False

    async def _ensure_db(self) -> None:
        async with self._init_lock:
            if self._initialized:
                return
            async with aiosqlite.connect(self._db_path) as db:
                await db.executescript(_SCHEMA)
                if self.cfg.wal:
                    await db.execute("PRAGMA journal_mode=WAL")
                await db.execute(f"PRAGMA synchronous = {self.cfg.synchronous}")
                await db.execute(f"PRAGMA busy_timeout = {self.cfg.busy_timeout_ms}")
                await db.commit()
            self._initialized = True

    # ... append_message / save_artifact / create_checkpoint / set_state /
    #     get_state / list_sessions / delete_session / session() implementations
    #     mirror JsonlFileSessionManager but INSERT into 'events' table
    #     and SELECT for replay. Lock acquisition matches jsonl_file.
```

The implementation plan completes the method bodies; the spec locks the public surface and the schema.

#### 3.1.2 Capability set

Identical to `InMemorySessionManager` and `JsonlFileSessionManager`:

```python
{SESSION_MANAGE, SESSION_STATE, SESSION_TRANSCRIPT, SESSION_ARTIFACTS, SESSION_CHECKPOINTS}
```

#### 3.1.3 Replay semantics

On first `get_state(sid)` or `session(sid)` entry: if the session has any rows in `events`, replay all `(type, payload)` pairs in `seq` order onto a fresh in-memory dict (matching the structure JsonlFileSessionManager uses). Mark `sid in self._loaded` to skip on subsequent access.

#### 3.1.4 Error wrapping

Any `aiosqlite.Error` raised during a mutation gets caught at the top of each public method and re-raised as `SessionError(str(exc), hint="...")` with a contextual hint (e.g. `"check disk space and write permissions on db_path"`). Replay errors from individual rows log a warning and skip (consistent with jsonl_file's bad-line skip behavior).

### 3.2 `events/otel_bridge` — `OtelEventBusBridge`

#### 3.2.1 New file `openagents/plugins/builtin/events/otel_bridge.py`

```python
"""OpenTelemetry tracing bridge for SDK events (optional extra: 'otel')."""

from __future__ import annotations

import fnmatch
import json
import logging
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, Field

from openagents.errors.exceptions import PluginLoadError
from openagents.interfaces.events import (
    EVENT_EMIT,
    EVENT_HISTORY,
    EVENT_SUBSCRIBE,
    EventBusPlugin,
    RuntimeEvent,
)
from openagents.interfaces.typed_config import TypedConfigPluginMixin

try:
    from opentelemetry import trace as otel_trace
    _HAS_OTEL = True
except ImportError:
    otel_trace = None  # type: ignore[assignment]
    _HAS_OTEL = False

logger = logging.getLogger("openagents.events.otel_bridge")


class OtelEventBusBridge(TypedConfigPluginMixin, EventBusPlugin):
    """OpenTelemetry tracing bridge for SDK events.

    What:
        Wraps another event bus. For each emit, creates a one-shot
        OTel span named ``openagents.<event_name>`` with payload
        flattened into span attributes (``oa.<key>=<json-or-str>``).
        Long values are truncated to ``max_attribute_chars``. Inner
        bus.emit always runs first, so subscribers and other
        wrappers (file_logging) are unaffected by OTel failures.

    Usage:
        ``{"events": {"type": "otel_bridge", "config": {"inner":
        {"type": "async"}, "tracer_name": "openagents",
        "include_events": ["tool.*", "llm.*"], "max_attribute_chars":
        4096}}}``. Requires the ``otel`` extra and that the host
        process has already configured an OTel TracerProvider (see
        opentelemetry-sdk docs). If no TracerProvider is configured,
        the OTel API no-ops and this bridge becomes free.

    Depends on:
        - the optional ``opentelemetry-api`` PyPI package
        - a globally configured OTel TracerProvider in the host
          process (provided by the user via opentelemetry-sdk)
        - inner event bus loaded via load_plugin
    """

    class Config(BaseModel):
        inner: dict[str, Any] = Field(default_factory=lambda: {"type": "async"})
        tracer_name: str = "openagents"
        include_events: list[str] | None = None
        max_attribute_chars: int = 4_096
        max_history: int = 10_000

    def __init__(self, config: dict[str, Any] | None = None):
        if not _HAS_OTEL:
            raise PluginLoadError(
                "events 'otel_bridge' requires the 'opentelemetry-api' package",
                hint="Install the 'otel' extra: uv sync --extra otel; "
                     "also configure a TracerProvider via opentelemetry-sdk",
            )
        super().__init__(
            config=config or {},
            capabilities={EVENT_SUBSCRIBE, EVENT_EMIT, EVENT_HISTORY},
        )
        self._init_typed_config()
        self._tracer = otel_trace.get_tracer(self.cfg.tracer_name)
        inner_ref = dict(self.cfg.inner)
        inner_cfg = dict(inner_ref.get("config") or {})
        inner_cfg.setdefault("max_history", self.cfg.max_history)
        inner_ref["config"] = inner_cfg
        self._inner = self._load_inner(inner_ref)

    def _load_inner(self, ref: dict[str, Any]) -> Any:
        from openagents.config.schema import EventBusRef
        from openagents.plugins.loader import load_plugin

        return load_plugin("events", EventBusRef(**ref), required_methods=("emit", "subscribe"))

    def _matches_include(self, name: str) -> bool:
        if self.cfg.include_events is None:
            return True
        return any(fnmatch.fnmatchcase(name, pat) for pat in self.cfg.include_events)

    def _flatten_attribute(self, key: str, value: Any) -> tuple[str, str]:
        if isinstance(value, (str, int, float, bool)) or value is None:
            v = str(value)
        else:
            try:
                v = json.dumps(value, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                v = repr(value)
        if len(v) > self.cfg.max_attribute_chars:
            v = v[: self.cfg.max_attribute_chars] + "...[truncated]"
        return f"oa.{key}", v

    def subscribe(self, event_name: str, handler: Callable[[RuntimeEvent], Awaitable[None] | None]) -> None:
        self._inner.subscribe(event_name, handler)

    async def emit(self, event_name: str, **payload: Any) -> RuntimeEvent:
        # Inner bus always runs first; it must not be blocked by OTel issues.
        event = await self._inner.emit(event_name, **payload)

        if not self._matches_include(event_name):
            return event

        try:
            with self._tracer.start_as_current_span(f"openagents.{event_name}") as span:
                for k, v in payload.items():
                    attr_k, attr_v = self._flatten_attribute(k, v)
                    span.set_attribute(attr_k, attr_v)
        except Exception as exc:  # noqa: BLE001 - OTel SDK exceptions vary; never break inner emit
            logger.error("otel_bridge: failed to emit span for %s: %s", event_name, exc)

        return event

    async def get_history(self, event_name: str | None = None, limit: int | None = None) -> list[RuntimeEvent]:
        return await self._inner.get_history(event_name=event_name, limit=limit)

    async def clear_history(self) -> None:
        await self._inner.clear_history()
```

#### 3.2.2 Span shape

- Name: `openagents.<event_name>` (e.g. `openagents.tool.succeeded`)
- Attributes: `oa.<payload_key>` for each payload key, value serialized as described in `_flatten_attribute`
- Duration: spans are short-lived (one-shot, zero work inside the `with` block); OTel records them with start/end nearly equal
- Future evolution: pairing `session.run.started` / `session.run.completed` into one parent span is **out of scope** for this spec; documented as future work in §6.

#### 3.2.3 Wildcard `include_events`

`fnmatch` style: `"tool.*"` matches `tool.called`, `tool.succeeded`, `tool.failed`, etc. Case-sensitive. `None` (default) means all events.

### 3.3 Wiring

#### 3.3.1 `pyproject.toml` additions

```toml
[project.optional-dependencies]
mem0 = ["mem0ai>=0.0.20"]      # existing
mcp = [...]                    # existing
sqlite = ["aiosqlite>=0.20.0"]   # NEW
otel = ["opentelemetry-api>=1.25.0"]  # NEW

[tool.coverage.report]
fail_under = 92
omit = [
    "openagents/plugins/builtin/memory/mem0_memory.py",
    "openagents/plugins/builtin/tool/mcp_tool.py",
    "openagents/plugins/builtin/session/sqlite_backed.py",   # NEW
    "openagents/plugins/builtin/events/otel_bridge.py",       # NEW
]
```

#### 3.3.2 `openagents/plugins/registry.py` additions

```python
from openagents.plugins.builtin.session.sqlite_backed import SqliteSessionManager
from openagents.plugins.builtin.events.otel_bridge import OtelEventBusBridge

# in _BUILTIN_REGISTRY:
"session": {
    "in_memory": InMemorySessionManager,
    "jsonl_file": JsonlFileSessionManager,
    "sqlite": SqliteSessionManager,   # NEW
},
"events": {
    "async": AsyncEventBus,
    "file_logging": FileLoggingEventBus,
    "otel_bridge": OtelEventBusBridge,   # NEW
},
```

The `_BUILTIN_REGISTRY` registration triggers at import time — but the `__init__` itself will raise `PluginLoadError` only if a user **constructs** the plugin without the extra installed. Just importing the module is safe (the conditional import at top sets `_HAS_AIOSQLITE = False` instead of raising).

## 4. Data flow

### 4.1 SQLite session

```
runtime.session_manager.session(sid) async-context
  ├─ acquire per-sid asyncio.Lock
  ├─ if sid not in _loaded:
  │     await self._ensure_db()
  │     SELECT type,payload FROM events WHERE sid=? ORDER BY seq
  │     replay each row onto _states[sid] (transcript / artifacts / checkpoints / state keys)
  │     _loaded.add(sid)
  ├─ yield _states[sid]
  └─ release lock

# A mutation looks like:
runtime.session_manager.append_message(sid, message)
  ├─ acquire per-sid asyncio.Lock
  ├─ load if needed (above)
  ├─ INSERT INTO events(sid, type, payload, ts)
  │   VALUES (?, 'transcript', json.dumps(message), iso_now())
  ├─ mutate in-memory _states[sid][_TRANSCRIPT_KEY] in place
  └─ release lock
```

Different sessions write in parallel; same session serialized. SQLite's own locking + WAL handles cross-process and cross-connection concurrency.

### 4.2 OTel bridge

```
pattern.emit("tool.succeeded", tool_id="x", result=...)
  └─ OtelEventBusBridge.emit("tool.succeeded", **payload)
       ├─ event = await self._inner.emit(...)         # always runs; subscribers/file_logging unaffected
       ├─ if not include match: return event
       ├─ try:
       │   with tracer.start_as_current_span("openagents.tool.succeeded") as span:
       │       for k, v in payload.items(): span.set_attribute(f"oa.{k}", _truncate(_serialize(v)))
       ├─ except Exception: logger.error(...); pass
       └─ return event
```

Span lifecycle is fully synchronous within the `with` block; no work happens outside. OTel SDK (if configured by user) handles batching/export downstream.

## 5. Error handling and migration

### 5.1 New exception types

None. SQLite errors wrap as `SessionError`; OTel errors are swallowed with `logger.error`.

### 5.2 Failure modes

| condition | behavior |
|---|---|
| User uses `type: "sqlite"` without `aiosqlite` installed | `PluginLoadError` at construction with `hint="uv sync --extra sqlite"` |
| User uses `type: "otel_bridge"` without `opentelemetry-api` installed | `PluginLoadError` at construction with `hint="uv sync --extra otel; also configure TracerProvider"` |
| `aiosqlite.Error` during INSERT or SELECT | `SessionError(str(exc), hint=...)` raised |
| Bad JSON row during replay | `logger.warning("sqlite_session: skipped bad row seq=%d in %s")` and continue |
| OTel API call raises (e.g. attribute too long beyond OTel SDK limits) | `logger.error("otel_bridge: failed to emit span ...")`, inner bus emit was already done |
| `include_events` pattern compiles to nothing | All events skip OTel spans; inner bus still runs |

### 5.3 Compatibility matrix

| affected surface | impact |
|---|---|
| Default base install | unchanged (no new required deps) |
| Existing `JsonlFileSessionManager` users | unchanged |
| Existing `FileLoggingEventBus` users | unchanged |
| Existing wildcard event subscribers | unchanged (OTel bridge wraps, doesn't re-emit through subscribe API) |
| Existing event payloads | unchanged (OTel only **reads** payload, never mutates) |
| Coverage floor (92%) | unchanged (new files in `omit`) |
| `openagents schema` CLI | now lists 2 extra Config schemas |
| `openagents list-plugins` CLI | now lists `sqlite` under session and `otel_bridge` under events |

### 5.4 Migration documentation

Append to `docs/migration-0.2-to-0.3.md`:

```markdown
## 0.3.x extras: sqlite session + otel_bridge events

- New optional builtin ``session/sqlite`` (``SqliteSessionManager``).
  Install: ``uv sync --extra sqlite`` (adds ``aiosqlite``).
  Drop-in replacement for ``jsonl_file`` when you need indexed query
  or cross-process readers. Schema is single-version; persisted data
  from 0.3.x is not guaranteed to be readable by future major versions.

- New optional builtin ``events/otel_bridge``
  (``OtelEventBusBridge``). Install: ``uv sync --extra otel`` (adds
  ``opentelemetry-api``). You also need an OTel TracerProvider
  configured by the host process (typically via
  ``opentelemetry-sdk`` + an exporter). Without a TracerProvider the
  OTel API no-ops and the bridge becomes free.
```

## 6. Testing plan

### 6.1 SQLite session — 5 new tests (3 unit + 1 integration + 1 import-fallback)

| file | scenario |
|---|---|
| `tests/unit/test_sqlite_session_basic_roundtrip.py` | append_message / save_artifact / create_checkpoint / set_state — read back via fresh manager from same db_path |
| `tests/unit/test_sqlite_session_replay_on_reopen.py` | populate session, close manager, instantiate new manager pointing at same db_path, assert state fully reconstructed |
| `tests/unit/test_sqlite_session_concurrent_writes.py` | 50 concurrent `append_message` via `asyncio.gather`; reload via fresh manager; `seq` order matches submission order |
| `tests/unit/test_sqlite_session_extra_missing_raises.py` | monkeypatch `_HAS_AIOSQLITE = False`; assert `PluginLoadError("requires the 'aiosqlite' package")` with hint |
| `tests/integration/test_sqlite_session_with_real_runtime.py` | runtime configured with sqlite session; run twice; second run sees first run's transcript via replay |

### 6.2 OTel bridge — 4 new tests

| file | scenario |
|---|---|
| `tests/unit/test_otel_bridge_emits_span_per_event.py` | use `opentelemetry.sdk.trace.export.in_memory_span_exporter.InMemorySpanExporter` (only in this test, dev-only); after a few `bus.emit(...)` calls assert exported spans have correct names + `oa.*` attributes |
| `tests/unit/test_otel_bridge_attribute_truncation.py` | emit with a long string in payload; assert span attribute ends with `...[truncated]` and length ≤ `max_attribute_chars + 14` |
| `tests/unit/test_otel_bridge_include_filter_wildcards.py` | `include_events=["tool.*"]`; emit `tool.called`, `tool.succeeded`, `llm.called`; only first two produce spans; all three are emitted to inner |
| `tests/unit/test_otel_bridge_inner_runs_first_on_otel_failure.py` | monkeypatch `tracer.start_as_current_span` to raise; assert inner bus still received emit; assert `caplog` has `otel_bridge: failed to emit` |

For OTel tests, install `opentelemetry-sdk` as a **dev-only** dependency (not a runtime extra). The runtime still depends only on `opentelemetry-api`.

### 6.3 CLI smoke

Extend `tests/unit/test_cli_schema.py` (or closest equivalent):

- `openagents list-plugins` output includes `session.sqlite` and `events.otel_bridge`
- `openagents schema` output includes Config schemas for both

### 6.4 Coverage

- New files added to `[tool.coverage.report] omit`
- `fail_under = 92` unchanged
- The 9 new tests verify correctness without affecting the floor

### 6.5 Regression

- `uv run pytest -q` — full suite green (~599 tests after the additions)
- `uv run python examples/quickstart/run_demo.py` (real ZhiPu glm-5.1)
- `uv run python examples/research_analyst/run_demo.py`
- `uv run python examples/production_coding_agent/run_demo.py`
- All within 5 minutes

## 7. Documentation updates

| file | change |
|---|---|
| `docs/configuration.md` | append "session.sqlite" and "events.otel_bridge" config sections with examples |
| `docs/event-taxonomy.md` | append a "OpenTelemetry mapping" section explaining `event_name` → span name and `payload key` → `oa.<key>` attribute |
| `docs/plugin-development.md` | append "Optional extras" subsection: how to declare them in `pyproject.toml`, fail-soft import pattern, hint-bearing `PluginLoadError` |
| `docs/migration-0.2-to-0.3.md` | append the section from §5.4 |
| `docs/api-reference.md` | append SqliteSessionManager + OtelEventBusBridge to the builtin index |

## 8. Out of scope (explicit deferrals)

- Postgres / MySQL session backends — single new persistence backend per spec; defer to user demand
- OTel SDK default configuration — host process responsibility
- OTel logs / metrics support — only spans (matches event semantics)
- Pairing `session.run.started/completed` into a parent span — design future work
- Multi-process OTel context propagation — agent SDK is single-process
- SQLite schema migration tooling — schema is single-version; future breaking changes get their own ticket
- OpenTelemetry semantic conventions for AI workloads — emerging spec, not yet stable; revisit when GA
- Generic "event_bus.attribute_filter" plugin — narrow case; if needed, build on top of otel_bridge

## 9. Risks and mitigations

| risk | mitigation |
|---|---|
| Users install `sqlite` extra but their environment ships an old aiosqlite | Pin `aiosqlite>=0.20.0` in optional-dep spec; tested CI version locked |
| OTel API/SDK version skew (API 1.25 vs SDK 1.20) | Pin only the `api` floor; document SDK version is user's choice; OTel guarantees API/SDK protocol stability across minor versions |
| SQLite DB file corrupt mid-write | WAL mode + `synchronous=NORMAL` default; users wanting maximum durability set `synchronous=FULL` |
| Per-session asyncio.Lock dictionary leaks across long-lived sessions | Acceptable — `_locks` is bounded by active session count; integration test exercises long-lived session pattern |
| OTel span burst at high event rates degrades performance | OTel SDK's BatchSpanProcessor handles batching/dropping; bridge itself is O(1) per emit |
| Truncation hides important payload data in OTel | `max_attribute_chars` defaults to 4096 (large enough for typical tool results); user can raise if needed |
| Drift between sqlite schema and replay code | `_SCHEMA` constant + replay code in same file; integration test verifies round-trip |
| `start_as_current_span` accidentally creates parent-child relationships across unrelated events | Each emit is a one-shot span using `start_as_current_span` only within its `with` block; no implicit nesting since events emit serially in single async loop |

## 10. Rollout

Single PR-shape, single implementation plan. Order:

1. **`pyproject.toml`** — add `[project.optional-dependencies] sqlite` and `otel`; add both new files to `omit`. Lands first because everything else imports through it.
2. **`SqliteSessionManager`** + 5 tests + opt-in CI verification (install extra → run targeted tests).
3. **`OtelEventBusBridge`** + 4 tests + opt-in CI verification (install both extras → run targeted tests).
4. **Registry wiring** — append to `_BUILTIN_REGISTRY`.
5. **CLI smoke** — extend test_cli_schema.py.
6. **Docs** — 5 doc files updated.
7. **Final regression** — full pytest, coverage, three demos.

Each step commits independently. Tests for new builtins skip cleanly when extras not installed (use `pytest.importorskip("aiosqlite")` etc.) so the default test run still works without installing extras.
