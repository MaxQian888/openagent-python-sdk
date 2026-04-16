from __future__ import annotations

import shutil
import sys
from uuid import uuid4
from pathlib import Path

import pytest


SKILL_SRC = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "openagent-agent-builder"
    / "src"
)

if str(SKILL_SRC) not in sys.path:
    sys.path.insert(0, str(SKILL_SRC))


_TMP_ROOT = Path(__file__).resolve().parents[1] / ".tmp" / "pytest-local"


@pytest.fixture
def tmp_path() -> Path:
    _TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = _TMP_ROOT / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
