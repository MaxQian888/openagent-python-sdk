"""Filesystem-oriented execution policy helper."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from openagents.interfaces.tool import PolicyDecision, ToolExecutionRequest


_READ_TOOL_IDS = {"read_file", "list_files", "grep_files", "ripgrep"}
_WRITE_TOOL_IDS = {"write_file", "delete_file"}
_PATH_KEYS = ("path", "file_path", "directory", "dir_path", "cwd", "root")


def _normalize_roots(values: list[str] | None) -> list[Path]:
    roots: list[Path] = []
    for value in values or []:
        if not isinstance(value, str) or not value.strip():
            continue
        roots.append(Path(value).resolve(strict=False))
    return roots


def _extract_paths(params: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for key in _PATH_KEYS:
        raw = params.get(key)
        if isinstance(raw, str) and raw.strip():
            paths.append(Path(raw).resolve(strict=False))
    return paths


def _is_within(path: Path, roots: list[Path]) -> bool:
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


class FilesystemExecutionPolicy:
    """Builtin policy helper for filesystem-oriented workloads.

    What:
        Allows/denies the standard read_/write_/list_/grep_/ripgrep
        tools based on configured ``read_roots`` / ``write_roots``
        and tool-name allow/deny lists. Resolves and rejects path
        traversal that would escape the declared roots.

    Usage:
        Embed in a custom ToolExecutorPlugin.evaluate_policy() override, or
        use FilesystemAwareExecutor (builtin) which wraps this helper.

    Depends on:
        - request.params (for path keys: ``path``, ``file_path``,
          ``directory``, ``dir_path``, ``cwd``, ``root``)
    """

    class Config(BaseModel):
        read_roots: list[str] = Field(default_factory=list)
        write_roots: list[str] = Field(default_factory=list)
        allow_tools: list[str] = Field(default_factory=list)
        deny_tools: list[str] = Field(default_factory=list)

    def __init__(self, config: dict[str, Any] | None = None):
        cfg = self.Config.model_validate(config or {})
        self._read_roots = _normalize_roots(cfg.read_roots)
        self._write_roots = _normalize_roots(cfg.write_roots)
        self._allow_tools = set(cfg.allow_tools)
        self._deny_tools = set(cfg.deny_tools)

    async def evaluate_policy(self, request: ToolExecutionRequest) -> PolicyDecision:
        if request.tool_id in self._deny_tools:
            return PolicyDecision(allowed=False, reason=f"Tool '{request.tool_id}' is denied")

        if self._allow_tools and request.tool_id not in self._allow_tools:
            return PolicyDecision(
                allowed=False,
                reason=f"Tool '{request.tool_id}' is not in allow_tools",
            )

        paths = _extract_paths(request.params or {})
        if not paths:
            return PolicyDecision(allowed=True, metadata={"policy": "filesystem"})

        reads_files = bool(getattr(request.execution_spec, "reads_files", False))
        writes_files = bool(getattr(request.execution_spec, "writes_files", False))
        if not reads_files and not writes_files:
            if request.tool_id in _WRITE_TOOL_IDS:
                writes_files = True
            elif request.tool_id in _READ_TOOL_IDS:
                reads_files = True
            else:
                reads_files = True

        if writes_files and self._write_roots:
            for path in paths:
                if not _is_within(path, self._write_roots):
                    return PolicyDecision(
                        allowed=False,
                        reason=f"Write path '{path}' is outside write_roots",
                    )

        if reads_files and self._read_roots:
            for path in paths:
                if not _is_within(path, self._read_roots):
                    return PolicyDecision(
                        allowed=False,
                        reason=f"Read path '{path}' is outside read_roots",
                    )

        return PolicyDecision(allowed=True, metadata={"policy": "filesystem"})
