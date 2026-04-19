## ADDED Requirements

### Requirement: Modular command package layout

The `openagents/cli/` package SHALL organize every subcommand as a single module under `openagents/cli/commands/<name>.py`, each exposing exactly two public callables: `add_parser(subparsers)` and `run(args) -> int`. The top-level `openagents/cli/main.py` SHALL contain only a registry of command names, a lazy-import dispatcher, and the root `argparse.ArgumentParser`. The existing modules `schema_cmd.py`, `validate_cmd.py`, and `list_plugins_cmd.py` SHALL be relocated under `commands/` and MUST keep their previous import paths available as thin re-export shims so external code importing them directly continues to work.

#### Scenario: Adding a new subcommand requires one module plus one test

- **WHEN** a contributor adds `openagents/cli/commands/foo.py` with `add_parser` and `run` and appends `"foo"` to the registry list in `main.py`
- **THEN** `openagents foo --help` prints the new command's help, `openagents --help` lists it under available subcommands, and no other module in `openagents/cli/` needs editing

#### Scenario: Legacy import paths remain stable

- **WHEN** an external caller imports `from openagents.cli.schema_cmd import run`
- **THEN** the import succeeds and `run` is the same callable as `openagents.cli.commands.schema.run`

### Requirement: `openagents` binary installed via entry point

The project `pyproject.toml` SHALL declare `[project.scripts] openagents = "openagents.cli.main:main"` (already present as of 0.4.0) so that after `uv sync` or `pip install io-openagent-sdk` an `openagents` executable is available on `PATH`. An optional dependency group `cli` SHALL bundle `questionary` and `watchdog` (and reuse the existing `rich` / `yaml` extras via `io-openagent-sdk[rich,yaml]`) for the richer developer experience, and `io-openagent-sdk[cli]` MUST install these extras.

#### Scenario: Post-install binary is discoverable

- **WHEN** a fresh environment runs `uv sync` then `openagents --help`
- **THEN** the CLI help is printed with exit code `0` and no `ModuleNotFoundError` is raised

#### Scenario: `cli` extra pulls in Rich, questionary, watchdog, yaml

- **WHEN** `uv pip install 'io-openagent-sdk[cli]'` completes
- **THEN** `import rich`, `import questionary`, `import watchdog`, and `import yaml` all succeed in that environment (the last two are added by this change; the first two are satisfied transitively via the existing `rich` and `pptx`/`questionary` dependency trees)

### Requirement: Standard exit codes across all subcommands

Every `openagents` subcommand SHALL return one of the following integer exit codes from its `run(args)` function, and tests MUST assert on these codes rather than on stderr substrings:
- `0` — success
- `1` — user error: missing required argument, unknown subcommand, file not found, ambiguous selection
- `2` — validation error: config did not pass `load_config`, strict-mode unresolved plugin type, invalid JSON/YAML
- `3` — runtime error: LLM call failed, plugin raised during `setup`/`execute`/`writeback`, session persistence failed

#### Scenario: Missing required input returns code 1

- **WHEN** `openagents run examples/quickstart/agent.json` is invoked without `--input`, `--input-file`, and no data on stdin
- **THEN** the process exits with code `1` and stderr names the missing argument

#### Scenario: Malformed agent.json returns code 2

- **WHEN** `openagents validate path/to/broken.json` is called on a file that fails `load_config`
- **THEN** the process exits with code `2` and stderr prefix is `ConfigLoadError:` or `ConfigValidationError:`

#### Scenario: LLM failure during run returns code 3

- **WHEN** `openagents run ...` executes and the underlying LLM client raises
- **THEN** the process exits with code `3` and the raised exception type + message are printed to stderr

### Requirement: `openagents init` scaffolds a new project from templates

The `init` subcommand SHALL create a new directory containing a runnable OpenAgents project from one of three bundled templates (`minimal`, `coding-agent`, `pptx-wizard`). It MUST prompt for project name, provider (anthropic, openai-compatible, mock), and API-key env-var name using `questionary` when available and falling back to positional/flag arguments otherwise. Generated files MUST include `agent.json`, a `README.md`, and any provider-specific stub code required to run `openagents run ./agent.json` immediately.

#### Scenario: Non-interactive invocation succeeds

