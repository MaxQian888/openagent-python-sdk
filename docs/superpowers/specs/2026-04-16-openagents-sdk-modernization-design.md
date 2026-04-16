# OpenAgents SDK Modernization Design

## Goal

Modernize `openagent-python-sdk` from a loosely typed config-and-runtime kernel into a typed, validated, dependency-injectable SDK that is easier to extend, safer to debug, and clearer to operate.

The target outcome for `0.2.0` is:

- Pydantic-based config and runtime models instead of hand-written dataclass parsers
- typed local dependency injection for tools and patterns
- explicit plugin loading contracts instead of silent constructor fallback
- structured, contextual SDK errors instead of ad-hoc exceptions and hidden failures
- enforced execution budgets and visible suppressed-error logging

## Ground Truth Boundary

This spec does **not** turn OpenAgents into a graph runtime or a multi-agent orchestration framework.

The SDK remains a **single-agent execution kernel**:

- one `Runtime.run(...)` executes one `agent_id`
- app/product semantics still live above the SDK
- session state, context assembly, tools, memory, and pattern seams remain the extension model
- no hidden DI container, workflow engine, or graph compiler is introduced

## Current Repository Truth

The current repo shape shows six concrete pressure points:

1. `openagents/config/schema.py`
   - ~400 lines of dataclasses and repeated `from_dict()` boilerplate
   - `PluginRef` subclasses differ mostly by field name and validation repetition
   - `MemoryRef.on_error` is an untyped string

2. `openagents/config/loader.py`
   - `load_config_dict()` still relies on `AppConfig.from_dict(...)` + separate `validate_config(...)`

3. `openagents/interfaces/runtime.py`, `pattern.py`, `tool.py`
   - runtime contracts are dataclasses with many `Any` fields
   - `RunResult.exception` is `Exception | None`
   - `stop_reason` is a magic string
   - tools still receive `context: Any`
   - pattern state lives in `ExecutionContext`, which is broad and weakly typed

4. `openagents/plugins/loader.py`
   - `_instantiate()` swallows `TypeError` while trying multiple constructor shapes
   - capability checks happen after instantiation

5. `openagents/decorators.py` + `openagents/plugins/registry.py`
   - decorator registration silently overwrites previous decorator registrations
   - decorator names that collide with builtin plugin names are not surfaced explicitly
   - builtin lookup currently wins first, so some collisions are effectively hidden

6. `openagents/plugins/builtin/runtime/default_runtime.py` and `plugins/builtin/events/async_event_bus.py`
   - memory failures under `on_error="continue"` are emitted as events but not logged
   - event handler exceptions currently break handler iteration
   - `RunBudget` exists, but central enforcement is incomplete

The package metadata also shows that the current published baseline is still early:

- `pyproject.toml` version: `0.1.1`
- core dependency set: only `httpx[http2]>=0.28.1`

## External Design Signals

This design is intentionally informed by current Python agent SDK patterns rather than invented in isolation.

### Pydantic v2

Pydantic v2 already supports:

- `BaseModel` as the primary validation surface
- generic models via `class Model(BaseModel, Generic[T]): ...`
- `model_validate()` / `model_dump()` / `model_json_schema()`

That makes it a strong fit for replacing the current manual parsing layer and for introducing a generic `RunContext[DepsT]`.

### Pydantic AI

Pydantic AI provides two particularly strong ideas worth borrowing:

- `RunContext[DepsT]` for typed local dependency injection
- `ModelRetry` / retry-feedback style exceptions for tool-to-model correction loops

The dependency model is especially relevant because OpenAgents also needs to pass local-only runtime state to tools without exposing it to the LLM.

### OpenAI Agents SDK

OpenAI Agents’ `RunContextWrapper[TContext]` reinforces the same local-context principle:

- app-owned dependencies are passed to code, not the model
- usage tracking lives alongside that local context
- context is a runtime carrier, not an LLM-visible prompt surface

### What We Are Not Borrowing

This spec does **not** adopt:

- LangGraph-style graph execution as the core runtime abstraction
- a full dependency-injection container
- a middleware stack that hides the existing plugin seams

Those patterns solve a different scope than the one this repository currently occupies.

## Design Overview

`0.2.0` introduces seven coordinated changes:

1. redesign the exception hierarchy
2. migrate config models to Pydantic
3. migrate runtime data objects to Pydantic
4. introduce typed `RunContext[DepsT]`
5. make plugin loading explicit and reliable
6. remove silent runtime failure paths
7. ship as a clean pre-1.0 breaking release

