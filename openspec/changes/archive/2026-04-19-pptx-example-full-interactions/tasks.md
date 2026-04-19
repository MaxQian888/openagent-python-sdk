## 1. Shared helpers (zero behaviour change)

- [x] 1.1 Create `examples/pptx_generator/wizard/_layout.py` with `LayoutRenderer` (Rich `Layout`: status bar, sidebar tree, main, log tail) and `LogRing(max_lines=5)`; expose a single `render(project)` entry point that can be called between stages.
- [x] 1.2 Add `tests/unit/test_pptx_wizard_layout.py` — snapshot-test sidebar glyphs (`✓ / ▶ / ○`) for every possible `project.stage`, exercise `LogRing` truncation, and verify the status bar shows `stage n/7`.
- [x] 1.3 Create `examples/pptx_generator/wizard/_editors.py` with reusable editors: `edit_intent(report) -> IntentReport`, `edit_outline(outline) -> SlideOutline`, `edit_theme_custom(base) -> ThemeSelection`. Each implements the two-level menu from design D2 and re-renders the whole object after each edit.
- [x] 1.4 Add `tests/unit/test_pptx_wizard_editors.py` — mock `questionary.select/text/confirm`, drive every branch (edit each field, add/remove/reorder for list fields, validator rejection of `#rrggbb`).
- [x] 1.5 Create `examples/pptx_generator/wizard/_slide_runner.py` with `generate_slide(runtime, spec, theme, *, max_retries=2) -> (SlideIR, status)`; implements the validate → retry ≤2 → fallback-freeform loop from spec `pptx-pipeline-resilience`. Also expose `SlideStatus` enum + `LiveStatusTable` adapter for Rich `Live`.
- [x] 1.6 Add `tests/unit/test_pptx_slide_runner.py` — mock runtime returns valid, then invalid+valid, then 3 invalid in sequence; assert 0 / 1 / 2 retries and correct status in each case.
- [x] 1.7 Create `examples/pptx_generator/wizard/_qa_scan.py` with `scan_placeholders(md_text, patterns) -> list[(slide_index, pattern, line)]`; try `rg` via `shell_exec` first, fall back to `re.finditer` over the markdown. Handle `markitdown` absence gracefully (returns empty list + flag).
- [x] 1.8 Add `tests/unit/test_pptx_qa_scan.py` — fixture markdown with/without placeholders, rg-present and rg-missing branches; assert slide-index attribution works.

## 2. Rewire stages to use helpers

- [x] 2.1 `wizard/intent.py` — replace confirm-or-retry with `_editors.edit_intent` loop; post-confirm offer "save as preference" → `MarkdownMemory.capture("user_goals", ...)`.
- [x] 2.2 `wizard/outline.py` — replace `accept/regenerate/abort` menu with `_editors.edit_outline` loop; guard regenerate-all with "discard edits?" confirmation.
- [x] 2.3 `wizard/theme.py` — adjust `_extract` to handle `{"candidates": [...]}` envelope, render gallery via Rich `Columns`, wire `_editors.edit_theme_custom` for the custom path; post-pick offer "save as preference" → `MarkdownMemory.capture("decisions", ...)`.
- [x] 2.4 `wizard/slides.py` — drive `_slide_runner.generate_slide` per slide, render `LiveStatusTable`, surface post-run summary with per-failed-index re-run menu; post-run offer "save as preference" → `MarkdownMemory.capture("decisions", ...)` for any manual tweaks.
- [ ] 2.5 `wizard/compile_qa.py` — rewrite as 4 Rich `Live` sub-steps (write JS → `npm install` with `node_modules` skip → `node compile.js` → `markitdown + _qa_scan`); on issue present the loopback menu (`go back to stage <X>` / `hand-edit slide <N>` / `accept and finish`); implement `go back to stage 6` by rewinding `project.stage` to `slides` and returning `StepResult(status="retry")` up to the `Wizard` loop. **Deferred — user reverted the in-flight rewrite; preserving existing simpler `compile_qa.py`.**
- [x] 2.6 `wizard/research.py` — post-confirm offer "save as preference" → `MarkdownMemory.capture("references", ...)`.
- [x] 2.7 Update `tests/integration/test_pptx_generator_example.py` to drive the new menus (choice-aware `Wizard.select`, `ThemeCandidateList` parsing, slot-valid SlideIR) so the end-to-end wizard still reaches `stage=done`. Per-field intent edits / Ctrl+C-resume / QA loopback branches are out of scope because stage 7 was rolled back.

## 3. Layout + CLI chrome

