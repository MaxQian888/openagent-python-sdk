# Ruff Linting Support — Design

**Date:** 2026-04-18

## Goal

Add ruff as the project's linter with a conservative rule set (`E, F, I`) to catch pycodestyle errors, undefined names, and import ordering issues — with zero false-positive noise on the existing codebase.

## Configuration

Add `[tool.ruff]` and `[tool.ruff.lint]` sections to `pyproject.toml`:

- `target-version = "py310"` — matches `requires-python`
- `line-length = 120` — matches existing code style
- `select = ["E", "F", "I"]` — pycodestyle errors, pyflakes, isort
- `exclude` — `dist/`, `*.egg-info`, `.venv`

## Dependency

Add `ruff` to the `dev` optional-dependency group in `pyproject.toml` via `uv add --optional dev ruff`.

## Fix Pass

Run `ruff check --fix .` to auto-fix all auto-fixable violations (primarily import ordering). Any remaining violations are fixed manually.

## No Pre-commit

No `.pre-commit-config.yaml` exists; none will be created. `ruff check .` can be run manually or wired into CI later.

## Out of Scope

- Ruff formatter (`ruff format`) — not requested
- Type checking (mypy/pyright) — separate concern
- Stricter rule sets (bugbear, pyupgrade) — deferred, can be added incrementally
