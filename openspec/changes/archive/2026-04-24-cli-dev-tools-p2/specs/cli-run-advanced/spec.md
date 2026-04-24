## ADDED Requirements

### Requirement: `openagents run --dry-run` validates configuration without calling the LLM

The `openagents run` subcommand SHALL accept a `--dry-run` flag. When set, the command SHALL:
1. Load the config via `load_config(path)` (schema + Pydantic validation).
2. Construct `Runtime.from_config(path)` (plugin instantiation + capability checks via `loader.py`).
3. Print `dry-run OK: {N} agent(s), {M} seam(s) configured` to stdout and exit `0`.

It MUST NOT make any LLM API calls, subscribe to the event bus, or execute any pattern.
If `load_config` or `Runtime.from_config` raise `ConfigError`, the command SHALL print the exception to stderr and exit `2`.

#### Scenario: Dry-run exits 0 on valid config without LLM call

- **WHEN** `openagents run examples/quickstart/agent.json --input "hello" --dry-run` is invoked
- **THEN** the process exits `0`, stdout contains `dry-run OK`, and no LLM HTTP request is made

#### Scenario: Dry-run exits 2 on malformed config

- **WHEN** `openagents run broken.json --input "x" --dry-run` is invoked and `broken.json` fails schema validation
- **THEN** the process exits `2` and stderr starts with `ConfigError:` or `ConfigValidationError:`

#### Scenario: Dry-run ignores missing --input

- **WHEN** `openagents run agent.json --dry-run` is invoked without `--input`, `--input-file`, or stdin
- **THEN** the process exits `0` (no input needed since no run is performed) and stdout contains `dry-run OK`

---

### Requirement: `openagents run --timeout SECONDS` enforces a wall-clock limit

The `openagents run` subcommand SHALL accept `--timeout SECONDS` (float, positive). When set:
- The `run_detailed` call SHALL be wrapped in `asyncio.wait_for(..., timeout=seconds)`.
- If the timeout elapses, the command SHALL print `TimeoutError: run exceeded {N}s` to stderr and exit `3`.
- If `--timeout` is not passed, behavior is unchanged (no timeout).

#### Scenario: Run exits 3 on timeout

- **WHEN** `openagents run agent.json --input "x" --timeout 0.001` is invoked against an agent that takes >0.001 s
- **THEN** the process exits `3` and stderr contains `TimeoutError`

#### Scenario: Run completes normally when within timeout

- **WHEN** `openagents run agent.json --input "x" --timeout 60` is invoked and the run finishes in < 60 s
- **THEN** the process exits `0` (or `3` on runtime error, same as without `--timeout`)

---

### Requirement: `openagents run --batch JSONL` executes multiple inputs and outputs results as JSONL

The `openagents run` subcommand SHALL accept `--batch <path>` as a mutually exclusive alternative to `--input` / `--input-file` / stdin. `--batch` reads a JSONL file where each line is either:
- A JSON object with at minimum `"input_text"` key; optional `"session_id"` key; additional keys are passed through to the output but ignored by the runtime.
- A plain JSON string (treated as `input_text`).

For each record, the command SHALL:
1. Execute `runtime.run_detailed(RunRequest(agent_id=..., session_id=..., input_text=...))`.
2. Emit a result JSONL line to stdout immediately upon completion:
   `{"index": N, "input": "...", "output": "...", "stop_reason": "...", "latency_ms": N, "error": null}`.
   On failure: `"output": null, "error": "<ExceptionType>: <message>"`.

After all records complete, the command SHALL emit a summary line to **stderr**:
`Batch: {total} inputs, {ok} OK, {err} error(s) | p50={p50}s p95={p95}s`

Concurrency is controlled by `--concurrency N` (integer ≥ 1, default `1`). With `N=1` records are executed serially; with `N>1` up to N records run concurrently via `asyncio.Semaphore`.

Exit code: `0` if all records succeed; `3` if any record fails.

`--timeout` applies per record when both flags are present.

#### Scenario: Serial batch execution produces one output line per input

- **WHEN** `openagents run agent.json --batch inputs.jsonl` is invoked with a file containing 3 records
- **THEN** stdout contains exactly 3 JSONL lines, each with `index` 0, 1, 2 and `stop_reason` present; stderr contains the summary line

#### Scenario: Batch exit code is 3 when any record fails

- **WHEN** one of the 3 records causes a runtime error (e.g., the mock provider is configured to fail on turn 2)
- **THEN** the process exits `3`; the failed record's output line has `"error"` non-null

#### Scenario: `--batch` is mutually exclusive with `--input`

- **WHEN** `openagents run agent.json --batch inputs.jsonl --input "hello"` is invoked
- **THEN** the process exits `1` and stderr mentions the mutual exclusion

#### Scenario: Concurrent batch respects `--concurrency`

- **WHEN** `openagents run agent.json --batch inputs.jsonl --concurrency 3` is invoked with 6 records
- **THEN** at most 3 coroutines run simultaneously (verifiable via mock provider call sequencing) and all 6 output lines appear on stdout

#### Scenario: Batch summary latency is calculated over completed records

- **WHEN** a batch of 4 records completes (2 succeed in 1 s, 2 fail instantly)
- **THEN** the stderr summary line contains `p50` and `p95` values derived from the 4 latency measurements (including failures)
