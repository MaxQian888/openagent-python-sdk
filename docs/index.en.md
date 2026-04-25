# OpenAgents SDK

**OpenAgents SDK** (v0.3.0) is a **config-as-code single-agent runtime kernel** for Python. It provides a minimal, composable foundation layer: developers declare agents via JSON configuration files, and inject memory, tools, execution policy, context assembly, and all other product semantics through plugin seams — rather than hard-coding product logic into the kernel.

The SDK deliberately does **not** own multi-agent teams, approval UX, mailboxes, or product workflows. All of that is implemented by the application layer through the seam protocol.

---

## Installation

=== "Recommended (uv)"

    ```bash
    uv sync
    ```

=== "pip"

    ```bash
    pip install io-openagent-sdk
    ```

=== "With optional extras"

    ```bash
    # YAML output support
    pip install "io-openagent-sdk[yaml]"
    ```

---

## Quick Start

```python
from openagents import Runtime

# Load runtime from a JSON config file
runtime = Runtime.from_config("agent.json")

# Run synchronously (suitable for scripts and tests)
result = runtime.run_sync(
    agent_id="assistant",
    session_id="s1",
    input_text="Hello",
)
print(result)
```

!!! tip "Minimal agent.json example"
    ```json
    {
      "agents": [
        {
          "id": "assistant",
          "llm": {
            "provider": "anthropic",
            "model": "claude-opus-4-5"
          }
        }
      ]
    }
    ```

---

## Three-Layer Architecture

The OpenAgents SDK is built around a three-layer design that keeps the kernel stable, extension points well-defined, and product semantics fully isolated in the application layer.

| Layer | Key Types / Interfaces | Characteristics |
|-------|----------------------|-----------------|
| **Kernel Protocol** | `RunRequest`, `RunResult`, `RunContext[DepsT]`, `ToolExecutionRequest`, `ContextAssemblyResult`, `SessionArtifact`, `StopReason` | Stable dataclasses; change rarely |
| **SDK Seams** (8 extension points) | `memory`, `pattern`, `tool`, `tool_executor`, `context_assembler`, `runtime`, `session`, `events`, `skills` | Runtime plugin extension points; each seam has a built-in default implementation |
| **App-Defined Protocol** | task envelopes, permission state, coding plans, artifact taxonomies, planner state | Product semantics implemented via `RunContext.state`/`.scratch`/`.assembly_metadata`, `RunRequest.context_hints`, `RunArtifact.metadata` |

!!! warning "Core principle"
    **Do not push product semantics into the kernel.** Prerequisites for adding a new seam: cross-app reuse, runtime-behavior impact, independent selector and lifecycle, and a committed built-in default plus tests. Otherwise, keep it in the app layer.

---

## Quick Navigation

<div class="grid cards" markdown>

- **Developer Guide**

    ---

    Environment setup, test commands, complete development workflow

    [:octicons-arrow-right-24: developer-guide.md](getting-started/developer-guide.md)

- **Seams & Extension Points**

    ---

    Seam responsibilities, decision tree, how to choose the right extension point

    [:octicons-arrow-right-24: seams-and-extension-points.md](architecture/seams-and-extension-points.md)

- **Configuration Reference**

    ---

    Full schema for `agent.json`, documentation for every field

    [:octicons-arrow-right-24: configuration.md](configuration/configuration.md)

- **Plugin Development**

    ---

    How to write custom plugins, register them to seams, test and publish them

    [:octicons-arrow-right-24: plugin-development.md](plugins/plugin-development.md)

- **API Reference**

    ---

    Complete API for `Runtime`, `RunRequest`, `RunResult`, `RunContext`, and other core types

    [:octicons-arrow-right-24: api-reference.md](reference/api-reference.md)

- **CLI Reference**

    ---

    Full documentation for `openagents schema`, `openagents validate`, `openagents list-plugins`

    [:octicons-arrow-right-24: cli-reference.md](cli/cli-reference.md)

- **Examples**

    ---

    How to run the quickstart and production_coding_agent examples

    [:octicons-arrow-right-24: examples.md](getting-started/examples.md)

- **Migration Guide**

    ---

    Changes and migration steps when upgrading from 0.2.x to 0.3.x

    [:octicons-arrow-right-24: migration-0.2-to-0.3.md](migration/migration-0.2-to-0.3.md)

</div>

---

## Quick Reference: Which Seam Do I Need?

| Need | Choose |
|------|--------|
| Inject and persist memory across turns | `memory` seam |
| Control the LLM invocation loop (ReAct, few-shot, etc.) | `pattern` seam |
| Register and execute tools (function calling) | `tool` + `tool_executor` seam |
| Customize how the context window is assembled | `context_assembler` seam |
| Custom session storage or locking | `session` seam |
| Intercept or publish runtime events | `events` seam |
| Package reusable agent capabilities | `skills` seam |
| Product task envelopes, permission models, planning state | **Not a seam** — put it in `RunContext.state` |

!!! note "Full decision tree"
    See [seams-and-extension-points.md](architecture/seams-and-extension-points.md) for the complete decision tree and per-seam lifecycle documentation.
