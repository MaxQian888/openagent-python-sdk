from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib requires Python 3.11+")
def test_openagent_cli_does_not_require_readline():
    pyproject_path = Path(__file__).resolve().parents[2] / "openagent_cli" / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    dependencies = data["project"]["dependencies"]
    readline_deps = [dep for dep in dependencies if dep.startswith("readline")]

    assert readline_deps == []


@pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib requires Python 3.11+")
def test_openagent_cli_uses_local_openagents_sdk_source():
    pyproject_path = Path(__file__).resolve().parents[2] / "openagent_cli" / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    sources = data.get("tool", {}).get("uv", {}).get("sources", {})
    sdk_source = sources.get("openagents-sdk")

    assert sdk_source == {"path": "..", "editable": True}


@pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib requires Python 3.11+")
def test_openagent_cli_declares_explicit_package_layout():
    pyproject_path = Path(__file__).resolve().parents[2] / "openagent_cli" / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    setuptools_cfg = data.get("tool", {}).get("setuptools", {})
    packages = setuptools_cfg.get("packages")
    package_dir = setuptools_cfg.get("package-dir")

    assert packages == [
        "openagent_cli",
        "openagent_cli.cli",
        "openagent_cli.config",
        "openagent_cli.plugins",
        "openagent_cli.plugins.executors",
        "openagent_cli.plugins.patterns",
        "openagent_cli.plugins.tools",
    ]
    assert package_dir == {
        "openagent_cli": ".",
        "openagent_cli.cli": "cli",
        "openagent_cli.config": "config",
        "openagent_cli.plugins": "plugins",
        "openagent_cli.plugins.executors": "plugins/executors",
        "openagent_cli.plugins.patterns": "plugins/patterns",
        "openagent_cli.plugins.tools": "plugins/tools",
    }


@pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib requires Python 3.11+")
def test_root_sdk_package_discovery_excludes_openagent_cli():
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    find_cfg = data.get("tool", {}).get("setuptools", {}).get("packages", {}).get("find", {})

    assert find_cfg.get("include") == ["openagents*"]
