from __future__ import annotations

import pytest

from openagent_cli.plugins.tools.bash_tool import BashTool
from openagent_cli.plugins.tools.edit_tool import EditTool
from openagent_cli.plugins.tools.glob_tool import GlobTool
from openagent_cli.plugins.tools.read_tool import ReadTool
from openagent_cli.plugins.tools.write_tool import WriteTool


def test_cli_tools_execution_spec_matches_current_sdk_contract():
    bash_spec = BashTool().execution_spec()
    edit_spec = EditTool().execution_spec()
    write_spec = WriteTool().execution_spec()

    assert bash_spec.default_timeout_ms == 60000
    assert bash_spec.side_effects == "process"
    assert edit_spec.writes_files is True
    assert edit_spec.side_effects == "filesystem"
    assert write_spec.writes_files is True
    assert write_spec.side_effects == "filesystem"


@pytest.mark.asyncio
async def test_glob_tool_normalizes_redundant_root_prefix(monkeypatch, tmp_path):
    repo_dir = tmp_path / "openagent-py-sdk"
    target_dir = repo_dir / "openagent_cli"
    target_dir.mkdir(parents=True)
    (target_dir / "README.md").write_text("hello\n", encoding="utf-8")

    monkeypatch.chdir(repo_dir)

    result = await GlobTool().invoke(
        {"pattern": "README*", "root": "openagent-py-sdk/openagent_cli"},
        context=None,
    )

    assert result["count"] == 1
    assert result["files"][0]["relative"] == "README.md"


@pytest.mark.asyncio
async def test_read_tool_normalizes_redundant_path_prefix(monkeypatch, tmp_path):
    repo_dir = tmp_path / "openagent-py-sdk"
    target_dir = repo_dir / "openagent_cli"
    target_dir.mkdir(parents=True)
    readme = target_dir / "README.md"
    readme.write_text("line1\nline2\n", encoding="utf-8")

    monkeypatch.chdir(repo_dir)

    result = await ReadTool().invoke(
        {"path": "openagent-py-sdk/openagent_cli/README.md"},
        context=None,
    )

    assert result["path"].endswith("README.md")
    assert "line1" in result["content"]
