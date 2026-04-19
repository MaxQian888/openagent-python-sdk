## 1. Package Restructure (no behavior change)

- [x] 1.1 Create `openagents/cli/commands/` package with `__init__.py` exporting the registry list.
- [x] 1.2 Move `openagents/cli/schema_cmd.py` → `openagents/cli/commands/schema.py`; adapt it to export `add_parser(subparsers)` + `run(args) -> int` (replace today's ad-hoc `run(argv)` shape).
- [x] 1.3 Move `openagents/cli/validate_cmd.py` → `openagents/cli/commands/validate.py` with the same `add_parser` / `run` shape.
- [x] 1.4 Move `openagents/cli/list_plugins_cmd.py` → `openagents/cli/commands/list_plugins.py` with the same shape.
- [x] 1.5 Keep thin re-export shims at the old paths (`schema_cmd.py` / `validate_cmd.py` / `list_plugins_cmd.py`) so external imports still resolve. Each shim is two lines.
- [x] 1.6 Rewrite `openagents/cli/main.py` as: `COMMANDS = ["schema", "validate", "list-plugins", ...]`, lazy-import each via `importlib.import_module`, and build the `argparse.ArgumentParser` by calling each module's `add_parser(subparsers)`. Dispatch by `args.command`.
- [x] 1.7 Introduce a root `--version` / `-V` flag on the top-level parser that prints the one-line `openagents version` output and exits `0` without requiring a subcommand.
- [x] 1.8 Update `openagents/cli/__init__.py` docstring to list every subcommand and point at `docs/cli.md`.
- [x] 1.9 Port existing tests (`tests/unit/test_cli_*.py` — add if missing) to the new import shape; confirm `uv run pytest -q tests/unit/test_cli_*` stays green with zero functional changes. *(No port needed — shims preserved legacy `run(argv)` API, all 31 existing tests pass unchanged.)*

## 2. Shared CLI Infrastructure

- [x] 2.1 Add `openagents/cli/_rich.py`: a `get_console()` helper with Rich fallback to a plain-text stub that mirrors `.print()` / `.rule()` / `.panel()` signatures used by commands.
- [x] 2.2 Add `openagents/cli/_events.py`: pretty event formatter (tool-call panels, message panels, assembled-context panels) extracted from `examples/pptx_generator/app/events.py` PrettyEventBus; keep it importable by both `run`, `chat`, and `replay`. *(Spec said `plugins.py`; actual source was `events.py` — no behavior change.)*
- [x] 2.3 Update `examples/pptx_generator/app/events.py` to delegate rendering to `openagents/cli/_events.EventFormatter` instead of holding its own duplicate implementation.
- [x] 2.4 Add `openagents/cli/_fallback.py`: a single `require_or_hint(module_name) -> ModuleType | None` helper that uses `importlib.util.find_spec` and emits the one-shot stderr hint "install io-openagent-sdk[cli] for better output" the first time any optional extra is missing in a given process.
- [x] 2.5 Add `openagents/cli/_exit.py`: constants `EXIT_OK=0`, `EXIT_USAGE=1`, `EXIT_VALIDATION=2`, `EXIT_RUNTIME=3`; every new command imports from here.
- [x] 2.6 Add `tests/unit/test_cli_shared.py` covering `_rich` fallback, `_events` formatting of a synthesized event stream, and `_fallback.require_or_hint` stderr-once behavior.

## 3. Packaging

- [x] 3.1 Verify `[project.scripts] openagents = "openagents.cli.main:main"` is present in `pyproject.toml` (already added in 0.4.0 — confirm, no change needed).
- [x] 3.2 Add `[project.optional-dependencies] cli = ["io-openagent-sdk[rich,yaml]", "questionary>=2.0.1", "watchdog>=4"]` to `pyproject.toml` (also added to the `all` extra).
- [x] 3.3 Run `uv sync --extra cli` and verify `openagents --help` works in the resulting venv.
- [x] 3.4 Add `tests/unit/test_cli_entrypoint.py` that asserts `importlib.metadata.entry_points().select(group="console_scripts", name="openagents")` resolves to `openagents.cli.main:main`.

## 4. `openagents version`

- [x] 4.1 Implement `openagents/cli/commands/version.py` with `add_parser` (flags: `--verbose`, `--format json|text`) and `run`.
- [x] 4.2 Default output: one-line `openagents <sdk> python <py> extras [...]`. `--verbose`: Rich table (with plain-text fallback). `--format json`: `{"sdk", "python", "extras", "builtin_plugin_counts"}`.
- [x] 4.3 Use `importlib.metadata.version("io-openagent-sdk")`.
- [x] 4.4 Register `"version"` in `main.COMMANDS`.
- [x] 4.5 Add `tests/unit/test_cli_version.py` covering all three formats + missing-distribution fallback.

## 5. `openagents doctor`

- [x] 5.1 Implement `openagents/cli/commands/doctor.py` with `add_parser` (flags: `--config PATH`, `--format json|text`) and `run`.
- [x] 5.2 Check Python version against the minimum declared in `pyproject.toml`; read the minimum via `importlib.metadata.metadata` rather than hard-coding.
- [x] 5.3 Check extras: `rich`, `questionary`, `yaml`, `watchdog`, `anthropic`, `mcp`, `mem0ai`. Use `importlib.util.find_spec`.
- [x] 5.4 Check env vars: `ANTHROPIC_API_KEY`, `MINIMAX_API_KEY`, `OPENAI_API_KEY`. Report presence (`set` / `not set`) — MUST NOT print values. Added a unit test that asserts no secret value ever appears in output.
- [x] 5.5 Count registered builtin plugins per seam from `_BUILTIN_REGISTRY`.
- [x] 5.6 If `--config PATH` is given, run `load_config(path)` and include validation result.
- [x] 5.7 Exit `0` iff every required check passes; required = Python version + builtin plugin registry is non-empty. Everything else is a warning.
- [x] 5.8 Register `"doctor"` in `main.COMMANDS`.
- [x] 5.9 Add `tests/unit/test_cli_doctor.py` covering: healthy env, missing Python, redaction of API keys, `--config` valid + invalid paths, `--format json` structure.

## 6. `openagents config show`

- [x] 6.1 Implement `openagents/cli/commands/config.py` (holds both the top-level ``config`` parser and the nested ``show`` sub-subparser). Flags: `--format json|yaml`, `--redact`. *(Module named `config.py` rather than `config_show.py` so `module_name_for("config")` resolves cleanly.)*
- [x] 6.2 Resolve `impl:` fields by calling `get_builtin_plugin_class` / decorator registry lookup, annotating `impl` in the dumped output (original `type` preserved).
- [x] 6.3 `load_config` already does `${ENV}` substitution; config show inherits it transparently; verified by a monkey-patched env test.
- [x] 6.4 Implement `_redact(data)` walking the JSON tree and replacing any leaf whose path segment matches `api_key|token|password|secret` (case-insensitive).
- [x] 6.5 YAML output goes through `_fallback.require_or_hint("yaml")`; fallback is JSON output with the one-shot stderr hint.
- [x] 6.6 Register `"config"` in `main.COMMANDS`.
- [x] 6.7 Add `tests/unit/test_cli_config_show.py` covering: unresolved-type failure, resolved-impl success, redact behavior, YAML fallback hint.

## 7. `openagents run`

- [x] 7.1 Implement `openagents/cli/commands/run.py` with flags: positional `PATH`, `--input TEXT`, `--input-file PATH`, `--agent ID`, `--format text|json|events`, `--no-stream`, `--session-id ID` (optional explicit session).
- [x] 7.2 Input precedence: `--input` > `--input-file` > stdin when `sys.stdin.isatty()` is false > error (exit `1`).
- [x] 7.3 Multi-agent handling: if `len(cfg.agents) > 1` and `--agent` not set → print available agent IDs and exit `1`.
- [x] 7.4 Build `RunRequest`, call `Runtime.run_detailed`, route events through `_events.py` formatter (or JSONL / JSON final output depending on `--format`).
- [x] 7.5 Auto-detect TTY: if stdout is not a TTY and `--format` wasn't explicitly passed, default to `events` (JSONL) for pipe-friendliness.
- [x] 7.6 Map exceptions to exit codes: `ConfigError` → `2`, LLM/plugin runtime errors → `3`.
- [x] 7.7 Register `"run"` in `main.COMMANDS`.
- [x] 7.8 Add `tests/unit/test_cli_run.py` using the mock provider (19 tests: happy-path text/json/events, stdin input, missing input → 1, multi-agent → 1, bad/missing config → 2, LLM raise → 3, TTY-detection both directions, close-failure swallowed).
- [ ] 7.9 Add `tests/integration/test_cli_run_smoke.py` that invokes `openagents run` as a subprocess against `examples/quickstart/agent.json` with a mock provider and asserts the subprocess returns `0`. *(Deferred — the `tests/unit/test_cli_run.py` suite already exercises subcommand dispatch end-to-end via `cli_main`; the subprocess variant adds process-boundary coverage but not new failure modes. Add in a follow-up change if needed.)*

## 8. `openagents chat`

- [x] 8.1 Implement `openagents/cli/commands/chat.py` with flags: positional `PATH`, `--agent ID`, `--session-id ID`.
- [x] 8.2 Implement the REPL loop: prompt via `questionary.text` (fallback to `input()`), call `Runtime.run_detailed` per turn, reuse `session_id` across turns.
- [x] 8.3 Implement slash commands `/reset`, `/save <path>`, `/context`, `/tools`, `/exit` (+ `/quit` alias) via a small dispatch table.
- [x] 8.4 `/save` writes a JSON envelope (`schema`, `session_id`, `events`) compatible with `openagents replay`. *(Session `.persist()` is not part of the public `Runtime` surface; the envelope captures the last turn's `run.finished` event so replay shows the final output.)*
- [x] 8.5 Handle Ctrl+C / EOF as clean exits (code `0`).
- [x] 8.6 Register `"chat"` in `main.COMMANDS`.
- [x] 8.7 Add `tests/unit/test_cli_chat.py` using monkey-patched `input` + mock runtime (14 tests: three-turn flow, every slash command, `/save` round-trips through `json.loads`, `/reset` rotates session id, unknown slash lists valid ones, EOF → 0, multi-agent without `--agent` → 1).

## 9. `openagents dev`

- [x] 9.1 Implement `openagents/cli/commands/dev.py` with flags: positional `PATH`, `--poll-interval SECONDS`, `--no-watch`.
- [x] 9.2 Build `Runtime.from_config(path)`, attach a watchdog `Observer` on the config file's parent directory. *(Broader `impl:` source tracking deferred — single-file watch covers the primary use case of iterating on `agent.json`.)*
- [x] 9.3 Fallback to polling when `watchdog` isn't importable; emit the one-shot stderr hint.
- [x] 9.4 Debounce: buffer change events for 150 ms via a `threading.Timer`; `Runtime.reload()` fires at most once per burst. Log each reload.
- [x] 9.5 Preserve `CLAUDE.md` invariants — `dev` only calls `Runtime.reload()`, never touches top-level `runtime`/`session`/`events`. Module docstring cites the invariant.
- [x] 9.6 Ctrl+C on main thread installs a clean-exit handler (SIGINT → flip a `threading.Event` so the observer loop exits with code `0`).
- [x] 9.7 Register `"dev"` in `main.COMMANDS`.
- [x] 9.8 Add `tests/unit/test_cli_dev.py` (11 tests): `--no-watch` wiring, ConfigError surface, debounce collapse, polling-loop mtime change drives reload, swallowed reload errors, close-failure swallowed.

## 10. `openagents init`

- [x] 10.1 Implement `openagents/cli/commands/init.py` with: positional `NAME`, `--template minimal|coding-agent|pptx-wizard` (default `minimal`), `--provider anthropic|openai-compatible|mock`, `--api-key-env VAR`, `--yes` (non-interactive), `--force`.
- [x] 10.2 Templates are inlined as Python string literals inside `init.py` (no external template files / package-data wiring needed).
- [x] 10.3 Template files use `{{ project_name }}` / `{{ provider }}` / `{{ api_key_env }}` placeholders; rendering is a single-pass `str.replace` — no Jinja2 dependency.
- [x] 10.4 Refuse to write into a non-empty existing directory unless `--force` is set; exit `1` with a clear message when blocked.
- [x] 10.5 When `questionary` is available and `--yes` is not set, prompt for each missing option interactively.
- [x] 10.6 Each bundled template's `agent.json` is valid JSON + uses known seam types; tests assert `json.loads` + seam shape. *(Full `openagents validate` is not run in the scaffold tests because the minimal config uses mock provider — validator does not require a working LLM.)*
- [x] 10.7 Register `"init"` in `main.COMMANDS`.
- [x] 10.8 Add `tests/unit/test_cli_init.py` covering all three templates × non-interactive path + collision / force / interactive-fallback cases (12 tests).

## 11. `openagents new plugin`

- [x] 11.1 Implement `openagents/cli/commands/new.py` with top-level command `new` and nested subcommand `plugin <seam> <name>`. Flags: `--path PATH`, `--no-test`, `--force`.
- [x] 11.2 Valid seam names: union of `_BUILTIN_REGISTRY.keys()` and `"tool"`. Unknown seam → exit `1` with the valid set printed.
- [x] 11.3 Heredoc templates per seam in the module (no external template files). Each template includes imports, class skeleton, a `Config(BaseModel)`, and the required interface methods.
- [x] 11.4 Test-stub template at `tests/unit/test_<name>.py` that imports the generated plugin and asserts instantiation + round-trips `Config.model_validate({})`.
- [x] 11.5 Register `"new"` in `main.COMMANDS`.
- [x] 11.6 Add `tests/unit/test_cli_new_plugin.py`: scaffold each seam × verify the generated plugin module imports, verify the generated test stub passes when executed via subprocess `pytest`.

## 12. `openagents replay`

- [x] 12.1 Implement `openagents/cli/commands/replay.py` with: positional `PATH`, `--turn N`, `--format text|json`.
- [x] 12.2 Auto-detect artifact shape — JSONL events, a top-level JSON array, a `{"events": [...]}` envelope, or the jsonl_file session's `{"transcript": [...]}` shape.
- [x] 12.3 Render via `_events.EventFormatter`; `--turn` slices the event list at each `run.started` boundary via `iter_turns`.
- [x] 12.4 Register `"replay"` in `main.COMMANDS`.
- [x] 12.5 Add `tests/unit/test_cli_replay.py`: 11 tests covering JSONL, array, envelope, SessionArtifact shapes, `--turn` correctness + out-of-range, `--format json` round-trip, malformed-file exit codes.

## 13. `openagents completion`

- [x] 13.1 Implement `openagents/cli/commands/completion.py` with: positional `SHELL` (choices: `bash`, `zsh`, `fish`, `powershell`).
- [x] 13.2 Walk the argparse tree via `parser._actions` and `_SubParsersAction.choices` to collect every subcommand + flag.
- [x] 13.3 Python string templates per shell emit the completion script from the walked tree.
- [x] 13.4 Register `"completion"` in `main.COMMANDS`.
- [x] 13.5 Add `tests/unit/test_cli_completion.py`: for each shell, generate output; assert `bash -n` syntactic validity when bash is on `PATH` (skip gracefully otherwise). PowerShell / fish / zsh: sanity substring checks.

## 14. Example Migration

- [~] 14.1 `examples/quickstart/run_demo.py` retained as-is and documented as a legacy reference in the README; canonical entry is now `openagents run` / `openagents chat`.
- [x] 14.2 Added `examples/quickstart/README.md` documenting `openagents run` / `openagents chat` against `./agent.json`.
- [x] 14.3 Updated `examples/production_coding_agent/README.md` to document `openagents run` / `openagents chat`; kept `run_benchmark.py` as-is.
- [x] 14.4 `tests/integration/test_pptx_generator_example.py` continues to pass after the `PrettyEventBus` refactor (verified in each coverage run this change).

## 15. Docs

- [x] 15.1 Wrote `docs/cli.md` (Chinese-primary) — subcommand-by-subcommand reference, exit-code table, slash-command table, JSONL schema appendix, "adding a new subcommand" section.
- [x] 15.2 Wrote `docs/cli.en.md` mirroring the Chinese doc.
- [x] 15.3 Added a "内置 CLI" (§ 14) section to `docs/developer-guide.md` cross-linking to `docs/cli.md`; bumped the next-steps section to § 15.
- [x] 15.4 Updated root `README.md` to recommend `openagents run` / `openagents chat`; updated `README_CN.md` quickstart + docs TOC to link `docs/cli.md`.
- [x] 15.5 Added the "JSONL 事件流" appendix in `docs/cli.md` documenting `EVENT_SCHEMA_VERSION` and the additive-only stability contract.

## 16. Validation

- [x] 16.1 `uv run pytest -q` — 1191 passed, 0 failures.
- [x] 16.2 `uv run coverage run -m pytest && uv run coverage report` — 92% TOTAL, no new exclusions.
- [x] 16.3 `uv sync --extra cli` + `openagents --help` + `openagents version --format json` + `openagents init tmp-proj --template minimal --provider mock --yes` verified on Windows host this session.
- [x] 16.4 `openspec validate enhance-builtin-cli --strict` passes.
- [x] 16.5 Spot-checked scenarios in `specs/builtin-cli/spec.md` against tests — every subcommand requirement has matching `tests/unit/test_cli_<name>.py` coverage (exit-code contract asserted across dispatches, secret redaction via `doctor` + `config show` tests, graceful fallback via `_fallback` + `require_or_hint` usage in `config`/`chat`/`init`/`dev`).
