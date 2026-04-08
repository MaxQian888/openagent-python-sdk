# Examples

## Quickstart (builtin plugins)

- Config: `examples/quickstart/agent.json`
- Run: `uv run python examples/quickstart/run_demo.py`

## Custom Plugins (`impl`)

- Config: `examples/custom_impl/agent.json`
- Plugins: `examples/custom_impl/plugins.py`
- Run: `uv run python -m examples.custom_impl.run_demo`

## OpenAI-Compatible Real Call

- Config: `examples/openai_compatible/agent.json`
- Env template: `examples/openai_compatible/.env.example`
- Run script: `examples/openai_compatible/run_demo.py`
- Run:
  - copy `.env.example` to `.env`
  - fill `OPENAI_MODEL`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`
  - `uv run python examples/openai_compatible/run_demo.py`

## Runtime Composition

- Config: `examples/runtime_composition/agent.json`
- Plugins: `examples/runtime_composition/plugins.py`
- Run script: `examples/runtime_composition/run_demo.py`
- Builtin seams:
  - `tool_executor: safe`
  - `execution_policy: filesystem`
  - `context_assembler: summarizing`
- Run:
  - `uv run python examples/runtime_composition/run_demo.py`
