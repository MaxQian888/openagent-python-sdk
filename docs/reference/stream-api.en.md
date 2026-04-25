# Streaming API

This page is a deep-dive companion to the [API Reference](api-reference.en.md) streaming section. It covers the internal architecture, complete usage examples, and things to watch out for.

## 1. Overview

The OpenAgents streaming API is a **projection of the event bus into a unified chunk stream**.

Internally the runtime always publishes events through `AsyncEventBus` (LLM text deltas, tool-call start/finish, artifact emissions, etc.). `run_stream()` subscribes to this event stream under the hood, maps **declared events** into `RunStreamChunk` objects, and returns them one by one through an async generator.

**Three primary entry points:**

| Entry point | Type | When to use |
| --- | --- | --- |
| `Runtime.run_stream(*, request)` | async generator | Async Python code (preferred) |
| `stream_agent_with_dict(payload, *, request)` | sync generator | Synchronous contexts |
| `stream_agent_with_config(config_path, *, request)` | sync generator | Synchronous contexts, loading from a file |

!!! note
    The synchronous wrappers drive the event loop via `asyncio.run()`, so they
    **cannot be called from inside a running event loop** (e.g., inside an async cell
    in a Jupyter Notebook).

## 2. RunStreamChunkKind

Every chunk carries a `kind` field indicating which underlying event it was projected from.

| Kind | Event bus source | Key payload fields |
| --- | --- | --- |
| `run.started` | `run.started` | — |
| `llm.delta` | `llm.delta` | `text: str` |
| `llm.finished` | `llm.succeeded` | `model: str` |
| `tool.started` | `tool.called` | `tool_id: str`, `params: dict` |
| `tool.delta` | `tool.delta` | `tool_id: str`, `text: str` |
| `tool.finished` | `tool.succeeded` / `tool.failed` | `tool_id: str`, `result: Any` (success) or `error: str` (failure) |
| `artifact` | `artifact.emitted` | `name: str`, `kind: str`, `payload: Any` |
| `validation.retry` | `validation.retry` | `attempt: int`, `error: str` |
| `run.finished` | — (synthesized by the runtime) | `result: RunResult` (via the `.result` field, not in `payload`) |

!!! note "Event filtering"
    Only events listed in the `EVENT_TO_CHUNK_KIND` mapping table produce chunks.
    Other internal events (such as `config.reloaded` or `agent.reloaded`) do not
    appear in the stream.

## 3. RunStreamChunk fields

```python
class RunStreamChunk(BaseModel):
    kind: RunStreamChunkKind        # Chunk type
    run_id: str                     # Corresponds to RunRequest.run_id
    session_id: str                 # Owning session
    agent_id: str                   # Owning agent
    sequence: int                   # Monotonically increasing within a run
    timestamp_ms: int               # Unix timestamp in milliseconds
    payload: dict[str, Any]         # Event-specific data
    result: RunResult | None        # Only populated on RUN_FINISHED
```

**`sequence` field**: guaranteed to increment by 1 from 1 for each chunk yielded within a single run. Consumers can detect disconnections by checking for gaps.

**`result` field**: only non-`None` when `kind == RUN_FINISHED`. Carries the complete `RunResult` (including `usage`, `artifacts`, `stop_reason`, etc.).

## 4. Basic usage (async)

