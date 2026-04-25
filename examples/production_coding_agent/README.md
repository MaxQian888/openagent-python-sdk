# Production Coding Agent

A production-style coding agent built on the OpenAgents kernel.

[中文文档](README.zh.md)

Demonstrates:

- explicit task-packet assembly
- persistent coding memory
- safe tool execution with filesystem boundaries
- local follow-up semantics
- structured delivery artifacts
- benchmark-style evaluation harness
- **durable execution**: `run_demo.py` passes `durable=True` — if an upstream LLM
  rate-limit / connection error hits mid-run, the runtime auto-loads the most
  recent step checkpoint and resumes (bounded by `RunBudget.max_resume_attempts`).

## Structure

```text
production_coding_agent/
  agent.json
  run_demo.py
  run_benchmark.py
  app/
    protocols.py
    plugins.py
    benchmark.py
  benchmarks/
    tasks.json
  workspace/
    PRODUCT_BRIEF.md
    app/
    tests/
  outputs/
```

### What lives where

- `agent.json` — runtime wiring
- `run_demo.py` — interactive demo entrypoint
- `run_benchmark.py` — local benchmark harness entrypoint
- `app/protocols.py` — structured protocol objects
- `app/plugins.py` — memory, context assembler, follow-up, repair, and pattern
- `app/benchmark.py` — deterministic benchmark runner
- `benchmarks/tasks.json` — benchmark task set
- `workspace/` — simulated repository to inspect
- `outputs/` — generated delivery artifacts

## Quick start (dev environment)

```bash
# 1. Install dependencies
uv sync

# 2. Configure credentials
cp examples/production_coding_agent/.env.example examples/production_coding_agent/.env
# Edit .env — fill in LLM_API_KEY, LLM_API_BASE, LLM_MODEL

# 3. Run via the built-in CLI (recommended)
openagents run examples/production_coding_agent/agent.json \
    --input "implement TicketService.close_ticket and add tests"

# Interactive multi-turn chat
openagents chat examples/production_coding_agent/agent.json

# Legacy demo script (equivalent, kept for illustration)
uv run python examples/production_coding_agent/run_demo.py
```

## Benchmark

```bash
uv run python examples/production_coding_agent/run_benchmark.py
```

## Testing

```bash
# Integration test — deterministic mock LLM, no real API key required
uv run pytest -q tests/integration/test_production_coding_agent_example.py
```

## Environment variables

| Name | Required | Notes |
|------|----------|-------|
| `LLM_API_KEY` | yes | OpenAI-compatible key. |
| `LLM_API_BASE` | yes | Base URL of the provider. |
| `LLM_MODEL` | yes | Model name. |