- [ ] 3.1 Update `examples/pptx_generator/cli.py::run_wizard` to own a persistent `Live(LayoutRenderer(project))` that is stopped around each `WizardStep.render` call, per design D1. **Deferred — `LayoutRenderer` is landed and unit-tested (task 1.1–1.2), but persistent-Live/questionary interplay is risky on Windows and is out of scope for this change. Follow-up ticket can adopt it once the stage-7 rewrite lands.**
- [x] 3.2 Install `KeyboardInterrupt` handler in `run_wizard` that flushes `project.json` via `save_project` and prints the resume hint.
- [x] 3.3 Add `memory forget <entry_id>` subcommand to `build_parser` and dispatch in `main`; implement `MarkdownMemory.forget` if not already exposed (already present on the builtin).
- [x] 3.4 Add `tests/unit/test_pptx_cli.py` coverage for: `memory forget` happy path + missing-id, `KeyboardInterrupt` flush behaviour (via monkeypatched wizard raising `KeyboardInterrupt`), and `ProjectCorruptedError` restore menu.

## 4. Persistence safety

- [x] 4.1 Update `examples/pptx_generator/persistence.py::save_project` to rotate existing `project.json` → `project.json.bak` atomically, then write `project.json.tmp` → `os.replace` to `project.json`. (Rotation + atomic replace already existed; added restore helper.)
- [x] 4.2 Update `load_project` to raise a dedicated `ProjectCorruptedError` on pydantic validation failure.
- [x] 4.3 Update `main` in `cli.py` to catch `ProjectCorruptedError` at startup and present the 3-choice restore menu (restore from `.bak` / start fresh / abort) from `pptx-wizard-ui` spec.
- [x] 4.4 Add `tests/unit/test_pptx_persistence.py` — rotation preserves previous content, replace is atomic (simulate crash between steps via monkeypatch), validation failure raises `ProjectCorruptedError`, restore-from-backup replaces file.

## 5. Agent wiring for theme candidates

- [x] 5.1 Add `ThemeCandidateList` pydantic model to `state.py` with `candidates: list[ThemeSelection]` and `3 <= len <= 5` validator.
- [x] 5.2 Update `examples/pptx_generator/app/plugins.py` so the `theme-selector` agent's `parse_output` returns `ThemeCandidateList`, keeping `ThemeSelection` as the single-pick type propagated to downstream stages.
- [x] 5.3 Adjust the `theme-selector` system prompt (lives in `plugins.py::_THEME_SYSTEM`, not `agent.json`) so the model returns a 3-5 candidates envelope.
- [ ] 5.4 Update `tests/integration/test_pptx_generator_example.py` mock provider fixture to return a valid `ThemeCandidateList`; add an assertion that fewer-than-3 triggers the repair path then user-facing regenerate prompt.

## 6. Documentation

- [x] 6.1 Replace `examples/pptx_generator/README.md` stub with a full user-facing guide (install / run `new` / run `resume` / `memory list|forget` / stage-by-stage walkthrough). Screenshots of the Rich `Layout` deferred with task 3.1.
- [x] 6.2 Update `docs/pptx-agent-cli.md` (+ `docs/pptx-agent-cli.en.md`) with the field-by-field editing, theme gallery, slide retry/fallback, and backup-restore flows.
- [x] 6.3 Update `docs/examples.md` (+ `docs/examples.en.md`) with the new interaction summary and `memory list / forget` commands.
- [x] 6.4 Confirmed `docs/seams-and-extension-points.md` does not need changes — no new SDK seam introduced; all additions are inside the example.

## 7. Verification

- [x] 7.1 Run `uv run pytest -q` — **933 passed, 4 skipped** (up from 820 passed / 24 failed on main before this change).
- [x] 7.2 Run `uv run coverage run -m pytest && uv run coverage report` — coverage is **91 %** after this change (same as before it; pre-existing `fail_under=92` shortfall is in the `openagents/` runtime, outside this change's scope — `source = ["openagents"]` excludes `examples/`).
- [ ] 7.3 Run `uv run pptx-agent new --topic "coverage demo"` end-to-end against a mock LLM env. **Manual — requires a running LLM endpoint (or the demo fixture) and terminal session. The integration test exercises the equivalent path with mocked LLM/shell.**
- [ ] 7.4 Run `uv run pptx-agent memory list` and `uv run pptx-agent memory forget <id>` — unit tests cover both paths (`tests/unit/test_pptx_cli.py::test_memory_list_subcommand`, `::test_memory_forget_happy_path`, `::test_memory_forget_missing_id`). **Manual smoke on a real terminal still recommended.**
- [ ] 7.5 Open the generated `.pptx` in a PPT reader — **Manual; requires human visual review. Leaving for the developer validating this change.**
