# quickstart

Single-agent ReAct demo using the Anthropic-compatible MiniMax endpoint.

## Run

```bash
# 1. Configure provider credentials
cp examples/quickstart/.env.example examples/quickstart/.env
# then fill in LLM_API_KEY, LLM_API_BASE, LLM_MODEL.

# 2. Invoke through the built-in CLI
openagents run examples/quickstart/agent.json --input "hello"

# JSONL events stream (for pipelines):
openagents run examples/quickstart/agent.json --input "hello" --format events

# Full RunResult as JSON:
openagents run examples/quickstart/agent.json --input "hello" --format json --no-stream

# Interactive multi-turn chat:
openagents chat examples/quickstart/agent.json
```

## Legacy script

`run_demo.py` remains for historical reference; it's a one-shot wrapper
that loads `.env`, constructs a `Runtime`, and issues two hand-coded
runs. New code should prefer `openagents run` / `openagents chat`.