- **WHEN** `openagents init my-agent --template minimal --provider mock --yes` runs in a directory that does not contain `my-agent/`
- **THEN** the directory `my-agent/` is created, it contains at minimum `agent.json` and `README.md`, and `openagents validate my-agent/agent.json` returns `0`

#### Scenario: Collision with existing directory is refused

- **WHEN** `openagents init my-agent --template minimal --yes` runs and `my-agent/` already exists and is non-empty
- **THEN** the process exits with code `1`, no files are overwritten, and stderr instructs the user to pass `--force` or choose a different name

#### Scenario: `--force` overwrites an existing directory

- **WHEN** `openagents init my-agent --template minimal --provider mock --yes --force` runs and `my-agent/` already contains a stale `agent.json`
- **THEN** the stale file is replaced, a fresh scaffold is written, and exit code is `0`

### Requirement: `openagents run` executes an agent against a single prompt

The `run` subcommand SHALL accept a path to an `agent.json`, resolve the input prompt from (in precedence order) `--input TEXT`, `--input-file PATH`, or stdin when piped, and execute the agent via `Runtime.from_config` + `Runtime.run_detailed`. When the config declares multiple agents, `--agent <id>` MUST be required; when a single agent is declared, it is selected implicitly. Default output MUST be a human-readable transcript; `--format json` MUST emit `RunResult.model_dump(mode="json")`; `--format events` MUST emit one JSON event per line (JSONL).

#### Scenario: Single-agent config runs with --input flag

- **WHEN** `openagents run examples/quickstart/agent.json --input "hello"` is invoked against a mock-provider config
- **THEN** the transcript is printed to stdout, the process exits `0`, and the last line contains the final output string

#### Scenario: Multi-agent config without --agent fails with code 1

- **WHEN** `openagents run multi.json --input "hi"` is invoked and the config declares two agents
- **THEN** the process exits with code `1` and stderr lists available agent IDs

#### Scenario: `--format events` emits JSONL to stdout

- **WHEN** `openagents run agent.json --input "x" --format events` is piped to `jq -c .`
- **THEN** `jq` parses every line as valid JSON and returns exit code `0`

#### Scenario: stdin input is consumed when no --input is given

- **WHEN** `echo "hello" | openagents run agent.json` runs
- **THEN** the prompt is the literal string `hello` and the command exits `0`

### Requirement: `openagents chat` provides an interactive multi-turn REPL

The `chat` subcommand SHALL start an interactive loop against a single agent from a given `agent.json`, reusing the same session across turns by holding the runtime's session open. It MUST support the following in-REPL slash commands: `/reset` (end the session and start a new one), `/save <path>` (persist the current `SessionArtifact` JSON to `<path>`), `/context` (print the assembled context from the most recent turn), `/tools` (print registered tool names + one-line descriptions), `/exit` (clean-exit with code `0`). Input prompts MUST use `questionary.text` when available and fall back to `input()` otherwise.

#### Scenario: `/exit` returns code 0

- **WHEN** the user types `/exit` at the REPL prompt
- **THEN** the process exits with code `0` and no traceback is printed

#### Scenario: `/save` writes a valid SessionArtifact JSON

- **WHEN** the user types `/save ./session.json` after at least one turn
- **THEN** the file `./session.json` exists, is valid JSON, and round-trips through `SessionArtifact.model_validate`

#### Scenario: `/reset` starts a new session id

- **WHEN** the user types `/reset` after one or more turns
- **THEN** subsequent turns use a different `session_id` than before the reset and no prior conversation history is carried over

### Requirement: `openagents dev` hot-reloads on config and plugin changes

The `dev` subcommand SHALL watch the config file and any source files referenced by the config for changes, and on change it MUST call `Runtime.reload()` and log which agents or plugins were re-bound. When `watchdog` is not importable, it MUST fall back to a polling loop (default 1s interval, overridable via `--poll-interval SECONDS`). It MUST debounce edit bursts by at least 150 ms so a single save does not trigger multiple reloads. Ctrl+C MUST exit cleanly with code `0`. The cache-keying invariants documented in `CLAUDE.md` (agent bundles by `(session_id, agent_id)`, LLM clients by `agent.id`) MUST be preserved — `dev` MUST NOT attempt to hot-swap top-level `runtime`, `session`, or `events` plugins.

#### Scenario: Editing agent.json triggers a single reload