```python
import asyncio
from openagents import Runtime
from openagents.interfaces.runtime import RunRequest, RunStreamChunkKind

runtime = Runtime.from_config("agent.json")

async def stream_run():
    request = RunRequest(
        agent_id="assistant",
        session_id="session-1",
        input_text="Explain quantum entanglement in one sentence.",
    )
    async for chunk in runtime.run_stream(request=request):
        if chunk.kind is RunStreamChunkKind.LLM_DELTA:
            # Print LLM output character by character
            print(chunk.payload.get("text", ""), end="", flush=True)

        elif chunk.kind is RunStreamChunkKind.TOOL_STARTED:
            print(f"\n[TOOL] {chunk.payload.get('tool_id')}")

        elif chunk.kind is RunStreamChunkKind.TOOL_FINISHED:
            if "error" in chunk.payload:
                print(f"\n[TOOL FAILED] {chunk.payload['error']}")
            else:
                print(f"\n[TOOL DONE] {chunk.payload.get('tool_id')}")

        elif chunk.kind is RunStreamChunkKind.ARTIFACT:
            name = chunk.payload.get("name")
            print(f"\n[ARTIFACT] {name}")

        elif chunk.kind is RunStreamChunkKind.RUN_FINISHED:
            print(f"\n[DONE] stop_reason={chunk.result.stop_reason}")
            print(f"       cost_usd={chunk.result.usage.cost_usd}")

asyncio.run(stream_run())
```

## 5. Synchronous usage

For contexts where `async` is not available (CLI scripts, WSGI frameworks):

```python
from openagents.runtime.sync import stream_agent_with_dict
from openagents.interfaces.runtime import RunRequest, RunStreamChunkKind

config = {
    "agents": [{
        "id": "assistant",
        "name": "Assistant",
        "memory": {"type": "noop"},
        "pattern": {"type": "react"},
    }],
    "runtime": {"type": "default"},
    "session": {"type": "in_memory"},
    "events": {"type": "async"},
    "skills": {"type": "local"},
}

request = RunRequest(
    agent_id="assistant",
    session_id="s1",
    input_text="Hello",
)

for chunk in stream_agent_with_dict(config, request=request):
    if chunk.kind is RunStreamChunkKind.LLM_DELTA:
        print(chunk.payload.get("text", ""), end="", flush=True)
    elif chunk.kind is RunStreamChunkKind.RUN_FINISHED:
        print()
        print(f"Done: {chunk.result.final_output}")
```

Loading from a file:

```python
from openagents.runtime.sync import stream_agent_with_config
from openagents.interfaces.runtime import RunRequest, RunStreamChunkKind

request = RunRequest(
    agent_id="assistant",
    session_id="s1",
    input_text="Hello",
)

for chunk in stream_agent_with_config("agent.json", request=request):
    if chunk.kind is RunStreamChunkKind.LLM_DELTA:
        print(chunk.payload.get("text", ""), end="", flush=True)
```

## 6. Combined with structured output (validation retries)

When `RunRequest.output_type` is set, a failed validation produces a `VALIDATION_RETRY` chunk, after which the runtime re-enters `pattern.execute()` and produces another full sequence of LLM/tool chunks.

```python
from pydantic import BaseModel
from openagents.interfaces.runtime import RunRequest, RunBudget, RunStreamChunkKind

class Summary(BaseModel):
    title: str
    points: list[str]

request = RunRequest(
    agent_id="assistant",
    session_id="s1",
    input_text="Summarize the following: ...",
    output_type=Summary,
    budget=RunBudget(max_validation_retries=3),
)

async for chunk in runtime.run_stream(request=request):
    if chunk.kind is RunStreamChunkKind.VALIDATION_RETRY:
        attempt = chunk.payload.get("attempt", "?")
        error = chunk.payload.get("error", "")
        print(f"\n[VALIDATION RETRY #{attempt}] {error}")

    elif chunk.kind is RunStreamChunkKind.LLM_DELTA:
        print(chunk.payload.get("text", ""), end="", flush=True)

    elif chunk.kind is RunStreamChunkKind.RUN_FINISHED:
        result = chunk.result
        if result.final_output is not None:
            summary: Summary = result.final_output
            print(f"\nTitle: {summary.title}")
        elif result.error:
            print(f"\nFailed: {result.error}")
```

Use the `attempt` field to distinguish retry rounds: each retry produces one `VALIDATION_RETRY` chunk followed by a new complete sequence of LLM/tool chunks.

## 7. Multiple concurrent agents

When running multiple agents concurrently, use `run_id` to correlate chunks from each run:

