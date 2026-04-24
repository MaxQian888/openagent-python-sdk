## Why

`LayoutRenderer`, `LogRing`, and `RingLogHandler` were built and unit-tested as part of the `pptx-example-shell-events-init` change, but the wiring step — passing them into each `WizardStep` inside `run_wizard()` — was never committed. As a result, `repaint()` is a no-op in every stage and the 4-region Rich Layout (status bar / sidebar / main / log tail) never renders at runtime.

## What Changes

- `examples/pptx_generator/cli.py::run_wizard()` gains ~15 lines that instantiate `LayoutRenderer` + `LogRing`, attach a `RingLogHandler` to the `examples.pptx_generator` logger, pass `layout` and `log_ring` to every `WizardStep`, emit the initial sidebar render before `wizard.run()` / `wizard.resume()`, repaint inside the `KeyboardInterrupt` handler before printing the resume hint, and detach the handler in `finally`.
- A new unit test in `tests/unit/examples/pptx_generator/test_cli.py` (or the existing `test_pptx_cli.py`) verifies that: `layout` and `log_ring` are non-None on every step, the logger handler is attached before the wizard runs and detached afterward, and the `KeyboardInterrupt` path calls the renderer before printing the hint.

## Capabilities

### New Capabilities

*(none — this change wires existing infrastructure, introduces no new spec-level capabilities)*

### Modified Capabilities

- `pptx-wizard-ui`: The "Rich Layout shell around every stage" requirement is currently unmet at runtime. This change closes the gap: `run_wizard()` will create and propagate the `LayoutRenderer` so every `repaint()` call produces visible output per the spec's "SHALL render every stage inside a four-region Rich Layout" invariant.

## Impact

- **`examples/pptx_generator/cli.py`** — `run_wizard()` function only; no public API changes.
- **`tests/unit/`** — one new or extended test module; no changes to existing test logic.
- **No dependency additions** — `rich` and `logging` are already in scope; no new packages.
- **No breaking changes** — steps remain dataclasses with optional `layout`/`log_ring` fields; callers that pass `None` (e.g. existing tests) continue to work.