These changes are meant to land together in one coherent cut rather than as partial compatibility layers.

---

## 1. Error Handling Redesign

### Current Problem

The SDK currently has a thin exception surface:

- `OpenAgentsError`
- `ConfigError`
- `PluginLoadError`
- `CapabilityError`
- tool-local `ToolError` variants

But runtime failures still frequently escape as raw `Exception`, `RuntimeError`, `ValueError`, or silently suppressed side effects.

### Decision

Introduce one explicit error tree under `OpenAgentsError`:

```text
OpenAgentsError
├── ConfigError
│   ├── ConfigValidationError
│   └── ConfigLoadError
├── PluginError
│   ├── PluginLoadError
│   ├── PluginCapabilityError
│   └── PluginConfigError
├── ExecutionError
│   ├── MaxStepsExceeded
│   ├── BudgetExhausted
│   ├── SessionError
│   └── PatternError
├── ToolError
│   ├── RetryableToolError
│   ├── PermanentToolError
│   ├── ToolTimeoutError
│   └── ToolNotFoundError
├── LLMError
│   ├── LLMConnectionError
│   ├── LLMRateLimitError
│   ├── LLMResponseError
│   └── ModelRetryError
└── UserError
    ├── InvalidInputError
    └── AgentNotFoundError
```

### Structured Context on Errors

Every `OpenAgentsError` gains optional runtime metadata:

```python
class OpenAgentsError(Exception):
    agent_id: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    tool_id: str | None = None
    step_number: int | None = None

    def with_context(self, **kwargs) -> Self: ...
```

This allows:

- `RunResult.exception` to be strongly typed
- logs to carry the same identifiers as runtime events
- downstream callers to branch on SDK-specific failures without string matching

### ModelRetryError

Add `ModelRetryError` as an SDK-level signal that a tool or validation path can raise when it wants the model to retry with corrected input.

This does **not** require a full new planner architecture. It is a narrow feedback primitive for:

- malformed tool parameters
- missing structured output fields
- repairable output contract violations

## 2. Pydantic Migration — Config System

### Current Problem

`openagents/config/schema.py` currently combines:

- schema definition
- input parsing
- validation normalization
- defaulting
- repeated `dict`/`str` checking

This makes the config layer verbose and hard to evolve.

### Decision

Replace config dataclasses with Pydantic v2 `BaseModel` classes.

Representative direction:

```python
class LLMOptions(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: str = "mock"
    model: str | None = None
    api_base: str | None = None
    api_key_env: str | None = None
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: PositiveInt | None = None
    timeout_ms: PositiveInt = 30000
    stream_endpoint: str | None = None
```

### Config Rules

- `load_config_dict()` becomes a thin wrapper around `AppConfig.model_validate(payload)`
- JSON file loading stays in `config/loader.py`
- config-layer `ValidationError` is wrapped into `ConfigValidationError`
- file IO / JSON parse problems are wrapped into `ConfigLoadError`
- JSON Schema export becomes a first-class supported outcome via `AppConfig.model_json_schema()`

### PluginRef Simplification

Collapse repeated `*Ref.from_dict()` patterns into a common model:

```python
class PluginRef(BaseModel):
    type: str | None = None
    impl: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_selector(self) -> Self:
        if not self.type and not self.impl:
            raise ValueError("must specify either 'type' or 'impl'")
        if self.type and self.impl:
            raise ValueError("must specify only one of 'type' or 'impl'")
        return self
```

Subtype models only add real semantics:

```python
class MemoryRef(PluginRef):
    on_error: Literal["continue", "fail"] = "continue"
```

### Expected Outcome

This removes:

- manual `from_dict()` plumbing
- most of `config/validator.py`
- repeated strip/type-check boilerplate

while adding:

- schema export
- better error messages
- IDE completion
- more obvious extension points

## 3. Pydantic Migration — Runtime Objects

### Current Problem

The runtime contract surface is still built from dataclasses:

- `RunBudget`
- `RunArtifact`
- `RunUsage`
- `RunRequest`
- `RunResult`
- `ToolResult`
- `ToolExecutionRequest`
- `ToolExecutionResult`
- `PolicyDecision`
- session artifacts/checkpoints

This works, but it keeps the core SDK in a weakly validated state even after config parsing.

### Decision

Migrate runtime data objects to Pydantic models with `arbitrary_types_allowed=True` where runtime services are attached.

Representative direction:

