"""Runtime configuration for the REDLINE MCP server, read entirely from env vars.

The MCP server is a *client* of an already-running REDLINE HTTP+WebSocket
server (server/main.py) — it never imports server.game or constructs a Game
object itself, so nothing here talks to a database or holds game state.
"""

import os
from dataclasses import dataclass


def _float_env(name, default):
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class RedlineMCPConfig:
    base_url: str
    ws_base_url: str | None
    http_timeout_seconds: float
    ws_connect_timeout_seconds: float
    action_wait_timeout_seconds: float

    @classmethod
    def from_env(cls) -> "RedlineMCPConfig":
        base_url = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        ws_base_url = os.environ.get("REDLINE_WS_BASE_URL")
        return cls(
            base_url=base_url,
            ws_base_url=ws_base_url.rstrip("/") if ws_base_url else None,
            http_timeout_seconds=_float_env("REDLINE_MCP_HTTP_TIMEOUT", 10.0),
            ws_connect_timeout_seconds=_float_env("REDLINE_MCP_WS_CONNECT_TIMEOUT", 10.0),
            action_wait_timeout_seconds=_float_env("REDLINE_MCP_ACTION_TIMEOUT", 8.0),
        )
