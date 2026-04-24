## MODIFIED Requirements

### Requirement: Rich Layout shell around every stage

The `pptx-agent` wizard SHALL render every stage inside a four-region Rich `Layout`: a top status bar (slug · stage n/7 · elapsed time), a left sidebar showing all 7 steps annotated with ✓ (done) / ▶ (active) / ○ (pending), a main region that hosts the current stage panel, and a bottom log tail capped at the last 5 log lines. Between stages the console SHALL be cleared and the `Layout` SHALL be redrawn from current `DeckProject` state so the sidebar, status bar, and log tail stay consistent with `project.stage`. The wizard SHALL NOT hold an open `rich.Live` context across any interactive prompt issued via `openagents.cli.wizard.Wizard.select/confirm/text/password` — the shell MUST coexist with `questionary.ask_async()` on Windows without terminal corruption. Stages MAY call `console.print(layout_renderer.render(project))` at any logical sub-step boundary to give the user time-updated feedback without a background ticker thread.

`run_wizard()` in `examples/pptx_generator/cli.py` SHALL instantiate a `LayoutRenderer(project=project)` and a `LogRing(max_lines=5)`, attach a `RingLogHandler` to `logging.getLogger("examples.pptx_generator")`, and set both as `layout` and `log_ring` attributes on every `WizardStep` before calling `wizard.run()` or `wizard.resume()`. The handler SHALL be detached in a `finally` block to prevent leakage across test invocations.

#### Scenario: Layout redraws on stage transition

- **WHEN** a stage completes and advances `project.stage` to the next stage
- **THEN** the console is cleared, the sidebar marks the prior step ✓ and the new step ▶, the status bar updates to `stage n/7`, and the main region shows the new stage's panel

#### Scenario: Layout and questionary coexist on Windows

- **WHEN** a stage uses `Wizard.select` or `Wizard.text` to prompt the user on a Windows conhost
- **THEN** the `questionary` prompt SHALL render without corrupted cursor positioning or interleaved Rich redraws, because no `rich.Live` context is active across the prompt call

#### Scenario: Every step receives a non-None LayoutRenderer

- **WHEN** `run_wizard()` constructs the seven `WizardStep` instances
- **THEN** each step's `layout` attribute SHALL be a `LayoutRenderer` instance and `log_ring` SHALL be a `LogRing` instance, so that `repaint()` produces visible output

#### Scenario: Log tail captures agent activity

- **WHEN** the `examples.pptx_generator` logger emits a record during any stage
- **THEN** the record SHALL be pushed into the `LogRing` via `RingLogHandler` and appear in the bottom region on the next `repaint()` call

#### Scenario: `KeyboardInterrupt` repaints the Layout before exit

- **WHEN** the user presses Ctrl+C at a stage boundary or during a prompt
- **THEN** `run_wizard` SHALL catch the signal, repaint the Layout once to reflect the final persisted stage (current stage marked ▶, not ✓), print the resume hint, and exit with code 130

#### Scenario: Logger handler is detached after run_wizard completes

- **WHEN** `run_wizard()` returns (whether completed, interrupted, or errored)
- **THEN** the `RingLogHandler` SHALL have been removed from `logging.getLogger("examples.pptx_generator")` so subsequent invocations do not stack duplicate handlers
