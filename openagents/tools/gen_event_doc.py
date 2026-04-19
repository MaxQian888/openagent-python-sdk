"""Generate ``docs/event-taxonomy.md`` from ``EVENT_SCHEMAS``.

Usage::

    uv run python -m openagents.tools.gen_event_doc

Writes ``docs/event-taxonomy.md`` relative to the repository root.
The matching drift-guard test
(``tests/unit/test_event_taxonomy_doc_synced.py``) ensures the file's
event-name set matches the registry exactly.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from openagents.interfaces.event_taxonomy import EVENT_SCHEMAS, EventSchema

_HEADER = """# Event Taxonomy

Events emitted by the SDK and built-in plugins. Schema is **advisory**: the
async event bus logs a warning when a declared event is emitted with
missing required payload keys, but never raises. Custom events not
present here are emitted unchanged with no validation.

The source of truth is
[`openagents/interfaces/event_taxonomy.py`](../openagents/interfaces/event_taxonomy.py).
Regenerate this file via::

    uv run python -m openagents.tools.gen_event_doc

| Event | Required payload | Optional payload | Description |
|---|---|---|---|
"""


def _format_payload(keys: tuple[str, ...]) -> str:
    if not keys:
        return "—"
    return ", ".join(f"`{k}`" for k in keys)


def _format_row(schema: EventSchema) -> str:
    return (
        f"| `{schema.name}` "
        f"| {_format_payload(schema.required_payload)} "
        f"| {_format_payload(schema.optional_payload)} "
        f"| {schema.description} |\n"
    )


_FOOTER = """
## OpenTelemetry mapping

The optional `events.otel_bridge` builtin maps SDK events onto OpenTelemetry
spans without altering the inner event bus contract. The mapping is one-to-one
and stateless:

| SDK | OpenTelemetry |
|---|---|
| event_name | span name `openagents.<event_name>` (e.g. `openagents.tool.succeeded`) |
| `payload[key]` = `value` | span attribute `oa.<key>` with the string-coerced or JSON-serialized value |
| value longer than `max_attribute_chars` (default 4096) | truncated to that length plus the literal suffix
`...[truncated]` |
| `include_events` filter (fnmatch) | only matching events produce spans; non-matches still go through the inner bus |

Spans are one-shot: nothing happens inside the `with` block beyond setting
attributes, so `start_time` and `end_time` are nearly equal. Pairing
`session.run.started`/`session.run.completed` into a single parent span is
out of scope for the current bridge.

Configure a `TracerProvider` in the host process via `opentelemetry-sdk`
plus an exporter of your choice; without one the OTel API no-ops and the
bridge becomes essentially free.
"""


def render_doc() -> str:
    """Render the markdown body for ``docs/event-taxonomy.md``."""
    body = _HEADER
    for name in sorted(EVENT_SCHEMAS):
        body += _format_row(EVENT_SCHEMAS[name])
    body += _FOOTER
    return body


def write_doc(target: Path) -> None:
    """Write the generated markdown to ``target`` (creating parents)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_doc(), encoding="utf-8")


def _default_target() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "docs" / "event-taxonomy.md"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=_default_target(),
        help="Output markdown path (default: <repo>/docs/event-taxonomy.md).",
    )
    args = parser.parse_args(argv)
    write_doc(args.out)
    print(f"wrote {args.out} ({len(EVENT_SCHEMAS)} events)")
    return 0


if __name__ == "__main__":  # pragma: no cover - manual CLI
    raise SystemExit(main())
