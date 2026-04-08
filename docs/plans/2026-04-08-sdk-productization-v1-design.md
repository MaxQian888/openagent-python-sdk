# SDK Productization V1 Design

## Goal

Turn the current single-agent runtime kernel into a productized SDK surface by making the new runtime seams first-class in agent configuration, adding a small set of high-value builtin implementations, and updating README/docs/examples so users can discover and use the system without reading runtime internals first.

## Scope

This design covers:

- agent-level configuration for `tool_executor`, `execution_policy`, and `context_assembler`
- decorator/registry/loader support for those seam types
- three builtin implementations:
  - `safe` tool executor
  - `filesystem` execution policy
  - `summarizing` context assembler
- README, `docs-v2`, and example updates

This design does not add team/subagent/product-layer orchestration.

## Key Design Decision

`tool_executor`, `execution_policy`, and `context_assembler` remain agent-level concerns.

Reasoning:

- different agents in the same app may require different execution and context strategies
- these seams shape how a single agent runs, not how the app hosts agents globally
- keeping them agent-scoped preserves the SDK's single-agent kernel boundary

## Configuration Shape

Each agent may now declare:

```json
{
  "tool_executor": {"type": "safe"},
  "execution_policy": {"type": "filesystem"},
  "context_assembler": {"type": "summarizing"}
}
```

These are selector objects following the existing `type` / `impl` / `config` convention.

Backward compatibility:

- the existing runtime-level `runtime.config.tool_executor`
- `runtime.config.execution_policy`
- `runtime.config.context_assembler`

remain supported as fallback, but agent-level config becomes the documented primary path.

## Plugin Model

Three new seam kinds become formal plugin categories:

- `tool_executor`
- `execution_policy`
- `context_assembler`

They get:

- schema refs
- decorator registries
- builtin registry entries
- loader functions
- package exports

## Builtins

### SafeToolExecutor

Purpose:

- validate parameters before execution
- apply timeout handling consistently
- normalize errors into structured `ToolExecutionResult`

Config:

- `default_timeout_ms`
- `allow_stream_passthrough`

### FilesystemExecutionPolicy

Purpose:

- guard file-oriented tools with allow/deny roots and tool filters
- support coding-agent workloads without forcing a full sandbox

Config:

- `read_roots`
- `write_roots`
- `allow_tools`
- `deny_tools`

### SummarizingContextAssembler

Purpose:

- trim transcript/artifact payloads to a bounded working set
- provide compact assembly metadata
- optionally append a deterministic summary marker for omitted history

Config:

- `max_messages`
- `max_artifacts`
- `include_summary_message`

## Docs and Examples

README should become the product landing page:

- core mental model
- agent-level seam overview
- recommended quickstarts
- canonical docs links

`docs-v2/configuration.md` should document the new agent-level selectors.

`docs-v2/plugin-development.md` should document how to write custom tool executors, execution policies, and context assemblers.

`docs-v2/api-reference.md` should document new exports and runtime contracts.

Add `examples/runtime_composition/` as the canonical seam-composition example using the three new builtin types together.

## Success Criteria

- users can discover and configure the new seams from README/docs alone
- builtin seam implementations provide immediate value for coding and non-coding agents
- tests cover config loading, loader behavior, runtime wiring, and example-adjacent behavior
- existing functionality remains green
