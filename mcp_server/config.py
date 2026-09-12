"""Runtime configuration for the REDLINE MCP server, read entirely from env vars.

The MCP server is a *client* of an already-running REDLINE HTTP+WebSocket
server (server/main.py) — it never imports server.game or constructs a Game
object itself, so nothing here talks to a database or holds game state.
"""

import os
from dataclasses import dataclass, field


def _float_env(name, default):
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int_env(name, default):
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _bool_env(name, default):
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _csv_env(name, default):
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# Same values the `mcp` SDK itself auto-applies when a streamable-http server
# binds literally to "127.0.0.1"/"localhost"/"::1" (see
# mcp.server.lowlevel.server.Server.streamable_http_app). We bind "0.0.0.0"
# inside a container so that auto-detection never fires — these are the
# explicit defaults that keep the same safe behavior regardless of bind host.
DEFAULT_ALLOWED_HOSTS = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
DEFAULT_ALLOWED_ORIGINS = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]


@dataclass(frozen=True)
class StreamableHttpConfig:
    """Bind address + DNS-rebinding-protection settings for `--transport
    streamable-http`. Kept separate from RedlineMCPConfig (which configures
    the *client* side talking to the REDLINE game server) since this is
    entirely about how *this* process's own HTTP endpoint is exposed.
    """

    host: str
    port: int
    path: str
    enable_dns_rebinding_protection: bool
    allowed_hosts: list[str] = field(default_factory=lambda: list(DEFAULT_ALLOWED_HOSTS))
    allowed_origins: list[str] = field(default_factory=lambda: list(DEFAULT_ALLOWED_ORIGINS))

    @classmethod
    def from_env(cls) -> "StreamableHttpConfig":
        return cls(
            host=os.environ.get("REDLINE_MCP_HTTP_HOST", "127.0.0.1"),
            port=_int_env("REDLINE_MCP_HTTP_PORT", 8080),
            path=os.environ.get("REDLINE_MCP_HTTP_PATH", "/mcp"),
            enable_dns_rebinding_protection=_bool_env(
                "REDLINE_MCP_ENABLE_DNS_REBINDING_PROTECTION", True
            ),
            allowed_hosts=_csv_env("REDLINE_MCP_ALLOWED_HOSTS", DEFAULT_ALLOWED_HOSTS),
            allowed_origins=_csv_env("REDLINE_MCP_ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS),
        )


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
