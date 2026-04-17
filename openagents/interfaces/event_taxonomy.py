"""Declared schema for events emitted by the SDK and built-in plugins.

Schema is **advisory**: ``EventBus.emit`` logs a warning when a declared
event name is emitted with missing required payload keys, but never
raises. Subscribers should not rely on the warning being present.

Custom user events not present in ``EVENT_SCHEMAS`` are emitted unchanged
with no validation.

To regenerate ``docs/event-taxonomy.md`` from this registry, run::

    uv run python -m openagents.tools.gen_event_doc
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventSchema:
    """Description of a single declared event name."""

    name: str
    required_payload: tuple[str, ...] = ()
    optional_payload: tuple[str, ...] = ()
    description: str = ""


EVENT_SCHEMAS: dict[str, EventSchema] = {
    # === existing events (carried over verbatim, no rename) ===
    "tool.called": EventSchema(
        "tool.called",
        ("tool_id", "params"),
        (),
        "Pattern is about to invoke a tool.",
    ),
    "tool.succeeded": EventSchema(
        "tool.succeeded",
        ("tool_id", "result"),
        ("executor_metadata",),
        "Tool returned successfully.",
    ),
    "tool.failed": EventSchema(
        "tool.failed",
        ("tool_id", "error"),
        (),
        "Tool raised; final after fallback. Use 'tool.retry_requested' for ModelRetry signal.",
    ),
    "tool.retry_requested": EventSchema(
        "tool.retry_requested",
        ("tool_id", "attempt", "error"),
        (),
        "Pattern caught ModelRetryError and is retrying.",
    ),
    "llm.called": EventSchema(
        "llm.called",
        ("model",),
        (),
        "Pattern is about to call an LLM.",
    ),
    "llm.succeeded": EventSchema(
        "llm.succeeded",
        ("model",),
        (),
        "LLM returned successfully.",
    ),
    "usage.updated": EventSchema(
        "usage.updated",
        ("usage",),
        (),
        "RunUsage object was updated; emitted after every LLM call.",
    ),
    "pattern.step_started": EventSchema(
        "pattern.step_started",
        ("step",),
        ("plan_step",),
        "Pattern began an execution step.",
    ),
    "pattern.step_finished": EventSchema(
        "pattern.step_finished",
        ("step", "action"),
        (),
        "Pattern completed an execution step.",
    ),
    "pattern.phase": EventSchema(
        "pattern.phase",
        ("phase",),
        (),
        "Pattern transitioned phases (e.g. planning, executing).",
    ),
    "pattern.plan_created": EventSchema(
        "pattern.plan_created",
        ("plan",),
        (),
        "PlanExecutePattern produced its plan.",
    ),
    # === new supplemental lifecycle events (Spec B WP2) ===
    "session.run.started": EventSchema(
        "session.run.started",
        ("agent_id", "session_id"),
        ("run_id", "input_text"),
        "Runtime begins a single run.",
    ),
    "session.run.completed": EventSchema(
        "session.run.completed",
        ("agent_id", "session_id", "stop_reason"),
        ("run_id", "duration_ms"),
        "Runtime finished a single run.",
    ),
    "context.assemble.started": EventSchema(
        "context.assemble.started",
        (),
        (),
        "context_assembler.assemble() is about to run.",
    ),
    "context.assemble.completed": EventSchema(
        "context.assemble.completed",
        ("transcript_size",),
        ("artifact_count", "duration_ms"),
        "context_assembler.assemble() returned.",
    ),
    "memory.inject.started": EventSchema(
        "memory.inject.started",
        (),
        (),
        "memory.inject() is about to run.",
    ),
    "memory.inject.completed": EventSchema(
        "memory.inject.completed",
        (),
        ("view_size",),
        "memory.inject() returned.",
    ),
    "memory.writeback.started": EventSchema(
        "memory.writeback.started",
        (),
        (),
        "memory.writeback() is about to run.",
    ),
    "memory.writeback.completed": EventSchema(
        "memory.writeback.completed",
        (),
        (),
        "memory.writeback() returned.",
    ),
}