- **WHEN** `openagents dev agent.json` is running and the file is saved after a change to `agents[0].llm.model`
- **THEN** exactly one `reload` log line is emitted within 2 seconds and subsequent `run` calls use the new model

#### Scenario: Polling fallback activates when watchdog is missing

- **WHEN** `openagents dev agent.json` starts in an environment where `watchdog` is not installed
- **THEN** a one-time stderr line warns that watchdog is missing and a polling loop begins using the default interval

### Requirement: `openagents new plugin` scaffolds a plugin skeleton

The `new plugin` subcommand SHALL accept a seam name and a plugin name and write a class-based Python plugin stub plus a matching test stub. Valid seam names MUST be exactly the union of `_BUILTIN_REGISTRY.keys()` and `"tool"`; any other seam name MUST cause exit code `1` with stderr listing valid seams. The scaffold MUST NOT auto-register the plugin — the user must add it to a config's `impl:` field or import it before config load (matching the contract in `openagents/plugins/loader.py`).

#### Scenario: Scaffolding a tool plugin produces importable Python

- **WHEN** `openagents new plugin tool my_calculator --path ./plugins/my_calculator.py` runs
- **THEN** the file exists and `python -c "import plugins.my_calculator"` succeeds with exit code `0`

#### Scenario: Unknown seam name is rejected with available list

- **WHEN** `openagents new plugin not-a-seam foo` runs
- **THEN** the process exits with code `1` and stderr contains each valid seam name

#### Scenario: Scaffolded test stub executes

- **WHEN** `openagents new plugin memory my_mem` has generated `tests/unit/test_my_mem.py`
- **THEN** `uv run pytest tests/unit/test_my_mem.py` returns exit code `0` without any code edits

### Requirement: `openagents doctor` diagnoses environment health

The `doctor` subcommand SHALL run a checklist covering: (1) Python version ≥ the project's declared minimum from `pyproject.toml`; (2) presence of optional extras (`rich`, `questionary`, `PyYAML`, `watchdog`, `anthropic`, `mcp`, `mem0ai`); (3) presence of common provider API-key environment variables (`ANTHROPIC_API_KEY`, `MINIMAX_API_KEY`, `OPENAI_API_KEY`) — reporting which are set without printing their values; (4) counts of registered builtin plugins per seam. When `--config PATH` is provided, it MUST additionally run `load_config` and report any validation errors. The process MUST exit `0` only when every "required" check passes; optional checks MUST report as warnings without affecting the exit code.

#### Scenario: Healthy environment exits 0

- **WHEN** `openagents doctor` is run in an environment that meets all required checks
- **THEN** the exit code is `0` and the stdout reports "OK" per section

#### Scenario: Missing required Python version fails

- **WHEN** `openagents doctor` runs under Python older than the `pyproject.toml` minimum
- **THEN** the exit code is `1` and stderr lists the detected and required versions

#### Scenario: API key values are never printed

- **WHEN** `openagents doctor` runs with `ANTHROPIC_API_KEY=secret-value-123` in the environment
- **THEN** no line of stdout or stderr contains the substring `secret-value-123`

### Requirement: `openagents config show` prints the fully-resolved AppConfig

The `config show` subcommand SHALL accept a path to an `agent.json`, run it through `load_config`, and print the resulting `AppConfig.model_dump(mode="json")` with `impl:` paths resolved via `get_builtin_plugin_class` / decorator registries and `${ENV}` substitutions applied. Output format MUST be controllable with `--format json|yaml` (default `json`). When `--redact` is passed, any leaf field whose JSON path contains any of the substrings `api_key`, `token`, `password`, or `secret` (case-insensitive) MUST be replaced by the literal string `***`.

#### Scenario: Resolved `impl` paths appear in output

- **WHEN** `openagents config show agent.json` runs and the config uses `pattern: { type: react }`
- **THEN** the output for `agents[0].pattern` contains an `impl` field resolving to the `react` pattern's Python dotted path

#### Scenario: `--redact` replaces api keys

- **WHEN** `openagents config show agent.json --redact` runs and the config contains `llm.api_key: sk-abc123`
- **THEN** the output contains the literal `"***"` at that path and does not contain `sk-abc123`

### Requirement: `openagents replay` renders persisted sessions