```python
class RunResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str
    final_output: Any = None
    stop_reason: StopReason = StopReason.COMPLETED
    usage: RunUsage = Field(default_factory=RunUsage)
    artifacts: list[RunArtifact] = Field(default_factory=list)
    error: str | None = None
    exception: OpenAgentsError | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### StopReason Enum

Replace string constants with a public enum:

```python
class StopReason(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    MAX_STEPS = "max_steps"
    BUDGET_EXHAUSTED = "budget_exhausted"
```

### Immutable Session Data

`SessionArtifact` and `SessionCheckpoint` become frozen Pydantic models where practical.

That removes the need to defensively `deepcopy()` session payload containers throughout the runtime path.

## 4. Typed Dependency Injection — RunContext[DepsT]

### Current Problem

Tools currently receive:

```python
async def invoke(self, params: dict[str, Any], context: Any) -> Any: ...
```

Patterns currently rely on `self.context`, but the context object is weakly typed and has no first-class application dependency carrier.

### Decision

Introduce a generic `RunContext[DepsT]` as the public runtime context model.

Representative direction:

```python
DepsT = TypeVar("DepsT")

class RunContext(BaseModel, Generic[DepsT]):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # identity
    agent_id: str
    session_id: str
    run_id: str
    input_text: str

    # app-owned local dependencies
    deps: DepsT | None = None

    # runtime state
    state: dict[str, Any] = Field(default_factory=dict)
    tools: dict[str, ToolPlugin] = Field(default_factory=dict)
    llm_client: Any | None = None
    llm_options: LLMOptions | None = None
    event_bus: EventBusPlugin
    memory_view: dict[str, Any] = Field(default_factory=dict)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    scratch: dict[str, Any] = Field(default_factory=dict)
    transcript: list[dict[str, Any]] = Field(default_factory=list)
    session_artifacts: list[SessionArtifact] = Field(default_factory=list)
    assembly_metadata: dict[str, Any] = Field(default_factory=dict)
    usage: RunUsage | None = None
    artifacts: list[RunArtifact] = Field(default_factory=list)
```

### What Changes Publicly

Tool signature becomes:

```python
async def invoke(self, params: dict[str, Any], ctx: RunContext[DepsT]) -> Any: ...
```

The runtime entrypoints gain optional application dependencies:

```python
await runtime.run(
    agent_id="assistant",
    session_id="demo",
    input_text="find all users",
    deps=my_deps,
)
```

### Pattern Integration

`RunContext[DepsT]` replaces `ExecutionContext` as the context object stored on patterns.

That means:

- base `PatternPlugin.setup(...)` still assembles the runtime context
- `self.context` becomes `RunContext[Any] | None`
- patterns gain access to `self.context.deps`
- tool calls, memory hooks, and policy paths now all see one shared context carrier

### Explicit Boundary

`RunContext` is a **local runtime object**.

It is not part of the prompt and is not automatically shown to the model. This mirrors the successful separation used by Pydantic AI and the OpenAI Agents SDK.

## 5. Plugin Loading Reliability

### Current Problem

`plugins.loader._instantiate()` and `DefaultRuntime._load_runtime_dependency()` still rely on silent constructor fallback:

- `factory(config=config)`
- `factory(config)`
- `factory()`

That means a real bug inside a plugin constructor can be mistaken for “try the next signature”.

### Decision

Make plugin construction explicit.

```python
class PluginConstructor(Protocol):
    def __init__(self, *, config: dict[str, Any], **kwargs: Any) -> None: ...
```

Rules:

- plugin constructors must accept `config=` as a keyword argument
- the loader no longer retries alternate constructor shapes
- the real constructor `TypeError` is preserved and wrapped in `PluginLoadError`

### Capability Validation Before Instantiation

Class-level validation happens before object creation whenever the loader resolves a class:

```python
def _validate_class_capabilities(cls: type, required: list[str]) -> None: ...
```

This changes the failure order from:

1. instantiate object
2. inspect methods

to:

1. resolve class
2. verify required methods exist
3. instantiate once

### Registry Collision Policy

Registration becomes explicit about name conflicts:

- decorator-over-decorator overwrite emits `warnings.warn(...)`
- decorator names that collide with builtin plugin names also emit a warning
- builtin lookup precedence remains explicit and documented

For `0.2.0`, builtin plugins still win when the same name exists in both registries, but that choice is no longer silent.

### Runtime Dependency Loader Parity

The same constructor and validation rules must also apply to runtime-managed dependencies loaded from `runtime.config.*`.

In other words:

- no separate hidden instantiation policy inside `DefaultRuntime`
- one constructor contract across the SDK

## 6. Silent Failure Fixes

### Current Problem

The SDK currently has several “continue but say nothing” paths:

- memory inject/writeback failures under `on_error="continue"`
- event handler failures during `emit(...)`
- partially defined runtime budgets that are not centrally enforced

### Decision A — Structured Logging for Suppressed Errors

Introduce an SDK logger namespace:

```python
logger = logging.getLogger("openagents")
```

Any suppressed failure that continues execution must be logged with identifiers such as:

- `agent_id`
- `session_id`
- `run_id`
- memory type / operation

Memory behavior becomes:

- emit runtime event
- log warning or error
- re-raise only when `on_error == "fail"`

### Decision B — Event Bus Error Isolation

`AsyncEventBus.emit(...)` should isolate handlers from one another:

- append the event to history first
- invoke each subscriber independently
- log handler failures
- continue to remaining handlers

One broken subscriber must not block the rest of the event stream.

### Decision C — Budget Enforcement

Budget enforcement is split into three layers:

1. `max_tool_calls`
   - enforced centrally before tool execution via the base tool-call path

2. `max_duration_ms`
   - enforced at runtime-controlled boundaries:
     - before/after memory hooks
     - before/after pattern execution
     - before tool and LLM helper calls

3. `max_steps`
   - enforced by step-oriented patterns
   - documented as a pattern-step budget, not an arbitrary Python-op counter

### Important Limitation

`max_duration_ms` and `max_steps` cannot preempt arbitrary user code running inside a custom pattern that never returns control to runtime helpers.

This limitation should be documented explicitly rather than implied away.

## 7. Migration Strategy and Dependency Impact

### Dependency Change

Add:

- `pydantic>=2.0`

as a **core** dependency in `pyproject.toml`.

### Version Change

Ship this as:

- `0.2.0`

because the public API changes are intentionally breaking and the package is still pre-1.0.

### Breaking Changes

`0.2.0` makes a clean cut in the following areas:

1. config dataclasses become Pydantic models
2. `from_dict()` callers move to `model_validate()` / loader helpers
3. `RunResult.exception` becomes `OpenAgentsError | None`
4. `RunResult.stop_reason` becomes `StopReason`
5. `ExecutionContext` is replaced by `RunContext`
6. tool context type changes from `Any` to `RunContext[DepsT]`
7. plugin constructors must accept `config=` keyword args
8. exception types are reorganized and renamed

### Compatibility Stance

There are no deprecation shims in this migration.

The repo should instead update, in one change:

- public exports
- examples
- docs
- tests
- builtin plugins
- fixtures for custom plugins

This is cleaner than carrying temporary compatibility logic across a moving design boundary.

## File Impact

### Create

- `docs/superpowers/specs/2026-04-16-openagents-sdk-modernization-design.md`
- a new public `RunContext` module under `openagents/interfaces/` or equivalent exported surface
- targeted tests for:
  - config validation
  - typed run context injection
  - plugin constructor failures
  - registry collision warnings
  - event bus isolation
  - budget enforcement

### Modify

- `pyproject.toml`
- `openagents/errors/exceptions.py`
- `openagents/config/schema.py`
- `openagents/config/loader.py`
- `openagents/interfaces/runtime.py`
- `openagents/interfaces/pattern.py`
- `openagents/interfaces/tool.py`
- `openagents/interfaces/session.py`
- `openagents/interfaces/__init__.py`
- `openagents/plugins/loader.py`
- `openagents/plugins/registry.py`
- `openagents/plugins/builtin/runtime/default_runtime.py`
- `openagents/plugins/builtin/events/async_event_bus.py`
- `openagents/decorators.py`
- `openagents/__init__.py`
- relevant examples, docs, and test fixtures

### Remove or Collapse

- manual config boilerplate that becomes redundant under Pydantic validation
- duplicated plugin-instantiation helpers with different fallback behavior

## Validation

Minimum validation for the migration implementation:

- `uv sync`
- targeted unit tests for new config/runtime/error surfaces
- `uv run pytest -q`
- import-level smoke for public exports used in examples and README snippets

## Success Criteria

This design is successful when:

- callers can pass typed local dependencies into runs
- tools and patterns consume one shared typed runtime context
- config parsing no longer depends on hand-written `from_dict()` code
- plugin constructor bugs fail loudly and accurately
- suppressed failures become visible through logs and events
- runtime results and stop reasons are typed
- the SDK still reads as a single-agent kernel rather than a graph framework
