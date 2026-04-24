"""Optional image-export helper for ``openagents run --save-image``.

Supported formats
-----------------
- ``.svg``  — built-in via ``rich``; no extra dependencies.
- ``.png`` / ``.jpg`` / ``.jpeg`` / ``.webp`` — requires ``cairosvg``
  (install with ``pip install io-openagent-sdk[screenshot]``).

Usage
-----
::

    from openagents.cli._screenshot import save_run_image
    save_run_image(result, runtime, Path("out.svg"))
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

_SVG_FORMATS = {".svg"}
_RASTER_FORMATS = {".png", ".jpg", ".jpeg", ".webp"}
_DEFAULT_WIDTH = 120
_DEFAULT_INCLUDE = {
    "tool.called",
    "tool.succeeded",
    "llm.succeeded",
    "session.run.started",
    "session.run.completed",
}


def _require_rich() -> None:
    try:
        import rich  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "rich is required for image export. Install with: pip install io-openagent-sdk[rich]"
        ) from exc


def _svg_to_raster_playwright(svg_text: str, suffix: str) -> bytes:
    """Convert SVG → raster via playwright (cross-platform, no system libs)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ImportError(
            "playwright is required for PNG/JPG/WEBP export. "
            "Install with: uv pip install playwright && playwright install chromium"
        ) from exc

    html = f"<html><body style='margin:0;padding:0;background:#1e1e2e'>{svg_text}</body></html>"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        page.set_content(html)
        page.wait_for_load_state("networkidle")
        data = page.screenshot(full_page=True, type="png")
        browser.close()

    if suffix in {".jpg", ".jpeg"}:
        try:
            import io as _io

            from PIL import Image

            img = Image.open(_io.BytesIO(data)).convert("RGB")
            buf = _io.BytesIO()
            img.save(buf, format="JPEG", quality=95)
            return buf.getvalue()
        except ImportError:
            pass  # return PNG bytes with .jpg extension
    if suffix == ".webp":
        try:
            import io as _io

            from PIL import Image

            img = Image.open(_io.BytesIO(data))
            buf = _io.BytesIO()
            img.save(buf, format="WEBP", quality=95)
            return buf.getvalue()
        except ImportError:
            pass

    return data


def _svg_to_raster_cairosvg(svg_text: str, suffix: str) -> bytes:
    """Fallback: Cairo-based converter (Linux/Mac, needs libcairo system lib)."""
    try:
        import cairosvg  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError("cairosvg not available") from exc

    svg_bytes = svg_text.encode("utf-8")
    png_bytes: bytes = cairosvg.svg2png(bytestring=svg_bytes)

    if suffix in {".jpg", ".jpeg", ".webp"}:
        try:
            import io as _io

            from PIL import Image

            img = Image.open(_io.BytesIO(png_bytes)).convert("RGB")
            buf = _io.BytesIO()
            fmt = "JPEG" if suffix in {".jpg", ".jpeg"} else "WEBP"
            img.save(buf, format=fmt, quality=95)
            return buf.getvalue()
        except ImportError:
            pass

    return png_bytes


def _recording_console(width: int = _DEFAULT_WIDTH) -> Any:
    from rich.console import Console

    return Console(record=True, width=width, force_terminal=True, highlight=False)


def _event_matches(name: str, include: set[str]) -> bool:
    return any(fnmatch.fnmatchcase(name, pat) for pat in include)


def _render_history(console: Any, runtime: Any, include: set[str]) -> None:
    """Re-render matching events from the event bus history onto *console*."""
    from openagents.observability._rich import render_event_row

    bus = getattr(runtime, "event_bus", None)
    history = getattr(bus, "history", []) if bus is not None else []
    for event in history:
        name = getattr(event, "name", "")
        if not _event_matches(name, include):
            continue
        try:
            rendered = render_event_row(event, show_payload=True)
            console.print(rendered)
        except Exception:
            pass


def _render_finished(console: Any, result: Any) -> None:
    """Render the run.finished and output panels onto *console*."""
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    from openagents.observability._rich import _render_value

    stop = result.stop_reason.value if hasattr(result.stop_reason, "value") else str(result.stop_reason)
    err = result.error_details
    stop_style = "bold green" if stop == "completed" else "bold red"

    header = Table.grid(padding=(0, 2))
    header.add_row(Text("stop_reason", style="dim"), Text(stop, style=stop_style))
    if err is not None:
        header.add_row(Text("error", style="dim"), Text(str(err.message), style="red"))
    console.print(Panel(header, title="[bold]run.finished[/]", border_style="dim"))

    if result.final_output is not None:
        raw = str(result.final_output)
        try:
            import json as _json

            parsed = _json.loads(raw)
            output_renderable: Any = _render_value(parsed)
        except Exception:
            output_renderable = Markdown(raw)
        console.print(Panel(output_renderable, title="[bold]output[/]", border_style="green"))


def save_run_image(
    result: Any,
    runtime: Any,
    path: Path,
    *,
    width: int = _DEFAULT_WIDTH,
    include: set[str] | None = None,
) -> None:
    """Render events + run.finished to *path* (.svg / .png / .jpg / .webp).

    Parameters
    ----------
    result:
        The ``RunResult`` returned by ``Runtime.run_detailed``.
    runtime:
        The ``Runtime`` instance (used to read ``event_bus.history``).
    path:
        Destination file path. Format is inferred from the suffix.
    width:
        Console width in characters used for the recording.
    include:
        Set of event name globs to include. Defaults to the standard
        set used by ``rich_console`` configs in the example configs.
    """
    _require_rich()
    suffix = path.suffix.lower()
    if suffix not in _SVG_FORMATS and suffix not in _RASTER_FORMATS:
        raise ValueError(f"Unsupported image format {suffix!r}. Supported: {sorted(_SVG_FORMATS | _RASTER_FORMATS)}")

    inc = include if include is not None else _DEFAULT_INCLUDE
    console = _recording_console(width=width)
    _render_history(console, runtime, inc)
    _render_finished(console, result)

    svg_text = console.export_svg(title=f"openagents run — {result.run_id}")

    if suffix in _SVG_FORMATS:
        path.write_text(svg_text, encoding="utf-8")
        return

    # Raster: try playwright first (cross-platform), fall back to cairosvg
    last_exc: Exception | None = None
    for converter in (_svg_to_raster_playwright, _svg_to_raster_cairosvg):
        try:
            raster_bytes = converter(svg_text, suffix)
            path.write_bytes(raster_bytes)
            return
        except ImportError as exc:
            last_exc = exc
            continue

    raise ImportError(
        f"No raster backend available for {suffix!r}. "
        "Install playwright: uv pip install playwright && playwright install chromium"
    ) from last_exc
