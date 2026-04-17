# Debug Logging + Rich Pretty Output — Design

- Status: drafted via brainstorm 2026-04-17; user approved section-by-section (§1–§5)
- Scope: single spec → single implementation plan → single PR-shape
- Non-goals: OTel logs/metrics export (already covered by `OtelEventBusBridge`), structured-log JSON output to files (already covered by `FileLoggingEventBus`), regex/JSONPath redaction, tracing/span instrumentation, non-rich alternative pretty-print backends (textual, colorama), log shipping/rotation.

## 1. Motivation

Two debug-output channels currently exist in the SDK, and both are underdeveloped:

1. **Python stdlib logging** — scattered `logging.getLogger("openagents.*")` calls in `runtime/default_runtime.py`, `llm/base.py`, `plugins/builtin/events/*.py`, `plugins/builtin/session/*.py`, `plugins/builtin/memory/*.py`, `plugins/builtin/tool/mcp_tool.py`, `interfaces/typed_config.py`. No unified configuration entry point, no level-per-logger control, no payload redaction, no pretty rendering. Developers integrating or debugging the SDK see plain `WARNING:openagents:...` lines with no color, no time column, no hierarchy.

2. **Runtime event stream** — `FileLoggingEventBus` writes NDJSON to disk, but there is no "human-readable" console sink. When running a demo or debugging a live run, there is no way to watch `tool.called`/`llm.succeeded`/`session.persisted` events pass by unless you `tail -f` a file and pipe through `jq`.

This spec rounds out both channels in one pass and introduces a small, reusable `openagents/observability/` subpackage as the long-term home for this kind of instrumentation.

### 1.1 What this spec is NOT

- Not a replacement for `FileLoggingEventBus` or `OtelEventBusBridge` — those handle persistence and distributed tracing respectively. The new `RichConsoleEventBus` is a third, independent sink for human eyeballs.
- Not a new kernel seam. Both channels use existing mechanisms (stdlib `logging` module; existing `events` seam contract).
- Not a mandatory dependency change. `rich` is an opt-in extra; users who never set `pretty: true` never import rich.

## 2. High-level plan

| # | What | Where | Optional? |
|---|---|---|---|
| 1 | New subpackage `openagents/observability/` | New top-level dir | No — pure stdlib, always present |
| 2 | New event bus plugin `RichConsoleEventBus` | `plugins/builtin/events/rich_console.py` | Requires `[rich]` extra to render |
| 3 | New `[rich]` pyproject extra | `pyproject.toml` | Opt-in for users; `[dev]` depends on it |
| 4 | `logging` section in `AppConfig` | `config/schema.py` | Optional field; default `None` |
| 5 | `Runtime.from_config` auto-apply hook | `plugins/builtin/runtime/default_runtime.py` | Off by default; opt-in via `auto_configure: true` |
| 6 | Extend `FileLoggingEventBus` with `redact_keys` + `max_value_length` + `exclude_events` + upgrade `include_events`/`exclude_events` to fnmatch globs | `plugins/builtin/events/file_logging.py` | Non-breaking — new optional fields; glob upgrade is superset of exact match |
| 7 | Docs + example updates | `docs/`, `examples/quickstart/agent.json` | — |

**Approach principles:**

- **Library etiquette preserved by default.** `openagents.observability.configure()` only touches the `openagents.*` logger namespace. Users embedding the SDK in a larger app see no behavior change until they explicitly opt in.
- **Opt-in pretty.** `pretty=True` is the only path that imports `rich`. Without it, `configure()` uses a plain `StreamHandler` and never references the `rich` module.
- **Hard failure over silent downgrade.** If a user sets `pretty=True` and `rich` is not installed, `configure()` raises `RichNotInstalledError` with the install hint. Same posture as `mcp_tool` / `mem0_memory`.
- **Shared basecode, separate config surfaces.** The stdlib channel and the event channel share `observability/redact.py` and `observability/_rich.py`, but each has its own configuration schema because their filter semantics differ (logger-name prefix vs event-name glob).

## 3. Module layout

```
openagents/
├─ observability/                        # NEW subpackage
│  ├─ __init__.py                        # public re-exports
│  ├─ config.py                          # LoggingConfig (pydantic) + env parser
│  ├─ logging.py                         # configure() / configure_from_env() / reset_logging()
│  ├─ filters.py                         # PrefixFilter, LevelOverrideFilter, RedactFilter
│  ├─ redact.py                          # redact(payload, keys, max_value_length) pure fn
│  ├─ errors.py                          # RichNotInstalledError
│  └─ _rich.py                           # rich Console factory, RichHandler factory, event row renderer
│                                        # (all rich imports centralized here, wrapped in try/except)
│
├─ plugins/builtin/events/
│  └─ rich_console.py                    # NEW RichConsoleEventBus wrapper
│
├─ config/schema.py                      # +logging: LoggingConfig | None = None on AppConfig
├─ plugins/registry.py                   # +register "events.rich_console"
└─ plugins/builtin/runtime/default_runtime.py
                                         # Runtime.from_config opt-in auto-configure hook
```

