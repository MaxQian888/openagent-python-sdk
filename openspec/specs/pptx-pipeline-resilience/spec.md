# pptx-pipeline-resilience

## Purpose

Resilience and cross-session memory contracts for the generation, compile, and QA tail of the PPT example. Owned by `examples/pptx_generator/wizard/slides.py`, `wizard/compile_qa.py`, `app/slot_schemas.py`, `app/plugins.py` (response-repair wiring), and the `memory forget` subcommand in `examples/pptx_generator/cli.py`.

This capability defines how the slide-generator stage validates every `SlideIR` against its per-type pydantic slot schema and routes failures through a bounded retry-then-fallback pipeline; how the compile-QA stage renders its 4 ordered sub-steps (`write JS → npm install → node compile.js → markitdown+rg scan`) as a Rich `Live` tree with loopback-to-earlier-stage choices when issues are detected; and how stages 1/3/5/6 optionally write user preferences back to `MarkdownMemory` (with a `memory forget` CLI path to reverse the capture). The invariants: **no slide SHALL ever leave the generator stage un-typed** (validated `SlideIR` or fallback `freeform`), and **no QA issue SHALL be silently accepted** (user must choose go-back / hand-edit / accept-and-finish).

## Requirements

### Requirement: Slide generation validates slots and retries with fallback

For each slide in the outline the `slide-generator` agent SHALL return a `SlideIR`. The wizard SHALL validate `slots` against the per-type pydantic schema declared in `examples/pptx_generator/app/slot_schemas.py`. If validation fails the wizard SHALL re-invoke the agent with an error-repair prompt, up to 2 retries total. If the 2nd retry still fails the wizard SHALL construct a `SlideIR` with `type="freeform"` whose `freeform_js` is produced from the original `SlideSpec` via a template. Each slide's lifecycle (queued / running / retry N / ok / fallback / failed) SHALL render in a Rich `Live` table that updates as states change.

#### Scenario: First attempt succeeds

- **WHEN** the agent's initial response validates against the slot schema
- **THEN** the slide SHALL be marked `ok`, no retry SHALL be issued, and the `SlideIR` SHALL be appended to `project.slides`

#### Scenario: Second attempt succeeds

- **WHEN** the first response fails validation and the first retry succeeds
- **THEN** the Live table SHALL show `retry 1` then `ok`, exactly one retry SHALL have been issued, and the validated `SlideIR` SHALL be kept

#### Scenario: Both retries fail — fallback to freeform

- **WHEN** the initial response and both retries all fail slot validation
- **THEN** the wizard SHALL mark the slide `fallback`, emit a `SlideIR` with `type="freeform"` and a `freeform_js` value derived from the `SlideSpec`, and include it in `project.slides`

#### Scenario: Post-run summary offers manual re-run of failed indices

- **WHEN** at least one slide ended in `fallback` or `failed`
- **THEN** the wizard SHALL show a summary (`N ok / M fallback / K failed`) and offer to re-run any chosen subset of indices, re-entering the same validate-then-fallback loop

### Requirement: Compile-QA runs 4 Rich Live sub-steps and loops back on issues

The compile-QA stage SHALL render a Rich `Live` tree with four ordered sub-steps — `write JS files` → `npm install` (skipped if `node_modules` already present) → `node compile.js` → `markitdown → rg placeholder scan` — each with a pending / running / ok / failed state. The placeholder scan SHALL use the `shell_exec` tool to invoke `rg -i "xxxx|lorem|placeholder|this page"` against the generated markdown and SHALL record every match with its slide index. When any issue is detected (non-zero exit on compile, markitdown missing, or placeholder matches) the wizard SHALL present the choices: `go back to stage <X>`, `hand-edit slide <N>`, `accept and finish`.

#### Scenario: Happy path completes all 4 sub-steps

- **WHEN** every sub-step returns success and the placeholder scan finds zero matches
- **THEN** the Live tree SHALL show 4 green ticks, `project.stage` SHALL become `done`, and the user SHALL see the final `.pptx` path

#### Scenario: Placeholder match triggers loopback prompt

- **WHEN** `rg` finds `lorem` on slide 3
- **THEN** the wizard SHALL surface the match inline, and the choices `go back to stage 6 (regenerate slide 3)` / `hand-edit slide 3` / `accept and finish` SHALL appear, with the default being `go back`

#### Scenario: npm install is skipped if node_modules exists

- **WHEN** `outputs/<slug>/slides/node_modules/pptxgenjs/` already exists
- **THEN** the `npm install` sub-step SHALL be marked `skipped` and the stage SHALL proceed to `node compile.js`

#### Scenario: Go-back-to-stage loopback rewinds project.stage

- **WHEN** the user chooses `go back to stage 6` after a QA failure
- **THEN** `project.stage` SHALL be rewound to `slides`, `project.json` SHALL be re-persisted, and the wizard SHALL re-render the slide-generator stage so the user can regenerate the offending slides

### Requirement: Memory writeback captures preferences from stages 1, 3, 5, 6

Stages `intent`, `research`, `theme`, and `slides` SHALL each offer an optional "save this as a preference for next time" checkbox after the stage commits. When checked, the wizard SHALL call `MarkdownMemory.capture` with a stage-appropriate `category` (`user_goals` for intent, `references` for research, `decisions` for theme and slides), a stage-derived `rule`, and a `reason` string that records which user action produced the memory.

#### Scenario: Intent stage writes to user_goals

- **WHEN** the user confirms the intent report and checks "save as preference"
- **THEN** `MarkdownMemory.capture` SHALL be called with `category="user_goals"` and a `rule` summarising tone / slide count / language

#### Scenario: Theme stage writes to decisions

- **WHEN** the user picks a theme candidate and checks "save as preference"
- **THEN** `MarkdownMemory.capture` SHALL be called with `category="decisions"` and a `rule` capturing palette primary + fonts

#### Scenario: Unchecked box skips writeback

- **WHEN** the user leaves the preference checkbox unchecked
- **THEN** no call to `MarkdownMemory.capture` SHALL be made for that stage

### Requirement: CLI exposes `memory forget` subcommand

`pptx-agent memory forget <entry_id>` SHALL remove the specified entry from the backing `MarkdownMemory` file and update `MEMORY.md`'s index if the section's entry count drops to zero. The subcommand SHALL exit non-zero and print a diagnostic if the entry id is not found.

#### Scenario: Forgetting an existing entry

- **WHEN** the user runs `pptx-agent memory forget abc123` for an entry that exists
- **THEN** the entry SHALL be removed from its section file, the CLI SHALL print `forgot abc123`, and exit code SHALL be 0

#### Scenario: Forgetting a missing entry

- **WHEN** the user runs `pptx-agent memory forget missing-id` and no such entry exists
- **THEN** the CLI SHALL print `entry not found: missing-id` to stderr and exit code SHALL be 1
