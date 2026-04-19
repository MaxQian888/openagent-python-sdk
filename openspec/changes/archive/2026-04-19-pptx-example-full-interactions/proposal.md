## Why

The `examples/pptx_generator/` example ships the 7-stage pipeline skeleton but cuts most of the interactive polish promised by the design spec (`docs/superpowers/specs/2026-04-18-pptx-agent-design.md`): intent/outline/theme stages only offer accept-or-regenerate, themes never render a gallery, generated slides have no schema-repair/fallback loop, the compile-QA stage has no placeholder scan or loopback, and there is no Rich `Layout` shell (status bar / sidebar / main / log tail). The example is advertised as the SDK's flagship production-grade CLI demo, so these omissions undersell the SDK and leave users without a convincing reference for building their own wizards. Finish it to the level of `uv` / `gh` / `poetry`, as the original design intended, without adding scope outside that spec.

## What Changes

- **Intent stage** gains per-field editing (`questionary` menu → edit topic / audience / purpose / tone / slide count / language / required sections / visuals / research queries) before confirmation; saving preferences captures per-field reasons.
- **Outline stage** gains add / remove / reorder / edit-single-slide actions on the slide list with inline regenerate-single-slide; keeps regenerate-all and abort.
- **Theme stage** renders 3–5 candidate palettes side-by-side via Rich `Columns` with arrow-key pick, plus a full custom editor (primary / secondary / accent / light / bg + heading / body / CJK fonts + style + badge).
- **Slides stage** adds strict slot-schema validation with ≤2 agent retries per slide, then fallback to `freeform` per the design; Rich `Live` shows per-slide state (queued / running / retry N / ok / fallback / failed); post-run summary lets user manually re-run failed indices.
- **Compile-QA stage** rewrites into the 4 Rich `Live` sub-steps (write JS → `npm install` → `node compile.js` → `markitdown` → placeholder scan via `rg`); any detected issue prompts "go back to stage X / hand-edit slide N / accept and finish".
- **Global wizard shell** adopts Rich `Layout` (status bar with slug/stage/elapsed time, left sidebar tree of 7 steps with ✓/▶/○, main panel, bottom log tail capped at 5 lines). `console.clear()` between stages.
- **Resume safety** — write `project.json.bak` before every atomic overwrite; if `project.json` fails pydantic validation on load, prompt restore-from-backup / start-fresh. Trap `KeyboardInterrupt` at the wizard level, flush `project.json`, print resume hint.
- **Memory writeback** — stages 1 / 3 / 5 / 6 expose "save this as a preference next time" checkboxes; each goes through `MarkdownMemory.capture` with a stage-specific category so the agents see it on future runs. Add `pptx-agent memory forget <id>` CLI subcommand (the `memory list` path already exists).
- **Docs** — update `examples/pptx_generator/README.md` and `docs/pptx-agent-cli.md` to describe the new interactions + screenshots of the layout.

No changes to SDK kernel / seams / builtin plugins — the gap is entirely in the example.

## Capabilities

### New Capabilities

- `pptx-wizard-ui`: Rich `Layout` shell (status bar / sidebar tree / main panel / log tail) and shared UX primitives (confirmation flow, keyboard-interrupt handling, backup/restore prompts) that every stage of the PPT example uses.
- `pptx-stage-editing`: per-stage interactive editing for intent (field-by-field), outline (add/remove/reorder/edit-per-slide), and theme (3–5 candidate gallery + full custom editor).
- `pptx-pipeline-resilience`: slide-generator strict-schema / ≤2-retry / fallback-freeform loop, compile-QA 4-step Live run with `rg` placeholder scan and stage loopback, and cross-session memory writeback (preference capture on stages 1 / 3 / 5 / 6 + `memory forget` subcommand).

### Modified Capabilities

None. The PPT example has no prior OpenSpec capability entries (the design lives in `docs/superpowers/specs/`), so every change here registers as a new capability rather than a modification.

## Impact

- **Code**
  - `examples/pptx_generator/wizard/*.py` — all 7 step modules rewritten against the new UI/behavior contracts (each grows roughly 2–4×).
  - `examples/pptx_generator/cli.py` — wizard bootstrap wraps the new `Layout`; adds `memory forget` subcommand; installs `KeyboardInterrupt` handler.
  - `examples/pptx_generator/persistence.py` — introduces `project.json.bak` rotation + restore flow.
  - `examples/pptx_generator/state.py` — minor additions (e.g. per-stage `preferences_captured` flags to drive the UI).
  - `examples/pptx_generator/app/plugins.py` — tighten the `slide-generator` response-repair + schema validation wiring so the retry / fallback semantics route through the existing `response_repair_policy` seam (no new seam).
  - `examples/pptx_generator/templates/*.js` — no changes.
- **Tests**
  - `tests/integration/test_pptx_generator_example.py` — end-to-end scenario extended to cover per-field edits, outline add/remove/reorder, theme pick-from-gallery, slide retry-then-fallback, QA-loopback, and resume-from-backup.
  - New unit coverage for the new helpers in `examples/pptx_generator/wizard/` (layout renderer, slide-status live model, QA scanner).
  - `tests/conftest.py` already adds the skill onto `sys.path`; no change needed.
- **Dependencies** — none added. Already using `rich`, `questionary`, `python-dotenv`, `httpx`.
- **Docs**
  - `examples/pptx_generator/README.md` — replace the 2-line stub with a user-facing guide.
  - `docs/pptx-agent-cli.md` (+ `.en.md`) — new or updated.
  - `docs/examples.md` — link to updated guide.
  - No change to `docs/seams-and-extension-points.md` (no new seam).
- **Runtime / kernel** — zero. No change to `openagents/` source.
- **Coverage floor** — coverage scope for the example is only exercised by the integration test; the new unit tests keep the overall floor above the 90 % threshold without needing `coverage.omit` entries.
