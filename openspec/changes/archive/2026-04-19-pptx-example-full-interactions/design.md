## Context

`examples/pptx_generator/` already wires a 7-stage pipeline (intent → env → research → outline → theme → slides → compile-QA) on the openagents SDK and proves the architecture end-to-end. The design spec at `docs/superpowers/specs/2026-04-18-pptx-agent-design.md` promised a production-grade CLI with Rich `Layout` chrome, field-by-field editing in every interactive stage, a 3-5 candidate theme gallery, schema-validated slide generation with retry-then-fallback, a 4-step compile-QA Live view with placeholder scan and loopback, cross-session memory writeback, and backup/restore for `project.json`. Most of those are stubbed: each wizard step is ~70-90 lines and only offers `accept / regenerate / abort`, the theme step shows one candidate, the slide step has no retry loop, the compile-QA step has no placeholder scan or loopback, and there is no Rich `Layout` at all.

All required SDK primitives already exist (`openagents.cli.wizard.Wizard`, `MarkdownMemory`, `ShellExecTool`, `EnvironmentDoctor`). The work is entirely in `examples/pptx_generator/`.

## Goals / Non-Goals

**Goals:**
- Deliver the interactions originally spec'd without inventing new SDK seams.
- Match the feel of `uv` / `gh` / `poetry`: one-screen state, keyboard-first, resumable.
- Keep every new behavior testable; extend the integration test to walk the full happy path plus each branch that the new specs introduce.
- Keep the example's role as a reference implementation: readable, minimally abstracted, and usable as a copy-start point.

**Non-Goals:**
- Changing any SDK kernel / seam protocol (`RunRequest`, `RunContext`, plugin base classes).
- Adding a new builtin plugin. `MarkdownMemory`, `ShellExecTool`, `remember_preference`, and `EnvironmentDoctor` already do what we need.
- Rewriting the agent prompts in `app/plugins.py` beyond the minimum required to get the retry / repair loop to work (no prompt-tuning for its own sake).
- Localization, telemetry, or plugin-marketplace concerns — these belong to other plans.

## Decisions

### D1. Redraw strategy: pre-run full-screen `Layout`, post-run scrollback

Rich's `Layout` with `Live` locks the bottom of the terminal and is awkward to mix with `questionary` prompts. Chosen approach: the wizard owns a persistent `Live(layout, refresh_per_second=4)` that we **pause** (`Live.stop`) before every `questionary.ask()` call and resume afterwards. Between stages we `console.clear()` then re-enter the `Live`. The log tail is a `RingBuffer[str]` the `Live` reads from; stages append to it via the existing `Wizard.live_log` primitive. Alternative considered — running the whole wizard inline without `Layout` — rejected because it breaks the `uv`-style "one-screen state" the spec calls out.

### D2. Editing model: menu → field picker → typed input

Rather than a single monolithic form, every stage with editable output (intent / outline / theme-custom) uses a two-level menu: (1) top-level action menu (`confirm` / `edit field` / `regenerate` / `abort`), (2) field picker that dispatches to the right control (`select` for enums, `text` with validator for free-form strings, numeric `text` for counts, sub-menus for list fields). This keeps interactions shallow (max 3 key presses per edit) and re-uses `Wizard.select` / `Wizard.text` / `Wizard.multi_select` uniformly. Alternative — a single "big dialog" with all fields at once — rejected because `questionary` has no multi-field form primitive; stitching one ourselves would compete with the established interaction model.

### D3. Outline index invariant

After every outline edit (add / remove / reorder) the code re-indexes `SlideSpec.index` to be contiguous starting at 1 before re-rendering and before any downstream stage touches it. This keeps the integration contract with stage 6 (which fans out by index) simple: indexes are always the display order.

### D4. Theme candidates come from the agent, not hard-coded locally

The `theme-selector` agent prompt is adjusted to return a `{"candidates": [ThemeSelection, ...]}` envelope (3-5 entries). `state.py` gains `ThemeCandidateList` pydantic wrapper; the agent's `parse_output` (in `app/plugins.py`) returns the envelope. The wizard then renders all candidates; the user can also invoke the custom editor, which is initialized from the last picked candidate.

### D5. Slide retry loop sits in the wizard, not the agent

Two options for handling slot-schema failures:
- **(a) wizard validates and re-invokes the agent** — transparent, testable with mock runtime, keeps validation visible to the user.
- **(b) push retry into `response_repair_policy` and let the agent self-heal** — hides complexity from the wizard, but the repair seam is one-shot, not loop-up-to-2, and obscures which slide failed from the UI.

Chose (a). The retry lives in `wizard/slides.py`; on validation failure we build an error-summary prompt (`"your previous response failed schema validation: <error>. Please return strictly conforming SlideIR."`) and call `runtime.run` again. The Rich `Live` table is the UI side of this loop.

### D6. QA placeholder scan uses the existing `shell_exec` + `rg`

