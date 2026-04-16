# OpenAgents SDK

Build protocol-rich agents on top of a small, explicit runtime kernel.

OpenAgents is a config-as-code, async-first SDK for teams that want a clear
single-agent runtime, a small set of strong extension seams, and enough room to
invent product-specific middle protocols above the kernel.

Key public contracts in `0.2.0`:

- `RunContext[DepsT]` for typed local dependency injection
- `RunRequest` / `RunResult` as structured runtime IO
- `StopReason` for typed run termination state

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

Run the smallest maintained example:

```bash
uv run python examples/quickstart/run_demo.py
```

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
