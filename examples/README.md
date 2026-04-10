# Examples

All examples use **MiniMax LLM** via the Anthropic-compatible protocol by default.
Setup: copy `.env.example` to `.env` and add your `MINIMAX_API_KEY`.

---

## Quickstart

Builtin plugins only — zero custom code.

- Config: `quickstart/agent.json`
- Run: `uv run python examples/quickstart/run_demo.py`

## Custom Plugins (`impl`)

Custom Skill + custom Pattern, full 6-hook capability system.

- Config: `custom_impl/agent.json`
- Plugins: `custom_impl/plugins.py`
- Run: `uv run python examples/custom_impl/run_demo.py`

## OpenAI-Compatible Real Call

Uses your own OpenAI-compatible endpoint.

- Config: `openai_compatible/agent.json`
- Env: `openai_compatible/.env.example`
- Run:
  ```
  cp openai_compatible/.env.example openai_compatible/.env
  # fill OPENAI_MODEL, OPENAI_BASE_URL, OPENAI_API_KEY
  uv run python examples/openai_compatible/run_demo.py
  ```

## Runtime Composition

Builtin execution seams (safe tool executor, filesystem policy, summarizing assembler).

- Config: `runtime_composition/agent.json`
- Plugins: `runtime_composition/plugins.py`
- Run: `uv run python examples/runtime_composition/run_demo.py`

## Persistent QA Assistant

File-backed persistent memory across sessions, keyword search, interactive CLI.

- Config: `persistent_qa/agent.json`
- Plugins: `persistent_qa/plugins/`
- Run: `uv run python examples/persistent_qa/run_demo.py`

## Multi-Step Research

Plan-Execute pattern: search → read_file → synthesize, with scratch metadata.

- Config: `multi_step_research/agent.json`
- Plugins: `multi_step_research/plugins.py`
- Run: `uv run python examples/multi_step_research/run_demo.py`

## Skill Hooks Demo

All 6 Skill capability hooks firing in order — `get_system_prompt`, `get_metadata`,
`augment_context`, `filter_tools`, `before_run`, `after_run`.

- Config: `skill_hooks_demo/agent.json`
- Plugins: `skill_hooks_demo/plugins.py`
- Run: `uv run python examples/skill_hooks_demo/run_demo.py`

## Long Conversation

SummarizingContextAssembler (transcript trimming) + ChainMemory (buffer + window).

- Config: `long_conversation/agent.json`
- Run: `uv run python examples/long_conversation/run_demo.py`

## Sandbox Agent

FilesystemExecutionPolicy (read-only whitelist) + SafeToolExecutor (timeout guard).

- Config: `sandbox_agent/agent.json`
- Plugins: `sandbox_agent/plugins.py`
- Run: `uv run python examples/sandbox_agent/run_demo.py`
