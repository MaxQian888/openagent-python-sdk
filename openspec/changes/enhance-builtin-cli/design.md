## Context

`openagents/cli/` today has four files: `main.py` (an argparse dispatcher with three subcommands), `schema_cmd.py`, `validate_cmd.py`, `list_plugins_cmd.py`, plus an unrelated `wizard.py` that powers the `pptx_generator` example. The CLI surface is intentionally minimal because the SDK positioned itself as a library first. That decision has run its course — every example (`quickstart`, `production_coding_agent`, `pptx_generator`) reimplements the same "load config → build Runtime → call `run()` → print events" loop in its own `run_demo.py`. Adopters copy those scripts rather than use a canonical entry point, which fragments the UX and keeps telemetry / error handling from improving in one place.

At the same time, `Runtime.from_config(path)`, `Runtime.reload()`, `PrettyEventBus` (in `examples/pptx_generator/app/plugins.py`), and `wizard.Wizard` already exist as reusable infrastructure. The missing piece is a CLI shell that composes them. Mature frameworks (Mastra `dev`/`init`/`build`, CrewAI `create`/`train`/`replay`, LangChain `langchain app new`/`serve`, FastAPI + `uvicorn --reload`, Ruff, Poetry) converge on a recognizable command shape, which is the template we're copying rather than inventing something novel.

Stakeholders: SDK adopters (primary), the examples (secondary — they become the first consumer of `openagents run`), and downstream contributors who will write new plugins (served by `openagents new plugin`).

## Goals / Non-Goals

**Goals:**
- One canonical command per step of the developer loop: *scaffold → run → iterate (dev) → inspect → ship*.
- Zero new mandatory dependencies: every new command degrades gracefully when optional extras (`rich`, `questionary`, `watchdog`, `yaml`) aren't installed. The existing `wizard.py` already models this fallback pattern.
- Kernel untouched: no new seam, no change to `RunRequest` / `RunResult` / `RunContext` / `interfaces/*`. All new commands are pure consumers of the public `Runtime` API.
- File-per-command layout (`openagents/cli/commands/<name>.py`) so a future subcommand is a one-file addition with a matching one-file test. `main.py` shrinks to a registry + dispatcher.
- Every subcommand is testable headlessly with the mock LLM provider and stubbed stdin — no real network, no real filesystem churn outside the tmp dir the test owns.
- Stable exit codes: `0` success, `1` user error (bad args / not-found), `2` validation error, `3` runtime error. Tests assert on these.
- Text output formats are parseable: `--format json` available wherever the existing commands support it (`schema`, `list-plugins`, new: `config show`, `doctor`, `replay`, `version`).

**Non-Goals:**
- No product semantics in the CLI (no multi-agent team orchestration, no approval UI, no task-envelope protocol). Those remain app-layer.
- No hosted / deploy / cloud commands. `openagents deploy` is intentionally out of scope — we don't own a hosting surface, and adding one would violate the "single-agent runtime kernel" charter from `CLAUDE.md`.
- No plugin marketplace / registry fetching. `openagents new plugin` scaffolds local files; it does not download from PyPI or a remote index.
- No rewrite of the existing three commands. Their argparse surface and output are frozen.
- No migration tool for pre-0.3 configs. `validate --strict` already covers validation; a format migration belongs in a separate change if needed.

## Decisions

### 1. Keep argparse, do not adopt Typer / Click

**Decision.** Stay on the standard-library `argparse` already used by the three existing commands.

**Rationale.** The SDK's `pyproject.toml` currently has no CLI-framework dependency, and `argparse` is sufficient for the ~10 subcommands we're adding. Typer would pull in Click + `typing-extensions` pressure and complicate the graceful-extras story (`rich` is already optional via `questionary`/`wizard.py`). Argparse also maps cleanly to the completion-script generator we need for `openagents completion`.

