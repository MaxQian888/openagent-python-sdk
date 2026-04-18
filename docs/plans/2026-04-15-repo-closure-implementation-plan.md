# Repo Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the repo migration by restoring a valid package landing page, aligning docs with the real tree, removing stale tests, and cleaning regenerable local artifacts.

**Architecture:** Keep the SDK code layout intact and repair the outer repository contract around it. Documentation becomes `README.md` plus `README_EN.md` / `README_CN.md` plus `docs/`, examples are documented from the real `examples/` tree only, and tests assert current repo truth instead of deleted subsystems.

**Tech Stack:** Python 3.10+, pytest, markdown docs, uv

---

### Task 1: Lock The Target Repo Contract

**Files:**

- Create: `tests/unit/test_repository_layout.py`
- Test: `pyproject.toml`
- Test: `.gitignore`
- Test: `README_EN.md`
- Test: `README_CN.md`
- Test: `docs/examples.md`
- Test: `examples/README.md`

- [ ] **Step 1: Write the failing repo-structure tests**
- [ ] **Step 2: Run `uv run pytest -q tests/unit/test_repository_layout.py` and verify it fails**
- [ ] **Step 3: Use the failures to drive doc and metadata fixes**

### Task 2: Rebuild The Documentation Entry Surface

**Files:**

- Create: `README.md`
- Create: `docs/repository-layout.md`
- Modify: `README_EN.md`
- Modify: `README_CN.md`
- Modify: `docs/README.md`
- Modify: `docs/examples.md`
- Modify: `examples/README.md`
- Modify: `docs/plugin-development.md`

- [ ] **Step 1: Add a short root `README.md` for package metadata and navigation**
- [ ] **Step 2: Add `docs/repository-layout.md` describing the real top-level structure**
- [ ] **Step 3: Update `README_EN.md` and `README_CN.md` to link into `docs/` and only mention maintained examples**
- [ ] **Step 4: Trim `docs/examples.md` and `examples/README.md` so they describe only `quickstart` and `production_coding_agent`**
- [ ] **Step 5: Update secondary doc references such as `docs/plugin-development.md` to point at real references**

### Task 3: Remove Historical Test Debt

**Files:**

- Delete: `tests/integration/test_custom_impl_example.py`
- Delete: `tests/integration/test_runtime_composition_example.py`
- Delete: `tests/integration/test_openagent_cli_runtime_integration.py`
- Delete: `tests/unit/test_openagent_cli_config.py`
- Delete: `tests/unit/test_openagent_cli_packaging.py`
- Delete: `tests/unit/test_openagent_cli_pattern.py`
- Delete: `tests/unit/test_openagent_cli_repl.py`
- Delete: `tests/unit/test_openagent_cli_tools.py`

- [ ] **Step 1: Remove tests that target deleted repo surfaces**
- [ ] **Step 2: Keep surviving integration coverage around `quickstart` and `production_coding_agent`**
- [ ] **Step 3: Re-run targeted repo-structure tests and related example tests**

### Task 4: Fix Ignore Rules And Clean Local Artifacts

**Files:**

- Modify: `.gitignore`

- [ ] **Step 1: Remove ignore rules that hide tracked repo structure such as `docs/`, `examples/`, and `README.md`**
- [ ] **Step 2: Keep ignore rules for real local artifacts such as `.venv/`, `.pytest_cache/`, `.uv-cache/`, and `*.pyc`**
- [ ] **Step 3: Delete regenerable artifacts from the workspace without touching `.venv/`**

### Task 5: Verify The Closed Repo

**Files:**

- Test: `tests/unit/test_repository_layout.py`
- Test: `tests/integration/test_runtime_from_config_integration.py`
- Test: `tests/integration/test_production_coding_agent_example.py`

- [ ] **Step 1: Run `uv run pytest -q tests/unit/test_repository_layout.py`**
- [ ] **Step 2: Run `uv run pytest -q tests/integration/test_runtime_from_config_integration.py tests/integration/test_production_coding_agent_example.py`**
- [ ] **Step 3: Run `uv run pytest -q`**
- [ ] **Step 4: Inspect `git status --short` to confirm the repo shape matches the intended closure**