The `replay` subcommand SHALL accept a path to a `SessionArtifact` JSON file produced by `session.persist()` (or a raw transcript exported by `openagents run --format events`) and render it using the same formatter as `openagents run`. It MUST support `--turn N` to limit output to a single turn (1-indexed) and `--format json` to re-emit the normalized artifact as JSON.

#### Scenario: Valid session artifact is rendered

- **WHEN** `openagents replay ./session.json` runs against a valid `SessionArtifact` JSON
- **THEN** the process exits `0` and prints at least one tool-call or message panel

#### Scenario: `--turn` limits rendered content

- **WHEN** `openagents replay ./session.json --turn 2` runs against an artifact with three turns
- **THEN** only turn 2 is rendered and the output does not contain turn 1 or turn 3 content

### Requirement: `openagents completion <shell>` emits shell completion scripts

The `completion` subcommand SHALL support emitting completion scripts for the shells `bash`, `zsh`, `fish`, and `powershell`. Given a shell name as positional argument, it MUST print a complete, syntactically valid completion script for that shell to stdout, derived from the argparse tree via `_actions` introspection. The script MUST include every subcommand and every flag known to the root parser at invocation time.

#### Scenario: Bash completion script is syntactically valid

- **WHEN** `openagents completion bash | bash -n` runs
- **THEN** `bash -n` exits with code `0` (no parse errors)

#### Scenario: Unknown shell name is rejected

- **WHEN** `openagents completion tcsh` runs
- **THEN** the process exits with code `1` and stderr lists the four supported shell names

### Requirement: `openagents version` reports SDK and environment versions

The `version` subcommand SHALL print a single line of the form `openagents <sdk-version> python <py-version> extras [<list>]` using `importlib.metadata.version("io-openagent-sdk")` for the SDK version. With `--verbose`, it MUST instead print a Rich-formatted table (or plain-text fallback when Rich is not installed) including per-seam builtin plugin counts. With `--format json`, it MUST emit a single JSON object with keys `sdk`, `python`, `extras`, `builtin_plugin_counts`.

#### Scenario: Default output is a single informative line

- **WHEN** `openagents version` is invoked
- **THEN** stdout contains exactly one line starting with `openagents ` and the exit code is `0`

#### Scenario: `--format json` produces parseable output

- **WHEN** `openagents version --format json` is piped to `jq .sdk`
- **THEN** `jq` prints a quoted version string and exits `0`

### Requirement: Graceful degradation when optional extras are missing

Every subcommand that uses an optional dependency (`rich`, `questionary`, `watchdog`, `PyYAML`) SHALL detect the missing dependency via `importlib.util.find_spec` at command entry and continue with a plain-text fallback where feasible, printing a single stderr hint pointing to `pip install io-openagent-sdk[cli]`. No subcommand MAY raise `ImportError` to the user as a result of an optional extra being absent.

#### Scenario: `openagents run` still works without Rich

- **WHEN** Rich is not installed and `openagents run agent.json --input hi` runs against a mock-provider config
- **THEN** the process exits `0`, transcript is still printed in plain text, and a single stderr hint about `[cli]` extras is emitted

#### Scenario: `openagents dev` falls back to polling without watchdog

- **WHEN** `watchdog` is not installed and `openagents dev agent.json` starts
- **THEN** the process does not raise `ImportError`, a fallback poll loop runs, and a single stderr hint is emitted

### Requirement: Test coverage floor preserved

Every new subcommand SHALL have a unit test file at `tests/unit/test_cli_<command>.py` covering the happy path, the primary error path, and at least one argparse edge case (unknown flag or missing required argument). The repo-wide coverage floor of **92%** declared in `pyproject.toml` MUST NOT be lowered to accommodate the new CLI code, and no new file MAY be added to the coverage exclusion list unless it is an optional-extra integration (matching the existing rationale for `mem0_memory.py`, `mcp_tool.py`, `sqlite_backed.py`, `otel_bridge.py`).

#### Scenario: Coverage check still passes

- **WHEN** `uv run coverage run -m pytest && uv run coverage report` is run after all subcommands are merged
- **THEN** the overall coverage is ≥ 92% and the command exits `0`

#### Scenario: Every new subcommand has its own test file

- **WHEN** the change is archived
- **THEN** for every module under `openagents/cli/commands/*.py` there exists a matching `tests/unit/test_cli_<name>.py`
