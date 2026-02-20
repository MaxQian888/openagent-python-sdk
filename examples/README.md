# Examples

## Quickstart (builtin plugins)

- Config: `examples/quickstart/agent.json`
- Run: `uv run python examples/quickstart/run_demo.py`

## Custom Plugins (`impl`)

- Config: `examples/custom_impl/agent.json`
- Plugins: `examples/custom_impl/plugins.py`
- Run: `uv run python examples/custom_impl/run_demo.py`

## OpenAI-Compatible Real Call

- Config: `examples/openai_compatible/agent.json`
- Env template: `examples/openai_compatible/.env.example`
- Run script: `examples/openai_compatible/run_demo.py`
- Run:
  - copy `.env.example` to `.env`
  - fill `OPENAI_MODEL`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`
  - `uv run python examples/openai_compatible/run_demo.py`