```python
import asyncio
from openagents.interfaces.runtime import RunRequest, RunStreamChunkKind
from uuid import uuid4

async def stream_multiple():
    requests = [
        RunRequest(agent_id="assistant", session_id=f"s{i}",
                   input_text=f"Task {i}", run_id=str(uuid4()))
        for i in range(3)
    ]

    async def consume(req):
        chunks = []
        async for chunk in runtime.run_stream(request=req):
            chunks.append(chunk)
        return req.run_id, chunks

    results = await asyncio.gather(*[consume(r) for r in requests])
    for run_id, chunks in results:
        finished = next(c for c in chunks if c.kind is RunStreamChunkKind.RUN_FINISHED)
        print(f"run={run_id[:8]}  output={finished.result.final_output}")

asyncio.run(stream_multiple())
```

!!! tip
    `sequence` is **per-run**, not per-session. When multiple runs are active concurrently,
    the same sequence number may appear from different runs. Use `run_id`, not `sequence`,
    to correlate chunks across concurrent runs.

## 8. How it works

```
run_stream()
  │
  ├─ subscribe("*", handler)          # Wildcard subscription on event bus
  │
  ├─ asyncio.create_task(_drive_run)  # Run run_detailed() as a background task
  │
  └─ Poll queue, yield RunStreamChunk
       │
       ├─ llm.delta → LLM_DELTA
       ├─ llm.succeeded → LLM_FINISHED
       ├─ tool.called → TOOL_STARTED
       ├─ tool.delta → TOOL_DELTA
       ├─ tool.succeeded / tool.failed → TOOL_FINISHED
       ├─ artifact.emitted → ARTIFACT
       ├─ validation.retry → VALIDATION_RETRY
       └─ [run task completes] → RUN_FINISHED (synthesized, not from event bus)
```

**Key implementation details:**

1. **Event filtering**: `project_event()` looks up the `EVENT_TO_CHUNK_KIND` mapping table; unmapped events are silently discarded.
2. **run_id filtering**: Events whose payload contains a `run_id` that does not match the current run are skipped, preventing interference from other concurrent runs in the same session.
3. **RUN_FINISHED synthesis**: The terminal chunk is manually synthesized by `run_stream()` after the run task completes; it does not depend on the event bus. This guarantees that the terminal chunk is always delivered, even if the run fails.
4. **Cancellation safety**: The generator's `finally` block cancels the run task and attempts to remove the handler from the subscriber list to prevent resource leaks.

## 9. Things to watch out for

!!! warning "Do not call sync wrappers inside a running event loop"
    `stream_agent_with_dict` / `stream_agent_with_config` use `asyncio.run()` internally
    and cannot be called from an environment that already has a running event loop (e.g.,
    Jupyter Notebooks, FastAPI async handlers). Use `runtime.run_stream()` directly in
    those environments.

!!! warning "TOOL_FINISHED maps both success and failure"
    The `TOOL_FINISHED` chunk is produced by both `tool.succeeded` and `tool.failed` events.
    Check `payload.get("error")` to distinguish the outcome rather than assuming
    `TOOL_FINISHED` always means success.

!!! tip "Disconnect detection"
    If you are forwarding chunks over a WebSocket or SSE transport layer, include the
    `sequence` field in each forwarded message. Clients can detect a gap in the sequence
    to know that chunks were missed (assuming you cache chunks server-side for recovery).

!!! note "RUN_FINISHED is always the last chunk"
    Even if an exception is raised inside the run, `run_stream()` **always** yields a
    `RUN_FINISHED` chunk last, with `result.stop_reason = failed` and `result.error`
    containing the error message. Consumers can unconditionally use `RUN_FINISHED` as
    the stream termination signal.

## Further reading

- [API Reference](api-reference.en.md)
- [Configuration Reference](../configuration/configuration.md)
- [Plugin Development](../plugins/plugin-development.md)
- [Seams and Extension Points](../architecture/seams-and-extension-points.md)
