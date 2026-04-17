# Event Taxonomy

Events emitted by the SDK and built-in plugins. Schema is **advisory**: the
async event bus logs a warning when a declared event is emitted with
missing required payload keys, but never raises. Custom events not
present here are emitted unchanged with no validation.

The source of truth is
[`openagents/interfaces/event_taxonomy.py`](../openagents/interfaces/event_taxonomy.py).
Regenerate this file via::

    uv run python -m openagents.tools.gen_event_doc

| Event | Required payload | Optional payload | Description |
|---|---|---|---|
| `context.assemble.completed` | `transcript_size` | `artifact_count`, `duration_ms` | context_assembler.assemble() returned. |
| `context.assemble.started` | — | — | context_assembler.assemble() is about to run. |
| `llm.called` | `model` | — | Pattern is about to call an LLM. |
| `llm.succeeded` | `model` | — | LLM returned successfully. |
| `memory.inject.completed` | — | `view_size` | memory.inject() returned. |
| `memory.inject.started` | — | — | memory.inject() is about to run. |
| `memory.writeback.completed` | — | — | memory.writeback() returned. |
| `memory.writeback.started` | — | — | memory.writeback() is about to run. |
| `pattern.phase` | `phase` | — | Pattern transitioned phases (e.g. planning, executing). |
| `pattern.plan_created` | `plan` | — | PlanExecutePattern produced its plan. |
| `pattern.step_finished` | `step`, `action` | — | Pattern completed an execution step. |
| `pattern.step_started` | `step` | `plan_step` | Pattern began an execution step. |
| `session.run.completed` | `agent_id`, `session_id`, `stop_reason` | `run_id`, `duration_ms` | Runtime finished a single run. |
| `session.run.started` | `agent_id`, `session_id` | `run_id`, `input_text` | Runtime begins a single run. |
| `tool.called` | `tool_id`, `params` | — | Pattern is about to invoke a tool. |
| `tool.failed` | `tool_id`, `error` | — | Tool raised; final after fallback. Use 'tool.retry_requested' for ModelRetry signal. |
| `tool.retry_requested` | `tool_id`, `attempt`, `error` | — | Pattern caught ModelRetryError and is retrying. |
| `tool.succeeded` | `tool_id`, `result` | `executor_metadata` | Tool returned successfully. |
| `usage.updated` | `usage` | — | RunUsage object was updated; emitted after every LLM call. |
