# OpenAgents Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise coverage for `openagents/` to at least 90 percent with repeatable project-local tooling and focused TDD.

**Architecture:** Add coverage tooling and config first so the repo can measure the target consistently. Then use coverage output to identify the biggest uncovered kernel surfaces and close them with small, behavior-driven unit tests that execute real package code.

**Tech Stack:** Python, pytest, coverage, uv

---

### Task 1: Add Coverage Tooling

**Files:**

- Modify: `pyproject.toml`

- [ ] **Step 1: Add `coverage[toml]` to dev dependencies**
- [ ] **Step 2: Add `[tool.coverage.run]` and `[tool.coverage.report]` config scoped to `openagents/`**
- [ ] **Step 3: Run a baseline coverage command and capture the uncovered hotspots**

### Task 2: Lock Coverage Regression Tests

**Files:**

- Create or modify: focused test files under `tests/unit/`

- [ ] **Step 1: Write failing tests for the first uncovered public surface**
- [ ] **Step 2: Run the targeted test and verify it fails for the expected reason**
- [ ] **Step 3: Implement the minimal change only if the failing test exposes a real defect instead of pure missing coverage**
- [ ] **Step 4: Re-run the targeted test and verify it passes**

### Task 3: Close High-Leverage Module Gaps

**Files:**

- Modify: `tests/unit/test_exports_and_entrypoints.py` if created
- Modify: `tests/unit/test_runtime_sync_helpers.py`
- Modify: `tests/unit/test_hotreload.py`
- Modify: `tests/unit/test_llm_registry.py`
- Modify: `tests/unit/test_plugin_loader.py`

- [ ] **Step 1: Cover entry/export modules and sync helpers**
- [ ] **Step 2: Cover hotreload/build utility branches**
- [ ] **Step 3: Cover registry and plugin export branches**
- [ ] **Step 4: Re-run coverage after each wave and stop when total coverage reaches the target**

### Task 4: Verify The Target

**Files:**

- Test: `pyproject.toml`
- Test: `tests/unit/`
- Test: `tests/integration/`

- [ ] **Step 1: Run the full test suite**
- [ ] **Step 2: Run the full coverage command for `openagents/`**
- [ ] **Step 3: Confirm the reported total is at least 90 percent**
