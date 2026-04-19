# pptx-wizard-ui

## Purpose

Rich `Layout` shell and shared UX primitives that wrap every stage of the `examples/pptx_generator/` 7-step wizard. Owned by `examples/pptx_generator/wizard/` and `examples/pptx_generator/cli.py`, with atomic persistence in `examples/pptx_generator/persistence.py`.

This capability governs how the PPT example presents each stage on the terminal (status bar / sidebar tree / main region / bottom log tail), how every stage routes its interactive I/O through a single set of primitives, how the wizard traps `KeyboardInterrupt` so the user never loses partial work, and how `project.json` is rotated through a `.bak` sibling so a corrupted write can always be recovered. Its overarching invariant: **no stage SHALL bypass the shared shell or the shared primitives**, and every persisted write SHALL be backup-preceded so resume is always viable.

## Requirements

### Requirement: Rich Layout shell around every stage

The `pptx-agent` wizard SHALL render every stage inside a four-region Rich `Layout`: a top status bar (slug · stage n/7 · elapsed time), a left sidebar showing all 7 steps annotated with ✓ (done) / ▶ (active) / ○ (pending), a main region that hosts the current stage panel, and a bottom log tail capped at the last 5 log lines. Between stages the console SHALL be cleared and the `Layout` SHALL be redrawn from current `DeckProject` state so the sidebar, status bar, and log tail stay consistent with `project.stage`.

#### Scenario: Layout redraws on stage transition

- **WHEN** a stage completes and advances `project.stage` to the next stage
- **THEN** the console is cleared, the sidebar marks the prior step ✓ and the new step ▶, the status bar updates to `stage n/7`, and the main region shows the new stage's panel

#### Scenario: Log tail shows only the latest 5 entries

- **WHEN** more than 5 log lines have been emitted in the current stage
- **THEN** only the most recent 5 SHALL appear in the bottom region and older lines SHALL be scrolled out of view without truncating the retained `project.json` / on-disk logs

#### Scenario: Elapsed time ticks while a stage is running

- **WHEN** a stage is in progress
- **THEN** the status bar SHALL update its elapsed time at least once per second without blocking the stage's async work

### Requirement: Shared wizard primitives for confirmation and input

The wizard SHALL expose a single set of primitives (`confirm`, `select`, `multi_select`, `text`, `password`, `panel`, `progress`, `live_log`) that every stage uses, so the look and feel are uniform across stages. All primitives SHALL respect the Rich `Layout` (no raw `print` leaking outside the main region) and questionary interactions SHALL render inside the main region.

#### Scenario: Every stage uses shared primitives

- **WHEN** the integration test exercises the 7 stages
- **THEN** no stage SHALL bypass the shared primitives with raw `input()` / `print()` calls; all interactive I/O SHALL route through `openagents.cli.wizard.Wizard`

### Requirement: Keyboard interrupt saves and exits cleanly

The wizard SHALL trap `KeyboardInterrupt` (Ctrl+C) at any stage boundary or during interactive prompts, flush the current `DeckProject` to `project.json` (atomic write with backup), print a resume hint of the form `pptx-agent resume <slug>`, and exit with a non-zero status.

#### Scenario: Ctrl+C during a stage

- **WHEN** the user presses Ctrl+C while stage N is running
- **THEN** the wizard SHALL catch the signal, persist `project.json` with `project.stage` set to N, print the resume hint, and return exit code 130

#### Scenario: Ctrl+C during a questionary prompt

- **WHEN** the user presses Ctrl+C while a questionary prompt is awaiting input
- **THEN** the wizard SHALL treat it the same as mid-stage Ctrl+C (persist + resume hint + exit)

### Requirement: Project state backup and restore

Every persisted write of `project.json` SHALL first rotate the existing file to `project.json.bak` (overwriting any prior backup). On resume, if `project.json` fails `DeckProject` pydantic validation, the wizard SHALL show a panel with the validation error and offer three choices: (1) restore from `project.json.bak`, (2) delete both files and start fresh, (3) abort.

#### Scenario: Corrupted project.json is detected on resume

- **WHEN** `pptx-agent resume <slug>` is invoked and `project.json` fails pydantic validation
- **THEN** the wizard SHALL NOT proceed; instead it SHALL render the error panel with the 3 restore choices and only act on the user's selection

#### Scenario: Restore from backup replaces the corrupted file

- **WHEN** the user selects "restore from backup" after corruption is detected
- **THEN** `project.json.bak` SHALL overwrite `project.json` and the wizard SHALL resume from the stage recorded in the restored file