`rg` is widely available and already used in dev. If `rg` is missing we fall back to a pure-Python scan (`re.search` per markdown line). `markitdown` remains optional (already handled by `EnvironmentDoctor`); if absent we still attempt the other three sub-steps and report `markitdown skipped`. Alternative — writing a new builtin scanner tool — rejected because it adds a seam entry for a 10-line regex job.

### D7. Memory writeback happens at stage-commit time from the wizard, not inside agent prompts

`remember_preference` tool already lets agents request writes mid-turn, but the "save as preference?" UX must be deterministic and user-driven. The wizard calls `MarkdownMemory.capture` directly from the stage's post-confirm path, wrapping it in try/except so a memory failure never breaks a successful generation. Each stage owns its own category → rule formatting helper in `wizard/<stage>.py`.

### D8. Resume safety: rotate-then-write with explicit restore UX

`persistence.save_project` rotates `project.json` → `project.json.bak` (unlink-and-rename, atomic on POSIX, best-effort on Windows), writes the new content to `project.json.tmp`, then `os.replace` to `project.json`. On load, if `DeckProject.model_validate` fails, `persistence.load_project` raises `ProjectCorruptedError`; the CLI's `main` catches it and prompts restore / start-fresh / abort. `KeyboardInterrupt` is trapped in `run_wizard` (not inside stages), so stages don't need per-step cleanup — they just need to leave `project` in a self-consistent state between `await` points.

### D9. Keep per-stage files under ~250 lines, extract helpers

Each stage file is becoming 2-4× larger. Rather than one big file per stage, we factor:
- `wizard/_layout.py` — the shared `LayoutRenderer` + `LogRing`
- `wizard/_editors.py` — reusable intent/outline/theme field editors
- `wizard/_slide_runner.py` — the retry-and-fallback loop for stage 6
- `wizard/_qa_scan.py` — the placeholder scanner for stage 7

The seven stage files become orchestrators that wire these helpers to `runtime.run` calls; this keeps the reading-order intuitive and lets unit tests target the helpers directly.

## Risks / Trade-offs

- **[Risk] Rich `Live` + `questionary` interaction is fragile on Windows terminals** → Mitigation: the wizard already pauses `Live` around prompts (D1); the integration test runs on Linux+Windows CI and an explicit smoke test drives questionary via `questionary.unsafe_prompt` with piped input to catch regressions.
- **[Risk] The `theme-selector` agent might return fewer than 3 or more than 5 candidates** → Mitigation: validator on `ThemeCandidateList` enforces the bound; out-of-bound responses go through `response_repair_policy` for a single repair pass, then fall back to asking the user to `regenerate`.
- **[Risk] The slide retry loop doubles worst-case token usage** → Mitigation: retries are capped at 2, fallback is free; the integration test uses a mock provider to assert exactly-N retries, so regressions are caught without real LLM cost.
- **[Risk] `project.json.bak` can itself be corrupt** → Mitigation: validation is performed after restore; if the backup also fails, the UX still has the "start fresh" option.
- **[Risk] Memory writeback happens after the agent's `writeback` hook has already run** → Mitigation: the wizard calls `MarkdownMemory.capture` which pushes to its own section file directly (not via `_pending_memory_writes`), so there's no re-entry into the runtime lifecycle.
- **[Trade-off] More interaction surface = more test scaffolding** → We extend the integration test and add focused unit tests for each new helper (`_slide_runner`, `_qa_scan`, `_editors`). The additions keep coverage ≥ the repo's 90 % floor; the existing `coverage.omit` list is unchanged.
- **[Trade-off] Larger example codebase** → Offsets: helpers under `wizard/_*.py` are small (< 150 lines each), cohesive, and directly reusable as templates by users building their own wizards — matching the example's role as a reference.

## Migration Plan

The example has no external users of its internal APIs beyond its own tests, so no deprecation shims are required.

1. Land new helpers (`_layout`, `_editors`, `_slide_runner`, `_qa_scan`) plus their unit tests first. Zero behaviour change.
2. Wire each stage to its new helper — one stage per commit, integration test updated in the same commit. This bisects cleanly if a regression is introduced.
3. Add the `memory forget` CLI subcommand and `project.json.bak` rotation in a small final commit.
4. Docs (`README.md` + `docs/pptx-agent-cli.md` + `docs/pptx-agent-cli.en.md` + `docs/examples.md` link) in the final commit of the series.

Rollback: revert the PR; old behaviour (`accept / regenerate / abort`) is preserved in git. No data migration is needed — `project.json` schema does not change.

## Open Questions

- **Should the theme gallery support a "save these 3 candidates for future reuse" memory write?** Likely yes but adds a spec scenario; defer to the implementer's judgement after getting user feedback on the base gallery UX.
- **How aggressive should `rg` placeholder patterns be?** Current list (`xxxx`, `lorem`, `placeholder`, `this page`) comes from the design spec; extending it (e.g. `todo`, `tbd`) is a small follow-up once we have real telemetry on false positives.
