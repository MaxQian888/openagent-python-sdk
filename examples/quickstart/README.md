# quickstart

Single-agent ReAct demo using an Anthropic-compatible endpoint (MiniMax by default).

[中文文档](README.zh.md)

## Quick start (dev environment)

```bash
# 1. Install dependencies
uv sync

# 2. Configure credentials
cp examples/quickstart/.env.example examples/quickstart/.env
# Edit .env — fill in LLM_API_KEY, LLM_API_BASE, LLM_MODEL

# 3. Run via the built-in CLI
openagents run examples/quickstart/agent.json --input "hello"
```

Other output formats:

```bash
# JSONL event stream (for pipelines)
openagents run examples/quickstart/agent.json --input "hello" --format events

# Full RunResult as JSON
openagents run examples/quickstart/agent.json --input "hello" --format json --no-stream

# Interactive multi-turn chat
openagents chat examples/quickstart/agent.json
```

## Legacy script

`run_demo.py` remains for historical reference; it's a one-shot wrapper
that loads `.env`, constructs a `Runtime`, and issues two hand-coded
runs. New code should prefer `openagents run` / `openagents chat`.

## Testing

The quickstart agent is exercised by the CLI smoke tests and the
`openagents run` integration tests, all of which use the mock provider
and require no real API key:

```bash
uv run pytest -q tests/integration/test_cli_smoke.py
uv run pytest -q tests/unit/cli/commands/test_run.py
```

## Environment variables

| Name | Required | Notes |
|------|----------|-------|
| `LLM_API_KEY` | yes | OpenAI-compatible key. |
| `LLM_API_BASE` | yes | Base URL of the provider (e.g. `https://api.minimax.chat/anthropic`). |
| `LLM_MODEL` | yes | Model name (e.g. `abab6.5-chat`). |
