"""DeckProject persistence.

Single-slot backup: each save overwrites the immediately previous
``project.json.bak``. Earlier history is not retained.

Crash safety: save writes to ``project.json.tmp`` then atomically replaces
the target via ``os.replace``. On failure between write and replace, the
``.tmp`` file remains on disk and is overwritten by the next successful
save — no cleanup loop is needed because paths are deterministic.

Missing-file behavior: ``load_project`` lets ``FileNotFoundError`` propagate
unchanged. Corrupt JSON or schema validation failures raise
:class:`ProjectCorruptedError` so the CLI can offer restore/start-fresh UX.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from pydantic import ValidationError

from .state import DeckProject


class ProjectCorruptedError(Exception):
    """Raised when ``project.json`` cannot be parsed or does not validate."""

    def __init__(self, path: Path, detail: str):
        super().__init__(f"project.json at {path} is corrupt: {detail}")
        self.path = path
        self.detail = detail


def project_path(slug: str, *, root: Path) -> Path:
    return Path(root) / slug / "project.json"


def backup_path(slug: str, *, root: Path) -> Path:
    return Path(root) / slug / "project.json.bak"


def load_project(slug: str, *, root: Path) -> DeckProject:
    path = project_path(slug, root=root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProjectCorruptedError(path, f"invalid JSON: {exc}") from exc
    try:
        return DeckProject.model_validate(data)
    except ValidationError as exc:
        raise ProjectCorruptedError(path, f"schema validation failed: {exc}") from exc


def restore_from_backup(slug: str, *, root: Path) -> DeckProject:
    """Replace ``project.json`` with ``project.json.bak`` and load the result."""
    bak = backup_path(slug, root=root)
    if not bak.exists():
        raise FileNotFoundError(f"no backup at {bak}")
    target = project_path(slug, root=root)
    shutil.copy2(bak, target)
    return load_project(slug, root=root)


def save_project(project: DeckProject, *, root: Path) -> Path:
    path = project_path(project.slug, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, backup_path(project.slug, root=root))
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return path
