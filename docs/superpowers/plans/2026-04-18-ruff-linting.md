# Ruff Linting Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ruff as the project linter with conservative rules (`E, F, I`) and fix all existing violations.

**Architecture:** All configuration lives in `pyproject.toml` under `[tool.ruff]` and `[tool.ruff.lint]`. Ruff is added as a dev dependency via uv. No new files are created.

**Tech Stack:** ruff, uv, pyproject.toml

---

### Task 1: Add ruff dev dependency

**Files:**
- Modify: `pyproject.toml` (dev optional-dependencies section)

- [ ] **Step 1: Add ruff to dev optional-dependencies**

In `pyproject.toml`, find the `[project.optional-dependencies]` section and update the `dev` group:

```toml
[project.optional-dependencies]
dev = [
    "coverage[toml]>=7.6.0",
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.4.0",
    "io-openagent-sdk[rich]",
]
```

- [ ] **Step 2: Sync dependencies**

```bash
uv sync
```

Expected: ruff is installed. Verify with:

```bash
uv run ruff --version
```

Expected output (version may differ): `ruff 0.4.x`

- [ ] **Step 3: Commit**

```bash
rtk git add pyproject.toml uv.lock && rtk git commit -m "chore: add ruff dev dependency"
```

---

### Task 2: Add ruff configuration to pyproject.toml

**Files:**
- Modify: `pyproject.toml` (add `[tool.ruff]` and `[tool.ruff.lint]` sections)

- [ ] **Step 1: Append ruff config sections to pyproject.toml**

Add the following at the end of `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py310"
line-length = 120
exclude = [
    "dist",
    "*.egg-info",
    ".venv",
]

[tool.ruff.lint]
select = ["E", "F", "I"]
```

- [ ] **Step 2: Verify config is valid**

```bash
uv run ruff check --show-settings . 2>&1 | head -20
```

Expected: No errors; settings output shows `select = ["E", "F", "I"]`.

- [ ] **Step 3: Commit**

```bash
rtk git add pyproject.toml && rtk git commit -m "chore: configure ruff with E, F, I rules"
```

---

### Task 3: Run ruff and fix violations

**Files:**
- Modify: various `openagents/**/*.py` files as needed

- [ ] **Step 1: Run ruff in check-only mode to see all violations**

```bash
uv run ruff check .
```

Note the output — violations will be primarily `I001`/`I002` (import ordering) and possibly `F401` (unused imports) or `E` style issues.

- [ ] **Step 2: Auto-fix all auto-fixable violations**

```bash
uv run ruff check --fix .
```

Expected: Output lists files modified. Most `I` (isort) violations are auto-fixed. `F401` unused-import violations are **not** auto-fixed by default — they will remain listed.

- [ ] **Step 3: Re-run to see remaining violations**

```bash
uv run ruff check .
```

If output is empty — all violations are fixed, skip to Step 5.

If violations remain, they will be `F401` (unused imports) or `E` style issues that require manual review. Fix each one:

For `F401` (unused import) — remove the import if truly unused, or add `# noqa: F401` if it is a re-export that must stay (e.g., `__init__.py` re-exports):

```python
# In __init__.py files that intentionally re-export symbols:
from openagents.foo import Bar  # noqa: F401
```

For `E` violations — fix per the ruff message (e.g., whitespace, line length).

- [ ] **Step 4: Verify zero violations**

```bash
uv run ruff check .
```

Expected: No output (exit code 0).

- [ ] **Step 5: Run existing test suite to confirm no regressions**

```bash
uv run pytest -q
```

Expected: All tests pass (same as before the change).

- [ ] **Step 6: Commit**

```bash
rtk git add -u && rtk git commit -m "chore: fix ruff E/F/I violations across codebase"
```
