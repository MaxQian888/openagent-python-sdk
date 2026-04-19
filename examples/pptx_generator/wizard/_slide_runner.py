"""Slide generation retry/fallback loop used by wizard/slides.py."""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ValidationError

from ..app.slot_schemas import SLOT_MODELS
from ..state import SlideIR, SlideSpec


class SlideStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_1 = "retry-1"
    RETRY_2 = "retry-2"
    OK = "ok"
    FALLBACK = "fallback"
    FAILED = "failed"


@dataclass
class SlideRunRecord:
    spec: SlideSpec
    status: SlideStatus = SlideStatus.QUEUED
    attempts: int = 0
    ir: SlideIR | None = None
    error: str | None = None


def _extract_ir(result: Any) -> SlideIR | None:
    if isinstance(result, SlideIR):
        return result
    parsed = getattr(result, "parsed", None)
    if isinstance(parsed, SlideIR):
        return parsed
    state = getattr(result, "state", None) or {}
    raw = state.get("slide")
    if raw is None:
        return None
    try:
        return SlideIR.model_validate(raw)
    except ValidationError:
        return None


def _validate_slots(ir: SlideIR) -> str | None:
    if ir.type == "freeform":
        if ir.freeform_js:
            return None
        return "freeform slide missing freeform_js"
    model = SLOT_MODELS.get(ir.type)
    if model is None:
        return f"unknown slide type {ir.type!r}"
    try:
        model.model_validate(ir.slots)
    except ValidationError as exc:
        return str(exc)
    return None


def _freeform_fallback(spec: SlideSpec, theme: Any) -> SlideIR:
    payload = {
        "title": spec.title,
        "key_points": list(spec.key_points),
    }
    script = (
        "module.exports.createSlide = function(pres, theme) {\n"
        "  const slide = pres.addSlide();\n"
        f"  slide.addText({json.dumps(spec.title)}, {{ x: 0.5, y: 0.5, fontSize: 28, bold: true }});\n"
        f"  const points = {json.dumps(list(spec.key_points))};\n"
        "  slide.addText(points.map(p => ({ text: p })), { x: 0.5, y: 1.5, fontSize: 18, bullet: true });\n"
        "};\n"
    )
    return SlideIR(
        index=spec.index,
        type="freeform",
        slots=payload,
        freeform_js=script,
        generated_at=datetime.now(timezone.utc),
    )


async def generate_slide(
    runtime: Any,
    spec: SlideSpec,
    theme: Any,
    *,
    session_id: str,
    max_retries: int = 2,
    on_status: Any = None,
) -> SlideRunRecord:
    """Drive one slide through up to ``max_retries`` validation cycles.

    Returns the final record including ``ir`` (either validated or freeform
    fallback) and the terminal ``status``.
    """
    record = SlideRunRecord(spec=spec, status=SlideStatus.RUNNING)
    if on_status:
        on_status(record)
    payload_base = {
        "target_spec": spec.model_dump(mode="json"),
        "theme": theme.model_dump(mode="json") if isinstance(theme, BaseModel) else (theme or {}),
    }
    last_error: str | None = None
    for attempt in range(max_retries + 1):
        record.attempts = attempt + 1
        if attempt == 1:
            record.status = SlideStatus.RETRY_1
        elif attempt >= 2:
            record.status = SlideStatus.RETRY_2
        else:
            record.status = SlideStatus.RUNNING
        if on_status:
            on_status(record)

        payload: dict[str, Any] = dict(payload_base)
        if last_error is not None:
            payload["previous_error"] = last_error
        result = await runtime.run(
            agent_id="slide-generator",
            session_id=session_id,
            input_text=json.dumps(payload, ensure_ascii=False),
        )
        ir = _extract_ir(result)
        if ir is None:
            last_error = "response did not include a parsable SlideIR"
            continue
        err = _validate_slots(ir)
        if err is None:
            record.ir = ir
            record.status = SlideStatus.OK
            if on_status:
                on_status(record)
            return record
        last_error = err

    # Exhausted retries → fallback
    record.ir = _freeform_fallback(spec, theme)
    record.status = SlideStatus.FALLBACK
    record.error = last_error
    if on_status:
        on_status(record)
    return record


@dataclass
class LiveStatusTable:
    """Rich-renderable adapter wrapping a list of :class:`SlideRunRecord`."""

    records: list[SlideRunRecord] = field(default_factory=list)

    def update(self, record: SlideRunRecord) -> None:
        for i, existing in enumerate(self.records):
            if existing.spec.index == record.spec.index:
                self.records[i] = record
                return
        self.records.append(record)
        self.records.sort(key=lambda r: r.spec.index)

    def render(self) -> Any:
        try:
            from rich.table import Table
        except ImportError:  # pragma: no cover
            return None
        table = Table(title="Slide generation")
        table.add_column("#", width=4)
        table.add_column("Type")
        table.add_column("Title")
        table.add_column("Status")
        for rec in self.records:
            color = {
                SlideStatus.OK: "green",
                SlideStatus.FAILED: "red",
                SlideStatus.FALLBACK: "yellow",
                SlideStatus.RETRY_1: "yellow",
                SlideStatus.RETRY_2: "yellow",
                SlideStatus.RUNNING: "cyan",
                SlideStatus.QUEUED: "dim",
            }.get(rec.status, "white")
            table.add_row(
                str(rec.spec.index),
                rec.spec.type,
                rec.spec.title,
                f"[{color}]{rec.status.value}[/{color}]",
            )
        return table

    def summary(self) -> dict[str, int]:
        out = {"ok": 0, "fallback": 0, "failed": 0}
        for rec in self.records:
            if rec.status == SlideStatus.OK:
                out["ok"] += 1
            elif rec.status == SlideStatus.FALLBACK:
                out["fallback"] += 1
            elif rec.status == SlideStatus.FAILED:
                out["failed"] += 1
        return out