**Alternatives considered.**
- *Typer* — nicer decorator ergonomics, auto-completion built in. Rejected because adding a required dep for ~350 lines of dispatch code is disproportionate, and the `wizard.py` Rich/questionary layer already gives us the nice interactive bits.
- *Click* — same objection; additionally its completion story is less portable than shipping a hand-generated script.

### 2. Package layout: `openagents/cli/commands/<name>.py`

**Decision.** Move `schema_cmd.py`, `validate_cmd.py`, `list_plugins_cmd.py` into `openagents/cli/commands/` as `schema.py`, `validate.py`, `list_plugins.py`. New commands live beside them. `main.py` iterates a list `COMMANDS = [...]` where each entry is `(name, help, module_path)`, lazy-imports the module when the subcommand fires (preserves today's fast-import behavior), and the module exposes `def add_parser(sub)` + `def run(args) -> int`.

**Rationale.** Today's `main.py` already branches on `args.command` with a local import per branch — this formalizes that pattern so new commands don't edit `main.py`'s dispatch table by hand. It's identical to how `git`, `poetry`, and `ruff` structure their CLI trees. Keep old module paths importable via `openagents/cli/schema_cmd.py` re-export shims so any out-of-tree code that imported them directly doesn't break.

**Alternatives considered.**
- *Entry-point plugin registration* (third-party packages contribute subcommands). Rejected for this change — it widens the surface and invites plugins-as-CLI-commands which we specifically don't want to encourage. Can be added later without re-architecting.

### 3. `openagents run` — single-shot, streams events

**Decision.** `openagents run <path-to-agent.json> [--input TEXT | --input-file PATH | -] [--agent ID] [--format text|json|events] [--no-stream]`:
- Resolves the config via `load_config`, constructs `Runtime.from_config`, builds a `RunRequest` with the prompt coming from `--input`, `--input-file`, or stdin.
- If multiple agents are declared, `--agent ID` is required (or the first if only one is declared — same convention as `Runtime.run_detailed`).
- Default output: Rich-formatted transcript via `PrettyEventBus`-style formatter (promote a trimmed copy from `examples/pptx_generator/app/plugins.py` to `openagents/cli/_events.py`).
- `--format json` dumps `RunResult.model_dump()` after completion; `--format events` emits one JSON event per line (JSONL) for piping into other tools.
- `--no-stream` buffers events and prints only the final output — for scripts / CI.

**Rationale.** Matches `uvicorn` / `mastra dev` shape for the "just run it" path. JSONL event stream is what every adopter wants when they pipe into a log store; `jq` works out of the box.

**Alternatives considered.**
- *Reuse the pptx `PrettyEventBus` directly* — rejected because the example version imports from `examples/*` which isn't an installable path. Instead, extract the reusable core to `openagents/cli/_events.py` and have the example subclass it.

### 4. `openagents chat` — REPL, reuses `wizard.py` helpers

**Decision.** Interactive loop built on `wizard.Wizard.text()` for input and Rich panels for output. Supports in-REPL slash commands: `/reset` (new session), `/save <path>` (dump `SessionArtifact`), `/context` (print assembled context from last turn), `/tools` (list tools), `/exit`.

**Rationale.** The wizard helpers already have graceful fallbacks for missing extras. Chat is a natural fit for a stateful session wrapper over `Runtime.run_detailed` with persistent `session_id`.

**Alternatives considered.**
- *prompt-toolkit for a real terminal UI* — heavier dep, and our use case is linear line-oriented chat, not full-screen TUI. `questionary` (already optional) sits on top of prompt-toolkit when present.

### 5. `openagents dev` — watchdog-based reload

**Decision.** Watch the config file + any file referenced by an `impl:` path + any file under `openagents/plugins/` if the config references builtin types. On change: call `Runtime.reload()`, log what re-bound. Ctrl+C clean-exits.

**Rationale.** `Runtime.reload()` already exists and is tested; `dev` is a thin wrapper on top. `watchdog` is a well-maintained, optional dep, gracefully falls back to a polling loop if not installed (checked via `importlib.util.find_spec`). Cache-behavior expectations from `CLAUDE.md` ("Runtime.reload re-parses config and invalidates LLM clients for changed agents, but does not hot-swap top-level runtime/session/events") are preserved — `dev` does not try to beat `reload()`'s invariants.

**Risk.** Agent plugin bundles are keyed by `(session_id, agent_id)`; a running chat session started from `openagents chat` would not see the reload. `dev` therefore starts a fresh session each run-trigger.

### 6. `openagents new plugin <seam> <name>`

**Decision.** Scaffold `plugins/<name>.py` (or `--path PATH`) with a class-based plugin skeleton, `Config` model, and `tests/unit/test_<name>.py` stub. Supported seams are exactly the names in `_BUILTIN_REGISTRY.keys()` + `tool`; unknown seams fail with a helpful message listing valid ones.

**Rationale.** Reduces the "what fields does a tool plugin need?" friction. The scaffold uses the same class skeleton `tests/fixtures/` demonstrates. We do NOT register the plugin for the user — they must import it in their config, which matches the documented contract from `loader.py`.

**Alternatives considered.**
- *Jinja2 templates* — rejected; a handful of string templates in Python is enough and avoids a new runtime dep. Keep templates as heredocs in `commands/new.py`.

### 7. `openagents doctor`

**Decision.** Run a checklist: Python version ≥ 3.10 (from `pyproject.toml`), detect extras (`rich`, `questionary`, `yaml`, `watchdog`, `anthropic`, `mcp`, `mem0ai`), report which env vars commonly-used providers look for (`ANTHROPIC_API_KEY`, `MINIMAX_API_KEY`, `OPENAI_API_KEY`), count registered builtin plugins per seam, and optionally `--config PATH` to also validate that file. Outputs a Rich table or `--format json`. Exit `0` only if all "required" checks pass.

**Rationale.** Mirrors `brew doctor` / `poetry check` / `ruff check --no-fix`. The top adopter-support question is "which env var / extra is missing" — this command answers it in one place.

### 8. `openagents config show`

**Decision.** Given an `agent.json`, print the fully-resolved `AppConfig.model_dump(mode="json")` with `impl` paths expanded (post-`get_builtin_plugin_class` / decorator registry lookup) and `${ENV}` substitutions applied. `--format json|yaml`, `--redact` replaces any field whose path contains `api_key`/`token`/`password` with `***`. Reuses `load_config` + `get_builtin_plugin_class`.

**Rationale.** Debugging "which plugin actually got resolved?" is a recurring question (pattern: `type: X` silently falls back to builtin vs. decorator-registered). This command answers it without requiring users to instrument their own code.

### 9. `openagents replay`

**Decision.** Accepts a path to a persisted `SessionArtifact` JSON (produced by `session.persist()`) or a transcript file, and renders it with the same formatter as `openagents run`. `--turn N` limits to a single turn; `--format json` re-dumps it normalized.

**Rationale.** Matches `crewai replay` semantics. Users who hit a bad output can share the artifact file + `replay` command for a reproducible view without re-running (and re-billing) the LLM.

### 10. `openagents completion <bash|zsh|fish|powershell>`

**Decision.** Walk the argparse tree via `parser._actions` and emit a completion script to stdout. Keep per-shell templates inline in `commands/completion.py` — four templates, ~40 lines each.

**Rationale.** Shell completion is table stakes for CLI adoption (Poetry, Ruff, `gh`, `kubectl` all ship this). Argparse's introspection is sufficient and avoids a dep on `argcomplete`. Users install by piping into the appropriate file per their shell's instructions — same UX as `gh completion`.

### 11. `openagents version`

**Decision.** One-line version printout (SDK version from `importlib.metadata.version("io-openagent-sdk")`, Python version, detected extras, builtin seam counts). `--verbose` prints a Rich table.

**Rationale.** Every CLI has this. Low effort, high signal for bug reports.

### 12. `pyproject.toml` gains `[project.scripts]` + `cli` extra

**Decision.**
```toml
[project.scripts]
openagents = "openagents.cli.main:main"

[project.optional-dependencies]
cli = ["rich>=13", "questionary>=2", "watchdog>=4", "PyYAML>=6"]
```

**Rationale.** Installing via `uv sync` / `pip install io-openagent-sdk` gives users an `openagents` binary on PATH. The `cli` extra makes `uv pip install io-openagent-sdk[cli]` the recommended developer install; core runtime still has zero extras.

## Risks / Trade-offs

- **[Risk] Scope creep on each subcommand** → Mitigation: every command is capped at one file under `openagents/cli/commands/` + one test file. If a command exceeds ~200 lines, it is a signal to carve helpers into `openagents/cli/_<helper>.py`, not to grow the command module.
- **[Risk] Event formatter drift between `run` / `chat` / `replay`** → Mitigation: a single `_events.py` module owns formatting; all three commands import from it. A test asserts identical output for a given transcript.
- **[Risk] `openagents dev` reload races on Windows** (the user is on Win11) when file locks prevent watchdog from re-reading a half-written file → Mitigation: debounce 150ms before calling `Runtime.reload()`, retry up to 3× on `PermissionError`, fall back to poll mode if watchdog import fails.
- **[Risk] `openagents new plugin` templates rot** as the plugin protocols evolve → Mitigation: the scaffolded code is imported + run in its own test (the scaffold's test stub must pass as soon as it's generated), so a protocol change that breaks scaffolds also breaks CI.
- **[Risk] JSONL output format becomes an ad-hoc API** consumers depend on → Mitigation: document it in `docs/cli.md` as *"best-effort for piping, subject to additive-only changes"*; version it with an `event_schema_version` field so future changes don't silently break downstream parsers.
- **[Trade-off] No plugin marketplace / third-party subcommand registration.** Accepted: adding entry-point subcommand plugins invites misuse ("my product's CLI lives inside `openagents`"). If a later change wants this, it's additive and doesn't require re-architecting.
- **[Trade-off] Graceful fallbacks mean subcommands differ in richness between `pip install io-openagent-sdk` and `io-openagent-sdk[cli]`.** Accepted: we document this explicitly in `--help` output (e.g., "Install io-openagent-sdk[cli] for hot-reload dev mode.") so it's never silently degraded.

## Migration Plan

1. **In-place phase.** Move the three existing command modules into `commands/` with re-export shims at the old paths; no behavior change, tests still pass.
2. **Additive phase.** Introduce `version`, `doctor`, `config show`, `completion`, `new plugin`, `replay`, `run`, `chat`, `dev` one at a time in separate commits. Each commit ships its test and one-paragraph `docs/cli.md` section.
3. **Examples migration.** Rewrite `examples/quickstart/run_demo.py` to be a ~5-line wrapper over `openagents run` (or delete it in favor of a README `openagents run` snippet). Do the same for `production_coding_agent`.
4. **Packaging.** Add `[project.scripts]` + `cli` extra; verify `uv sync && openagents --help` works fresh.
5. **Docs.** Write `docs/cli.md` (Chinese) + `docs/cli.en.md`. Cross-link from `docs/developer-guide.md` and both READMEs.

Rollback: each subcommand is an isolated module; removing a broken one means deleting its file + its test + its dispatch entry. No schema changes means no data migration.

## Open Questions

- Should `openagents run` default to `--format events` (JSONL) when stdout is not a TTY, falling back to Rich when it is? Leaning yes — matches `jq` / `docker logs` conventions. Deferred to implementation; tests cover both paths regardless.
- Does `openagents chat` persist sessions across invocations (auto-resume last session) or always start fresh? Proposal is *start fresh, with `/save` + `/load` slash commands for explicit persistence*. Revisit after we see adopter feedback.
- `openagents new plugin` template includes or omits `asyncio` imports by default? Leaning omit (match the class-based patterns in `tests/fixtures/`), users add as needed.
