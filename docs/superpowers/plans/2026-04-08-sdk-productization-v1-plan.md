# SDK Productization V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Productize the SDK by making agent-level runtime seams first-class, adding a small builtin set, and updating docs/examples so the system is usable without reading runtime internals.

**Architecture:** Add agent-scoped selector refs plus registry/loader support for `tool_executor`, `execution_policy`, and `context_assembler`; provide builtin implementations for each seam; then align README, `docs-v2`, and examples with the new public surface.

**Tech Stack:** Python 3.10+, dataclasses, existing plugin/capability system, pytest, markdown docs

---

### Task 1: Formalize agent-level seam config

**Files:**
- Modify: `openagents/config/schema.py`
- Modify: `openagents/config/validator.py`
- Modify: `openagents/runtime/runtime.py`
- Modify: `openagents/plugins/loader.py`

- [ ] Add selector refs for `tool_executor`, `execution_policy`, and `context_assembler`
- [ ] Attach them to `AgentDefinition`
- [ ] Validate them in config loading
- [ ] Update runtime/plugin loading to prefer agent-level seam plugins, with runtime-level config fallback for compatibility

### Task 2: Make new seam kinds first-class plugin categories

**Files:**
- Modify: `openagents/decorators.py`
- Modify: `openagents/plugins/registry.py`
- Modify: `openagents/__init__.py`
- Modify: `openagents/interfaces/__init__.py`
- Modify tests under `tests/unit/`

- [ ] Add registries/decorators/getters/list helpers
- [ ] Add builtin registry buckets
- [ ] Export new public symbols

### Task 3: Add builtin implementations

**Files:**
- Create: `openagents/plugins/builtin/tool_executor/safe.py`
- Create: `openagents/plugins/builtin/execution_policy/filesystem.py`
- Create: `openagents/plugins/builtin/context/summarizing.py`
- Modify: `openagents/plugins/registry.py`
- Modify tests under `tests/unit/`

- [ ] Implement `SafeToolExecutor`
- [ ] Implement `FilesystemExecutionPolicy`
- [ ] Implement `SummarizingContextAssembler`
- [ ] Add focused tests for each builtin

### Task 4: Update docs

**Files:**
- Modify: `README.md`
- Modify: `docs-v2/configuration.md`
- Modify: `docs-v2/plugin-development.md`
- Modify: `docs-v2/api-reference.md`
- Modify: `docs-v2/examples.md`
- Modify: `examples/README.md`

- [ ] Update README product framing and quickstart guidance
- [ ] Document new agent-level selectors and runtime fallback behavior
- [ ] Document custom plugin authoring for the new seam kinds
- [ ] Document builtin seam implementations and public exports

### Task 5: Add a composition example

**Files:**
- Create: `examples/runtime_composition/agent.json`
- Create: `examples/runtime_composition/run_demo.py`
- Modify: `examples/README.md`
- Modify: `docs-v2/examples.md`

- [ ] Show one agent combining `safe` + `filesystem` + `summarizing`
- [ ] Keep the example minimal and deterministic enough for local smoke usage

### Task 6: Verify and ship in small commits

**Files:**
- No fixed file list

- [ ] Run focused tests while implementing
- [ ] Run `uv run pytest -q`
- [ ] Commit in small batches by change family
- [ ] Push each stable batch
