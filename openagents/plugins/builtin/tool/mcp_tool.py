"""MCP (Model Context Protocol) tool plugin."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from openagents.interfaces.capabilities import TOOL_INVOKE
from openagents.interfaces.tool import ToolPlugin

logger = logging.getLogger(__name__)


@dataclass
class McpServerConfig:
    """MCP server connection configuration."""

    # For stdio connections (local servers)
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None

    # For SSE/HTTP connections (remote servers)
    url: str | None = None
    headers: dict[str, str] | None = None


class McpConnection:
    """Manages connection to an MCP server."""

    def __init__(self, config: McpServerConfig):
        self.config = config
        self._session: Any = None
        self._reader: Any = None
        self._writer: Any = None

    async def connect(self) -> None:
        """Establish connection to MCP server."""
        if self.config.url:
            await self._connect_http()
        else:
            await self._connect_stdio()

    async def _connect_stdio(self) -> None:
        """Connect via stdio (local subprocess)."""
        try:
            from mcp import ClientSession
            from mcp.client.stdio import stdio_client
        except ImportError as e:
            raise RuntimeError(
                "MCP SDK not installed. Install with: pip install mcp"
            ) from e

        server_params: Any = None
        if self.config.command:
            # Import StdioServerParameters
            from mcp import StdioServerParameters

            server_params = StdioServerParameters(
                command=self.config.command,
                args=self.config.args or [],
                env=self.config.env,
            )

        if server_params:
            transport = stdio_client(server_params)
            self._reader, self._writer = await transport.__aenter__()
            self._session = ClientSession(self._reader, self._writer)
            await self._session.__aenter__()

    async def _connect_http(self) -> None:
        """Connect via SSE/HTTP (remote server)."""
        try:
            from mcp import ClientSession
            from mcp.client.sse import SseClientTransport
        except ImportError as e:
            raise RuntimeError(
                "MCP SDK not installed. Install with: pip install mcp"
            ) from e

        transport = SseClientTransport(
            url=self.config.url,
            headers=self.config.headers or {},
        )
        self._reader, self._writer = await transport.__aenter__()
        self._session = ClientSession(self._reader, self._writer)
        await self._session.__aenter__()

    async def list_tools(self) -> list[dict[str, Any]]:
        """List available tools on the server."""
        if not self._session:
            raise RuntimeError("Not connected to MCP server")

        response = await self._session.list_tools()
        tools = []
        for tool in response.tools:
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema,
            })
        return tools

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call a tool on the server."""
        if not self._session:
            raise RuntimeError("Not connected to MCP server")

        result = await self._session.call_tool(tool_name, arguments)

        # Parse result into readable format
        output = []
        for item in result.content:
            if hasattr(item, "text"):
                output.append(item.text)
            elif hasattr(item, "type"):
                output.append(f"[{item.type}]")
            else:
                output.append(str(item))

        return {"content": output, "isError": result.isError}

    async def close(self) -> None:
        """Close the connection."""
        if self._session:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                logger.warning("Error closing MCP session", exc_info=True)
        if self._writer:
            try:
                await self._writer.aclose()
            except Exception:
                logger.warning("Error closing MCP writer", exc_info=True)


class McpTool(ToolPlugin):
    """Tool that forwards calls to an MCP server.

    Configuration:
        - server: Server connection config
            - command: Executable command (e.g., "python", "node")
            - args: Command arguments (e.g., ["server.py"])
            - env: Environment variables (optional)
            - url: Remote server URL (optional, for HTTP/SSE)
            - headers: HTTP headers (optional, for HTTP/SSE)
        - tools: List of tool names to expose (optional, exposes all if empty)

    Usage in agent config:
        {
            "tools": [
                {
                    "id": "mcp_filesystem",
                    "type": "mcp",
                    "config": {
                        "server": {
                            "command": "python",
                            "args": ["/path/to/mcp_server.py"]
                        },
                        "tools": ["read_file", "write_file"]
                    }
                }
            ]
        }

    Calling the tool:
        Call with params: {"tool": "tool_name", "arguments": {...}}
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})

        server_config = self.config.get("server", {})
        self._server_config = McpServerConfig(
            command=server_config.get("command"),
            args=server_config.get("args"),
            env=server_config.get("env"),
            url=server_config.get("url"),
            headers=server_config.get("headers"),
        )

        # List of tools to expose (empty = all)
        self._exposed_tools = set(self.config.get("tools", []))

        self._connection: McpConnection | None = None
        self._available_tools: list[dict[str, Any]] | None = None

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        """Forward tool call to MCP server."""
        tool_name = params.get("tool")
        if not tool_name:
            raise ValueError("'tool' parameter is required")

        arguments = params.get("arguments", {})

        # Ensure connection
        if self._connection is None:
            self._connection = McpConnection(self._server_config)
            await self._connection.connect()

            # Fetch available tools
            self._available_tools = await self._connection.list_tools()

        # Check if tool is allowed
        if self._exposed_tools and tool_name not in self._exposed_tools:
            raise ValueError(f"Tool '{tool_name}' is not exposed by this MCP server")

        # Forward call
        result = await self._connection.call_tool(tool_name, arguments)
        return result

    async def close(self) -> None:
        """Close MCP connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    def get_available_tools(self) -> list[dict[str, Any]] | None:
        """Get list of available tools (after connection)."""
        return self._available_tools
