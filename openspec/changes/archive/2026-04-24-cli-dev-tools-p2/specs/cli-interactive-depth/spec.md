## ADDED Requirements

### Requirement: `chat /help` lists all available slash commands

The `openagents chat` REPL SHALL handle `/help` as a valid slash command. Invoking `/help` SHALL print a formatted table of all available slash commands and their usage to the console output stream. The list SHALL include at minimum: `/exit`, `/quit`, `/reset`, `/save <path>`, `/context`, `/tools`, `/history`, `/help`.

This requirement fixes the known defect where `/help` currently falls through to the "unknown slash command" error branch in `_dispatch_slash`.

#### Scenario: `/help` prints command reference

- **WHEN** the user types `/help` during a chat session
- **THEN** the output contains all slash command names and no "unknown slash command" error is printed

#### Scenario: `/help` does not exit the REPL

- **WHEN** the user types `/help`
- **THEN** the REPL continues running (no exit)

---

### Requirement: `chat /history` shows per-turn summaries for the current session

The `openagents chat` REPL SHALL handle `/history` as a valid slash command. Invoking it SHALL print a summary list of all completed turns in the current session, one line per turn, in the format:
`turn {N} | {stop_reason} | {first 80 chars of final_output}`

The history is in-memory only and is lost on `/reset` (session rotation) and on exit. A session that has had no completed turns SHALL print `(no turns yet)`.

#### Scenario: `/history` after two turns shows two entries

- **WHEN** the user sends two messages and then types `/history`
- **THEN** output contains exactly two `turn N` lines

#### Scenario: `/history` after `/reset` shows empty history

- **WHEN** the user sends a message, types `/reset`, then types `/history`
- **THEN** output contains `(no turns yet)` (history is tied to the current session)

#### Scenario: `/history` with no prior turns

- **WHEN** the user types `/history` before sending any message
- **THEN** output contains `(no turns yet)`

---

### Requirement: `chat --history FILE` resumes a previously saved session

The `openagents chat` subcommand SHALL accept `--history <path>` flag. When provided:
1. The file SHALL be read and parsed using the same format as files produced by `/save` (JSON envelope `{"schema": 1, "session_id": "...", "events": [...]}`).
2. The `session_id` from the file SHALL be used as the initial session ID for the REPL (not a freshly generated UUID), so a session backend with transcript persistence (e.g., `jsonl_file`) will continue that session.
3. A banner SHALL be printed to stderr: `resuming session <id> from <path>`.
4. If the file cannot be parsed or is missing the `session_id` field, the command SHALL exit `1` with a clear error message on stderr.
5. If the session backend has no persistence (e.g., `in_memory`), the behavior is correct (the session ID is reused) but the LLM will not see prior context; the command SHALL NOT attempt to detect or warn about this.

`--history` and `--session-id` SHALL be mutually exclusive; if both are passed the command exits `1`.

#### Scenario: Session ID is loaded from history file

- **WHEN** `openagents chat agent.json --history ./session.json` is invoked with a file containing `"session_id": "abc123"`
- **THEN** the banner prints `resuming session abc123` and the first LLM call uses that session ID

#### Scenario: Missing history file exits 1

- **WHEN** `--history /nonexistent.json` is passed
- **THEN** the process exits `1` with an error message referencing the file path

#### Scenario: Malformed history file exits 1

- **WHEN** `--history` points to a file that is not valid JSON or lacks `session_id`
- **THEN** the process exits `1` with a descriptive error message

#### Scenario: `--history` and `--session-id` conflict exits 1

- **WHEN** both `--history <file>` and `--session-id abc` are passed
- **THEN** the process exits `1` with a mutual-exclusion error

---

### Requirement: `dev --watch-also GLOB` triggers reload on additional file changes

The `openagents dev` subcommand SHALL accept one or more `--watch-also <glob>` flags (repeatable). Each glob is resolved relative to the current working directory. When any file matching a glob changes:
- The same debounced `Runtime.reload()` path is triggered as for the main config file.
- The log message SHALL include the file path that changed: `[watch] change: <path>`.

In watchdog mode, the unique parent directories from all expanded globs are added as additional `observer.schedule(...)` targets with `recursive=True`. In polling mode, the set of currently-existing files matching all globs is checked on each poll interval.

When `--watch-also` matches more than 1000 files at startup, the command SHALL print a warning to stderr: `[watch] warning: --watch-also matches {N} files; consider a narrower glob`.

#### Scenario: Plugin file change triggers reload

- **WHEN** `openagents dev agent.json --watch-also "plugins/**/*.py"` is running and a `.py` file under `plugins/` is modified
- **THEN** `[reload] runtime reloaded` appears in stderr within ~200 ms

#### Scenario: Config file change still triggers reload with --watch-also

- **WHEN** `--watch-also` is set and the main `agent.json` changes
- **THEN** reload is still triggered (the original watch is not replaced)

#### Scenario: Warning on large glob

- **WHEN** `--watch-also "**/*"` matches 1500 files at startup
- **THEN** stderr contains a warning about `--watch-also matches 1500 files`

---

### Requirement: `dev --test-prompt TEXT` automatically probes the agent after each reload

The `openagents dev` subcommand SHALL accept `--test-prompt <text>`. After each successful `Runtime.reload()`, the command SHALL:
1. Execute `runtime.run_detailed(RunRequest(agent_id=..., session_id="dev-probe", input_text=test_prompt))` with a hard timeout of 30 seconds.
2. On success: print to stderr `✓ reload OK | probe {N}ms: {output[:60]}`.
3. On runtime error or timeout: print to stderr `✗ probe failed: {ExcType}: {message}`.

The probe result does not affect the `dev` command's exit code (which is always `0` on clean Ctrl+C). The probe session id `"dev-probe"` is reused across reloads (constant, predictable, easy to find in session logs).

#### Scenario: Probe succeeds after clean reload

- **WHEN** `openagents dev agent.json --test-prompt "ping"` is running and the config file is saved
- **THEN** stderr contains `✓ reload OK | probe` with a latency annotation

#### Scenario: Probe failure is reported but dev continues

- **WHEN** the probe run raises a `RuntimeError` (e.g., LLM call fails)
- **THEN** stderr contains `✗ probe failed:` and the dev command continues watching (does not exit)

#### Scenario: Probe respects 30-second hard timeout

- **WHEN** `--test-prompt` is set and the agent hangs for > 30 s
- **THEN** stderr contains `✗ probe failed: TimeoutError` and the dev loop continues

#### Scenario: No probe without --test-prompt

- **WHEN** `openagents dev agent.json` is invoked without `--test-prompt`
- **THEN** no probe is run after reload (behavior identical to the current command)
