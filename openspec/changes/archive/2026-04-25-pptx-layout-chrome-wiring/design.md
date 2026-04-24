## Context

`LayoutRenderer`, `LogRing`, and `RingLogHandler` were fully implemented and unit-tested as part of `2026-04-19-pptx-example-shell-events-init`. Every `WizardStep` has `layout: Any = None` and `log_ring: Any = None` fields and calls `repaint(console, self.layout, project)` at the start of `render()`. The `repaint()` function is a no-op when `renderer is None`, so all 7 stages currently produce no sidebar/status-bar output.

The second archive's tasks 1.3, 1.4, 1.6, and 1.7 were marked `[x]` but the corresponding `cli.py` changes were not committed. This change lands them.

## Goals / Non-Goals

**Goals:**
- Instantiate `LayoutRenderer(project=project)` + `LogRing(max_lines=5)` in `run_wizard()`
- Attach `RingLogHandler` to `logging.getLogger("examples.pptx_generator")` so agent activity feeds the log tail
- Pass `layout=renderer` and `log_ring=log_ring` to every `WizardStep` at construction time
- Emit `console.print(renderer.render(project))` once before `wizard.run()` / `wizard.resume()`
- Repaint in the `KeyboardInterrupt` handler before printing the resume hint
- Detach the log handler in a `finally` block to prevent test leakage
- Add a unit test that verifies the wiring contract

**Non-Goals:**
- `rich.live.Live` — explicitly banned because it corrupts Windows conhost across `questionary.ask_async()` calls; the `repaint()` snapshot approach is the deliberate alternative
- Rewriting `compile_qa.py` to use a live tree (deferred in the first archive, still deferred)
- Adding a background timer thread for elapsed-time ticks
- Any changes outside `examples/pptx_generator/`

## Decisions

### D1 — `repaint()` not `rich.live.Live`

Using `console.print(layout_renderer.render(project))` at stage boundaries instead of a persistent `Live(...)` context.

**Rationale**: `questionary.ask_async()` and `rich.live.Live` cannot safely coexist on Windows conhost (cursor positioning becomes corrupted). The `repaint()` pattern — snapshot render at each logical boundary — delivers the sidebar/status-bar information without holding an open `Live` context. This constraint is documented in `_layout.py`'s `repaint()` docstring.

**Alternative considered**: Background ticker thread calling `live.refresh()`. Rejected: adds complexity, same Windows issue, and no meaningful benefit over boundary-based repaints.

### D2 — Logger name `"examples.pptx_generator"`

Attach `RingLogHandler` to `logging.getLogger("examples.pptx_generator")` (the package root for the example).

**Rationale**: All log calls inside `examples/pptx_generator/` propagate up to this logger. Attaching at the root captures agent activity, pattern errors, and wizard diagnostics without naming individual submodules. The `include_prefixes` in `agent.json`'s logging block already names this prefix.

### D3 — Handler detachment in `finally`

Unconditionally detach `RingLogHandler` in the `finally` block of `run_wizard()`.

**Rationale**: Tests that call `run_wizard()` multiple times in the same process share the same logger object. Without detachment, each call stacks another handler, producing duplicate log lines and making the `test_ring_log_handler_detaches_without_leaking` assertion meaningless at the integration level.

### D4 — Test strategy

Extend the existing `tests/unit/test_pptx_cli.py` (or add `tests/unit/examples/pptx_generator/test_cli.py`) rather than adding to the layout test module.

**Rationale**: The wiring test is a `run_wizard` integration concern, not a `_layout.py` unit concern. It belongs alongside the other `run_wizard` tests. The test replaces `Wizard` with a spy class that captures the step instances passed to it.

## Risks / Trade-offs

- **Rich not installed** → `LayoutRenderer.build()` returns `None`; `repaint()` already guards against `rendered is None`, so a missing Rich silently no-ops. No new risk.
- **Windows conhost** → Using `console.print()` at stage boundaries, never `Live`; same guarantee as before the wiring.
- **Test isolation** → Mitigated by D3 (handler detachment in `finally`); tests that monkeypatch `Wizard` still work because the spy captures step instances before any prompt runs.
