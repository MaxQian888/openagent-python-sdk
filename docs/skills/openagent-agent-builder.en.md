# OpenAgent Agent Builder

`openagent-agent-builder` is an **app-layer skill** that sits on top of the OpenAgents SDK. It is discovered and executed through the top-level `skills` component (`LocalSkillsManager`) — it is not a seam inside the runtime.

## Installation and Setup

The skill lives in `skills/openagent-agent-builder/` at the repository root; no extra installation is required. Add the following `skills` configuration to your `agent.json` to enable it:

```json
{
  "skills": {
    "type": "local",
    "config": {
      "search_paths": ["skills"],
      "enabled": ["openagent-agent-builder"]
    }
  }
}
```

`search_paths` should be relative to the config file. `LocalSkillsManager` will automatically discover the `openagent-agent-builder` directory and register the skill.

!!! tip
    When running from the repository root, `search_paths: ["skills"]` points directly to `skills/openagent-agent-builder/`.
    When referencing from a different project, adjust to the appropriate relative or absolute path.

Its goal is to give the host agent or developer all of the following in one shot:

- A runnable single-agent `sdk_config` (a complete `AppConfig` payload)
- A real smoke run result (using mock LLM by default, zero dependencies)
- Integration suggestions for placing this agent into a team

## What It Does

- Build a `subagent`
- Build a single-role agent for an `agent-team` (`team-role`)
- Infer the `memory / pattern / llm / tools / runtime` quartet
- Automatically inject a `filesystem` execution policy based on `workspace_root`
- Output a handoff contract and integration hints
- Run a smoke run via `Runtime.from_dict(...).run_detailed(...)`

## What It Does Not Do

- Team scheduler, mailbox, or approval UX
- Background jobs, cancel/resume, cross-session persistence
- Global retry/cancel/resume policies
- Cross-agent lifecycle management
- Handoff execution between agents (it only describes what the contract looks like)

## Core I/O

Input is `OpenAgentSkillInput`:

- `task_goal` (required)
- `agent_role` (required, values: `planner` | `coder` | `reviewer` | `researcher`)
- `agent_mode` (required, values: `subagent` | `team-role`)
- `workspace_root`
- `available_tools`
- `constraints` (`max_steps`, `step_timeout_ms`, etc. are merged into the agent's `runtime`; `read_only: true` suppresses `write_roots`)
- `handoff_expectation` (`{input, output, artifact_format}`)
- `overrides` (deep-merged by seam dimension; when `tools` is a list it is a full replacement)
- `smoke_run` (default `true`)

Output is `OpenAgentSkillOutput`:

- `agent_spec`
- `agent_prompt_summary`
- `design_rationale`
- `handoff_contract`
- `integration_hints`
- `smoke_result` (`status` ∈ `"passed" | "failed" | "skipped"`)
- `next_actions`

## Agent Spec Shape

`agent_spec` directly conforms to `openagents.config.schema.AppConfig` (current `version = "1.0"`) — no additional DSL is invented. Fields include:

- `agent_key`
- `purpose`
- `sdk_config`: complete `AppConfig` including top-level `runtime / session / events / skills` selectors + `agents[0]`
- `run_request_template`: a field skeleton that can be passed directly to `RunRequest(...)`

You can therefore immediately do:

```python
runtime = Runtime.from_dict(spec["agent_spec"]["sdk_config"])
result = await runtime.run_detailed(request=RunRequest(**template_payload))
```

## Archetypes

Four archetypes are currently supported (see `skills/openagent-agent-builder/src/openagent_agent_builder/archetypes.py`):

| Role | Pattern | Default Tools | Notes |
| --- | --- | --- | --- |
| `planner` | `plan_execute` | search, read_file, list_files | Upstream role; produces a plan |
| `coder` | `react` + `safe` tool_executor | read_file, write_file, list_files, grep_files, ripgrep | Writable; `constraints.read_only=true` disables writes |
| `reviewer` | `react` + `safe` tool_executor | read_file, list_files, grep_files, ripgrep, search | Downstream role; read-only |
| `researcher` | `reflexion` + `safe` tool_executor | search, http_request, url_parse, query_param | Upstream role; iterative evidence gathering |

Archetypes are default templates only, not hardcoded team semantics. All seams can be adjusted through `overrides`.

## LLM Defaults to Mock

So that smoke runs can unconditionally pass in offline / CI environments, all archetype `llm.provider` values default to `mock`. Real deployments must switch to `anthropic` or `openai_compatible` via `overrides.llm` (see `LLMOptions` validation rules; the latter requires `api_base`).

## Seam Consolidation Note (0.3.x)

After the 0.3.x seam consolidation, the agent builder generates configs using `tool_executor: filesystem_aware` instead of the old `execution_policy: filesystem`. All generated `sdk_config` payloads are 0.3.x-compatible with no manual migration needed.

!!! warning
    If you have cached agent builder output from an older version (0.2.x format), re-run the builder or manually replace `execution_policy: filesystem` with `tool_executor: filesystem_aware`. See [migration-0.2-to-0.3.md](../migration/migration-0.2-to-0.3.md) for details.

## Host Adapters

All capabilities are consolidated under the skill directory:

- `skills/openagent-agent-builder/`
  - `SKILL.md`, `references/architecture.md`, `references/examples.md`, `agents/openai.yaml`
- `skills/openagent-agent-builder/src/openagent_agent_builder/`
  - Executable core (`normalize → archetypes → render → smoke`)
- `openagent_agent_builder.entrypoint.run_openagent_skill(payload: dict) -> dict`
  - Called by the top-level `skills` component or an app-owned main-agent tool

At session start, `skills.prepare_session()` only warms up the description; references and the entrypoint are loaded progressively on demand.

## Known Limitations

- **No multi-agent support**: The builder handles only single-agent configuration. It does not address team schedulers, mailboxes, or approval UX.
- **Smoke run uses mock LLM**: The smoke run uses the `mock` provider and will not fail due to LLM issues. Validating real LLM behavior requires running in the target environment yourself.
- **`overrides.tools` is a full replacement**: When `overrides.tools` is a list, it completely replaces the archetype's default tool list rather than appending to it. If you only want to add one tool, include the archetype defaults in the list as well.
- **No cross-session persistence guarantees**: The builder's generated `sdk_config` defaults to `jsonl_file` session storage, which is not guaranteed to be readable across major versions.
