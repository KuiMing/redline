from __future__ import annotations

import json
from contextlib import AsyncExitStack
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client


class MCPGatewayError(RuntimeError):
    pass


class MCPGateway:
    """A long-lived MCP client session used only for deterministic control flow."""

    def __init__(self, url: str):
        self.url = url
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> "MCPGateway":
        self._stack = AsyncExitStack()
        try:
            streams = await self._stack.enter_async_context(streamable_http_client(self.url))
            read, write = streams[:2]
            self._session = await self._stack.enter_async_context(ClientSession(read, write))
            await self._session.initialize()
            tools = await self._session.list_tools()
            names = {tool.name for tool in tools.tools}
            required = {"create_room", "resume_room", "get_room_status", "choose_faction", "set_ready", "start_game", "get_state", "get_legal_actions"}
            missing = required - names
            if missing:
                raise MCPGatewayError(f"REDLINE MCP is missing required tools: {', '.join(sorted(missing))}")
            return self
        except BaseException:
            try:
                await self._stack.aclose()
            except BaseException:
                pass
            self._stack = None
            self._session = None
            raise

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None

    async def call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._session is None:
            raise MCPGatewayError("MCP session is not connected")
        result = await self._session.call_tool(name, arguments or {})
        if not result.content:
            raise MCPGatewayError(f"MCP tool {name} returned no content")
        text = getattr(result.content[0], "text", None)
        if text is None:
            raise MCPGatewayError(f"MCP tool {name} returned non-text content")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MCPGatewayError(f"MCP tool {name} returned invalid JSON") from exc
        if result.is_error:
            message = payload.get("error") if isinstance(payload, dict) else None
            raise MCPGatewayError(str(message or f"MCP tool {name} failed"))
        if not isinstance(payload, dict):
            raise MCPGatewayError(f"MCP tool {name} returned a non-object payload")
        return payload