### 3.1 Dependency rules

- `observability/` depends on `pydantic` only (no `openagents.plugins`, `openagents.runtime`, or `openagents.interfaces`). It can be imported independently by CLI tooling, test fixtures, or third-party code.
- `plugins/builtin/events/rich_console.py` → `openagents.observability.redact` + `openagents.observability._rich` (one-directional).
- `default_runtime.py` imports `openagents.observability` **only** when `config.logging.auto_configure` is truthy; otherwise the module is not loaded.

## 4. Public API

### 4.1 `openagents.observability` re-exports

```python
from openagents.observability import (
    LoggingConfig,
    configure,
    configure_from_env,
    reset_logging,
    RichNotInstalledError,
)
```

### 4.2 Function signatures

```python
def configure(config: LoggingConfig | None = None) -> None:
    """Install handlers/filters/redactors on the 'openagents' logger tree.

    Idempotent: repeated calls first remove previously-installed OpenAgents
    handlers (those tagged with _openagents_installed=True) before adding
    new ones. Never touches the root logger or any logger outside the
    'openagents.*' namespace.

    If config is None, falls back to configure_from_env().
    Raises RichNotInstalledError when config.pretty=True and rich is missing.
    """

def configure_from_env() -> None:
    """Build a LoggingConfig from OPENAGENTS_LOG_* env vars, then configure()."""

def reset_logging() -> None:
    """Remove all OpenAgents-installed handlers and filters. For tests and Runtime.reload()."""
```

### 4.3 `LoggingConfig` fields

```python
class LoggingConfig(BaseModel):
    auto_configure: bool = False
    level: str = "INFO"
    per_logger_levels: dict[str, str] = Field(default_factory=dict)
    pretty: bool = False
    stream: Literal["stdout", "stderr"] = "stderr"
    include_prefixes: list[str] | None = None
    exclude_prefixes: list[str] = Field(default_factory=list)
    redact_keys: list[str] = Field(
        default_factory=lambda: ["api_key", "authorization", "token", "secret", "password"]
    )
    max_value_length: int = 500
    show_time: bool = True
    show_path: bool = False

    @field_validator("level")
    @classmethod
    def _validate_level(cls, v: str) -> str:
        if v.upper() not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}:
            raise ValueError(f"invalid log level: {v}")
        return v.upper()

    @field_validator("per_logger_levels")
    @classmethod
    def _validate_per_logger_levels(cls, v: dict[str, str]) -> dict[str, str]:
        return {k: cls._validate_level.__func__(cls, s) for k, s in v.items()}
```

### 4.4 `RichConsoleEventBus` configuration

```python
class RichConsoleEventBus.Config(BaseModel):
    inner: dict[str, Any] = Field(default_factory=lambda: {"type": "async"})
    include_events: list[str] | None = None
    exclude_events: list[str] = Field(default_factory=list)
    redact_keys: list[str] = Field(
        default_factory=lambda: ["api_key", "authorization", "token", "secret", "password"]
    )
    max_value_length: int = 500
    show_payload: bool = True
    stream: Literal["stdout", "stderr"] = "stderr"
    max_history: int = 10_000     # forwarded to inner if not set there
```

JSON usage:

```json
{
  "events": {
    "type": "rich_console",
    "config": {
      "inner": {"type": "async"},
      "include_events": ["tool.called", "llm.succeeded"],
      "exclude_events": ["*.debug"],
      "show_payload": true
    }
  }
}
```

`include_events` / `exclude_events` support `fnmatch`-style globs (`tool.*`, `*.succeeded`). When both are set, `exclude_events` is applied after `include_events` (deny wins).

Symmetry with `FileLoggingEventBus`:
- Same wrapper shape (`inner` + delegate `subscribe`/`emit`/`get_history`/`clear_history`).
- Shared field names where semantics match (`include_events`, `redact_keys`, `max_value_length`).
- Construction via decorator `@event_bus("rich_console")`.

## 5. Configuration sources and precedence

### 5.1 Three sources

```
agent.json "logging" section  ─┐
                               ├─► LoggingConfig ─► configure(config)
OPENAGENTS_LOG_* env vars   ───┘   (env overrides file)
```

### 5.2 Environment variables

