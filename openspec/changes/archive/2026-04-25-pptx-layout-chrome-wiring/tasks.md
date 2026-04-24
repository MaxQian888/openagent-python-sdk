## 1. Wire LayoutRenderer into run_wizard()

- [x] 1.1 In `examples/pptx_generator/cli.py::run_wizard()`, before `Wizard(...)` construction: import `logging` (already imported) and `LayoutRenderer`, `LogRing`, `RingLogHandler` from `wizard._layout`; instantiate `log_ring = LogRing(max_lines=5)` and `renderer = LayoutRenderer(project=project)`; create `_log_handler = RingLogHandler(ring=log_ring)` with a `logging.Formatter("%(name)s %(message)s")` formatter; call `logging.getLogger("examples.pptx_generator").addHandler(_log_handler)`.
- [x] 1.2 After creating the handler, set `step.layout = renderer` and `step.log_ring = log_ring` on every step in the `steps` list (iterate with a loop or set at construction time via keyword args).
- [x] 1.3 Call `console.print(renderer.render(project))` once immediately before `wizard.run()` / `wizard.resume()` to emit the initial sidebar state.
- [x] 1.4 In the `KeyboardInterrupt` handler (before `save_project` call), add `console.print(renderer.render(project))` so the final terminal frame reflects the persisted `project.stage`.
- [x] 1.5 In a `finally` block wrapping the `wizard.run()` / `wizard.resume()` call, call `logging.getLogger("examples.pptx_generator").removeHandler(_log_handler)` to prevent handler accumulation across repeated test invocations.

## 2. Update the spec

- [x] 2.1 Copy `openspec/changes/pptx-layout-chrome-wiring/specs/pptx-wizard-ui/spec.md` into `openspec/specs/pptx-wizard-ui/spec.md`, replacing its full content, so the canonical spec reflects the new wiring requirement.

## 3. Tests

- [x] 3.1 Add a test (in `tests/unit/examples/pptx_generator/test_cli.py` or extend `tests/unit/test_pptx_cli.py`) that calls `run_wizard()` with a spy `Wizard` class capturing the `steps` kwarg; assert every step's `layout` is a `LayoutRenderer` instance and `log_ring` is a `LogRing` instance.
- [x] 3.2 Add a test that verifies the `RingLogHandler` is attached to `logging.getLogger("examples.pptx_generator")` during the wizard run and detached after it returns; use `monkeypatch` to replace `Wizard` with `_StubWizard` (already in `test_events_jsonl_persistence.py`) and inspect `logger.handlers` inside the stub.
- [x] 3.3 Extend `test_keyboard_interrupt_flushes_and_exits` (or add a sibling) to verify that `console.print` is called with a `Layout` renderable in the `KeyboardInterrupt` path; inject a `MagicMock` console and assert the call happened before `save_project`.

## 4. Verification

- [x] 4.1 Run `uv run pytest tests/unit/examples/pptx_generator/ tests/unit/test_pptx_cli.py -q` — all pass, including new tests.
- [x] 4.2 Run `uv run pytest -q` — full suite passes (target: ≥ 1992 + new test count).
- [x] 4.3 Smoke: run `uv run python -m examples.pptx_generator.cli new --topic "test deck"` in a terminal with `LLM_API_KEY` mocked; confirm the sidebar renders at stage 1 and the elapsed timer appears in the status bar.
