## Why

The current `openagents` CLI exposes only three thin inspection utilities (`schema`, `validate`, `list-plugins`). Users who adopt the SDK today have to hand-write their own entry scripts to actually *run* an agent, scaffold a new project, iterate on a plugin, or diagnose a broken config. Comparable frameworks (Mastra, CrewAI, LangChain CLI, FastAPI/Uvicorn, Ruff) ship a much richer CLI that covers the full developer loop — scaffold → run → iterate → deploy — and that gap is the single biggest source of "I don't know where to start" feedback for new adopters. This change brings the builtin CLI up to parity by borrowing the proven primitives from those ecosystems without pushing product semantics into the kernel.

## What Changes

- Add `openagents init` to scaffold a new project from bundled templates (`minimal`, `coding-agent`, `pptx-wizard`) with prompts for API key / provider, modeled on `mastra init` and `crewai create`.
- Add `openagents run` to execute an `agent.json` against a single prompt / input file and print (or stream) the transcript + final output — the missing "just run my agent" command.
- Add `openagents chat` (interactive REPL) on top of the existing `wizard.py` Rich/questionary layer for multi-turn local sessions, with `/commands` (reset, save, show-context, show-tools).
- Add `openagents dev` — a reload-on-change wrapper around `Runtime.reload()` that watches the config file and plugin source trees (mirrors `uvicorn --reload` / `mastra dev`).
- Add `openagents new plugin <seam> <name>` to scaffold class-based plugin skeletons (tool, memory, pattern, context_assembler, tool_executor, execution_policy, followup_resolver, response_repair_policy) with a matching test stub.
- Add `openagents doctor` to check Python version, installed extras (yaml, rich, questionary, anthropic, mcp, mem0), provider env vars, and config health — a single command that tells a stuck user what's missing.
- Add `openagents config show` to print the fully-resolved `AppConfig` (JSON or YAML) with `impl` paths expanded, environment variable substitutions applied, and optional `--redact` for secrets.
- Add `openagents replay` to pretty-print a persisted `SessionArtifact` / transcript JSON back to the terminal (Rich panels for tool calls, responses, assembled context).
- Add `openagents completion <shell>` to emit bash/zsh/fish/powershell completion scripts generated from the argparse tree.
- Add `openagents version` that reports SDK version, Python version, detected extras, and registered builtin seam counts in one line.
- Modularize `openagents/cli/` into a dispatch + per-command package layout (one file per subcommand, shared `_rich.py` / `_wizard.py` helpers) so new subcommands don't bloat `main.py`.
- Formalize the existing `[project.scripts]` entry `openagents = "openagents.cli.main:main"` (already present) and introduce a new `[project.optional-dependencies] cli` extra that reuses the existing `rich`/`yaml` extras and adds `questionary` + `watchdog` on top.

No **BREAKING** changes: the three existing subcommands (`schema`, `validate`, `list-plugins`) keep their current flags and output format. New commands are additive.

## Capabilities

### New Capabilities
- `builtin-cli`: End-to-end developer CLI surface for the OpenAgents SDK — project scaffolding, run/chat/dev loops, plugin scaffolding, config inspection, environment diagnostics, session replay, and shell completion. Owns every `openagents <subcommand>` command and their argparse contract, output formats, and exit codes.

### Modified Capabilities
<!-- None — the three existing commands remain behaviorally stable; any richer output they gain is additive and covered by the new `builtin-cli` capability spec. -->

## Impact

- **Code**: New package `openagents/cli/commands/` (one module per subcommand). `openagents/cli/main.py` becomes a small dispatcher + `build_parser()` that walks a registry of command modules. Existing `schema_cmd.py` / `validate_cmd.py` / `list_plugins_cmd.py` are moved into `commands/` (thin re-export shims kept for import-path stability if any test imports them directly).
- **Dependencies**: `rich` and `questionary` (already optional, used by `wizard.py` and the pptx example) are promoted from test-only to a declared `cli` extra. `watchdog` is added to the same `cli` extra for `openagents dev`. None become mandatory — graceful fallback when extras aren't installed (matches existing pattern in `wizard.py`).
- **APIs**: No change to kernel protocols in `openagents/interfaces/`. `Runtime.reload()` is used as-is by the `dev` command. `RunRequest` / `RunResult` are consumed by `run` / `chat` / `replay`.
- **Docs**: New `docs/cli.md` (Chinese-primary + `docs/cli.en.md`). `README*.md` quickstart sections updated to use `openagents run` / `openagents init` in place of hand-written scripts. `docs/developer-guide.md` cross-linked.
- **Tests**: Each subcommand gets a `tests/unit/test_cli_<cmd>.py` that exercises the argparse surface, exit codes, and happy + error paths. Integration coverage via `tests/integration/test_cli_run_smoke.py` using the mock LLM provider. Coverage floor (90%) maintained; no new exclusions.
- **Examples**: `examples/quickstart/` README rewritten to use `openagents run examples/quickstart/agent.json --input "hello"`; `examples/production_coding_agent/` similarly.
- **Packaging**: `pyproject.toml` gains `[project.scripts]` and a `cli` optional dependency group.
