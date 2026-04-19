# OpenAgents SDK

Build protocol-rich agents on top of a small, explicit runtime kernel.

OpenAgents is a config-as-code, async-first SDK for teams that want a clear
single-agent runtime, a small set of strong extension seams, and enough room to
invent product-specific middle protocols above the kernel.

Key public contracts in `0.3.0`:

- `RunContext[DepsT]` for typed local dependency injection
- `RunRequest` / `RunResult[OutputT]` as structured runtime IO
- `Runtime.run_stream()` for event-level streaming projection
- `RunUsage.cost_usd` + `RunBudget.max_cost_usd` for cost tracking / budgeting
- `StopReason` for typed run termination state
- `openagents` CLI: `schema`, `validate`, `list-plugins`

What's new in `0.3.0`: see [CHANGELOG](CHANGELOG.md) and the
[0.2 → 0.3 migration guide](docs/migration-0.2-to-0.3.md).

## Start Here

- [English README](README_EN.md)
- [中文 README](README_CN.md)
- [Developer Docs](docs/README.md)
- [Repository Layout](docs/repository-layout.md)
- [Examples](docs/examples.md)

## Quick Repo Workflow

Sync dependencies:

```bash
uv sync
```

Run the test suite:

```bash
uv run pytest -q
```

Run the smallest maintained example through the built-in CLI:

```bash
openagents run examples/quickstart/agent.json --input "hello"
# or interactively:
openagents chat examples/quickstart/agent.json
```

The legacy `uv run python examples/quickstart/run_demo.py` script still
works and is kept for reference. See [docs/cli.en.md](docs/cli.en.md)
for the full CLI surface (`init`, `run`, `chat`, `dev`, `doctor`,
`config show`, `new plugin`, `replay`, `completion`, `version`).

## Maintained Repo Shape

```text
openagents/  SDK source
docs/        developer documentation
examples/    maintained runnable examples
tests/       unit and integration coverage
```

Current maintained examples:

- `examples/quickstart/`
- `examples/production_coding_agent/`
