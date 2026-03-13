"""System operation tools."""

from __future__ import annotations

import asyncio
import os
import subprocess
from typing import Any

from openagents.interfaces.capabilities import TOOL_INVOKE
from openagents.interfaces.tool import ToolPlugin


class ExecuteCommandTool(ToolPlugin):
    """Execute shell command."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})
        self._timeout = config.get("timeout", 30) if config else 30

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        command = params.get("command", "")
        timeout = params.get("timeout", self._timeout)

        if not command:
            raise ValueError("'command' parameter is required")

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            return {
                "command": command,
                "stdout": stdout.decode("utf-8"),
                "stderr": stderr.decode("utf-8"),
                "returncode": proc.returncode,
                "success": proc.returncode == 0,
            }
        except asyncio.TimeoutError:
            raise TimeoutError(f"Command timed out after {timeout}s")
        except Exception as e:
            raise RuntimeError(f"Failed to execute command: {e}")


class GetEnvTool(ToolPlugin):
    """Get environment variable."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        key = params.get("key", "")
        default = params.get("default")

        if not key:
            raise ValueError("'key' parameter is required")

        value = os.getenv(key, default)
        return {"key": key, "value": value, "exists": key in os.environ}


class SetEnvTool(ToolPlugin):
    """Set environment variable (process-level only)."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        key = params.get("key", "")
        value = params.get("value", "")

        if not key:
            raise ValueError("'key' parameter is required")

        os.environ[key] = str(value)
        return {"key": key, "value": value, "set": True}