| Var | Type | Overrides field |
|---|---|---|
| `OPENAGENTS_LOG_AUTOCONFIGURE` | `0/1` | `auto_configure` |
| `OPENAGENTS_LOG_LEVEL` | level name | `level` |
| `OPENAGENTS_LOG_LEVELS` | `"openagents.llm=DEBUG,openagents.events=INFO"` | `per_logger_levels` |
| `OPENAGENTS_LOG_PRETTY` | `0/1` | `pretty` |
| `OPENAGENTS_LOG_STREAM` | `stdout/stderr` | `stream` |
| `OPENAGENTS_LOG_INCLUDE` | `"openagents.llm,openagents.events"` | `include_prefixes` |
| `OPENAGENTS_LOG_EXCLUDE` | comma list | `exclude_prefixes` |
| `OPENAGENTS_LOG_REDACT` | comma list | `redact_keys` |
| `OPENAGENTS_LOG_MAX_VALUE_LENGTH` | int | `max_value_length` |

### 5.3 Precedence

```
env vars (only if set)  >  agent.json logging section  >  LoggingConfig defaults
```

Unset env vars do not override. `""` counts as unset.

### 5.4 Invocation paths

```python
# A — demo/CLI user, auto via config file
Runtime.from_config("agent.json")
  # -> if config.logging and config.logging.auto_configure:
  #      observability.configure(config.logging)

# B — embedded in host app, explicit
from openagents.observability import configure, LoggingConfig
configure(LoggingConfig(level="DEBUG", pretty=True))
runtime = Runtime.from_config("agent.json")   # auto_configure=False, no-op

# C — CI / ad-hoc, env-only
OPENAGENTS_LOG_AUTOCONFIGURE=1 OPENAGENTS_LOG_LEVEL=DEBUG uv run python examples/quickstart/run_demo.py
```

## 6. Data flow

### 6.1 Stdlib channel

```
logger.info("assembling context", extra={"agent": "a1", "session": "s1"})
        │
        ▼
'openagents' logger (effective level from per_logger_levels or root level)
  ├─ PrefixFilter        (include/exclude_prefixes)
  ├─ LevelOverrideFilter (per_logger_levels)
  └─ RedactFilter        (redact_keys on record.__dict__ extras)
        │
        ▼
  pretty=True? ── no ──► StreamHandler (plain single-line)
        │
        yes
        ▼
  RichHandler (rich.logging) ─► rich.Console(stream=cfg.stream, force_terminal=False)
```

Sample `pretty=True` output:

```
[12:04:31] INFO     context  assembling context  agent=a1 session=s1
[12:04:32] DEBUG    llm      request turn=1 messages=3 tools=4
[12:04:33] WARNING  events   tool.called missing payload key 'agent_id'
```

### 6.2 Event channel

```
await bus.emit("tool.called", agent_id="a1", tool="bash", arguments={"cmd": "ls"}, call_id="c42")
        │
        ▼
RichConsoleEventBus.emit():
  1. event = await inner.emit(...)           # let inner dispatch first
  2. include/exclude_events filter
  3. payload = redact(payload, cfg)
  4. row = _rich.render_event_row(event, show_payload=cfg.show_payload)
  5. console.print(row)                      # rendering failures logged + swallowed
```

Sample output (`show_payload=True`):

```
┌── 12:04:33.102  tool.called ────────────────────────┐
│ agent_id  = "a1"                                    │
│ tool      = "bash"                                  │
│ arguments = {"cmd": "ls"}                           │
│ call_id   = "c42"                                   │
└─────────────────────────────────────────────────────┘
12:04:33.145  tool.succeeded   tool=bash call_id=c42  duration=43ms
12:04:33.201  llm.chunk        agent_id=a1 delta="thinking..." (truncated 217 chars)
12:04:33.580  llm.succeeded    agent_id=a1 tokens=842  stop_reason=end_turn
```

### 6.3 `redact(payload, keys, max_value_length)` contract

Pure function. Deep-copies input; does not mutate.

1. Case-insensitive key-name match against `redact_keys` → value replaced with `"***"`.
2. String values exceeding `max_value_length` → truncated with `(truncated N chars)` suffix.
3. Nested dict/list recursion; circular references guarded with `"<circular>"`.
4. Non-string, non-dict, non-list scalars (int/float/bool/None) passed through unchanged.

Out of scope (deferred): regex patterns, JSONPath selectors, key-glob patterns.

### 6.4 Shared basecode, independent configs

Both channels use `observability/redact.py` and `observability/_rich.py`. They do **not** share configuration schemas — the stdlib channel filters by logger-name prefix, the event channel filters by event-name glob. Merging the schemas would introduce cognitive overhead ("does `include_prefixes` apply to events?") for no gain.

## 7. Error handling

| Scenario | Behavior |
|---|---|
| `pretty=True` and `rich` not installed | `configure()` raises `RichNotInstalledError("Install rich: pip install io-openagent-sdk[rich]")` at entry |
| `pretty=False` and `rich` not installed | Works normally; `rich` is never imported |
| `per_logger_levels` key outside `openagents.*` | Skip that key; `logger.warning("logger '%s' outside 'openagents.*' namespace is ignored (library etiquette)")`. Do not reject the whole config |
| Invalid `level` string | Pydantic `ValueError` at config validation time |
| `RichConsoleEventBus` render fails (IO, serialization) | `logger.error("rich_console render failed: %s", exc, exc_info=True)`; do NOT disrupt `inner.emit()` — matches `FileLoggingEventBus` posture |
| Repeated `configure()` calls | Idempotent: `reset_logging()` removes handlers tagged with `_openagents_installed=True`, then reinstalls. Third-party handlers untouched |
| `RichConsoleEventBus` without `rich` installed | Loader-time `RichNotInstalledError` (plugin construction fails clearly, same as `mcp_tool` without `mcp`) |

## 8. Testing strategy

All tests ship in the same PR as the source. Coverage gate (`fail_under = 92`) must stay green.

### 8.1 New test tree

```
tests/unit/observability/
├─ test_logging_config.py        # pydantic defaults, env overrides, precedence matrix, invalid values
├─ test_configure.py             # idempotence, namespace isolation, reset, ImportError path
├─ test_filters.py               # PrefixFilter white/blacklist, LevelOverrideFilter, combined
├─ test_redact.py                # case-insensitive keys, nested recursion, circular guard, truncation boundaries, immutability
├─ test_rich_console_bus.py      # (pytest.importorskip("rich")) filters, show_payload modes, render-failure swallow, redact wiring
└─ test_file_logging_extended.py # redact_keys / max_value_length / exclude_events + fnmatch glob behavior on FileLoggingEventBus
```

### 8.2 New integration tests

```
tests/integration/
├─ test_runtime_auto_configure.py  # auto_configure=True triggers configure(); False/absent does not (spy on observability.configure)
└─ test_env_override.py            # monkeypatch OPENAGENTS_LOG_* vars; assert override semantics vs agent.json values
```

### 8.3 Coverage policy

- `openagents/observability/` fully included in coverage.
- `plugins/builtin/events/rich_console.py` included (not in `coverage.omit`) because `rich` is part of `[dev]`; CI covers it.
- The `try: import rich` branch in `_rich.py` covered via `monkeypatch.setitem(sys.modules, "rich", None)` in `test_configure.py::test_pretty_without_rich_raises`.

### 8.4 Docs and example updates

- `docs/developer-guide.md` — new "调试与可观测性" section covering both channels, with env-var reference.
- `docs/configuration.md` — `logging` section field table.
- `docs/seams-and-extension-points.md` — add `rich_console` to the events seam list alongside `file_logging` / `otel_bridge`.
- `examples/quickstart/agent.json` — add `"logging": {"auto_configure": true, "pretty": true, "level": "INFO"}` so `run_demo.py` immediately shows colorized output on first run.

## 9. Packaging changes (`pyproject.toml`)

```toml
[project.optional-dependencies]
rich = [
    "rich>=13.7.0",
]
dev = [
    "coverage[toml]>=7.6.0",
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "io-openagent-sdk[rich]",
]
all = [
    "io-openagent-sdk[mcp,mem0,openai,otel,rich,sqlite,dev,tokenizers,yaml]",
]
```

No additions to `coverage.omit` — rich is installed in dev and CI.

## 10. Deliverables checklist

- [ ] `openagents/observability/__init__.py`, `config.py`, `logging.py`, `filters.py`, `redact.py`, `errors.py`, `_rich.py`
- [ ] `openagents/plugins/builtin/events/rich_console.py`
- [ ] `openagents/plugins/registry.py` registers `events.rich_console`
- [ ] `openagents/config/schema.py` adds `logging: LoggingConfig | None = None`
- [ ] `openagents/plugins/builtin/runtime/default_runtime.py` auto-configure hook
- [ ] `openagents/plugins/builtin/events/file_logging.py` gains `redact_keys`, `max_value_length`, `exclude_events`; `include_events`/`exclude_events` use fnmatch globs (superset of existing exact-match semantics)
- [ ] `pyproject.toml` `[rich]` extra; `[dev]` depends on `[rich]`; `[all]` includes `rich`
- [ ] `tests/unit/observability/*` (6 files) + `tests/integration/test_runtime_auto_configure.py` + `tests/integration/test_env_override.py`
- [ ] `docs/developer-guide.md`, `docs/configuration.md`, `docs/seams-and-extension-points.md` updates
- [ ] `examples/quickstart/agent.json` gets `logging` section
- [ ] Coverage stays ≥ 92%
