"""Streamable HTTP transport: CLI/config surface, transport dispatch, the
`/health` route, and a real (in-process, no sockets) MCP protocol round trip
over the actual Starlette app the SDK builds — not a mock of the protocol.

Real-subprocess-over-a-real-socket coverage (including the DNS-rebinding
Host/Origin rejection behavior, which needs genuine HTTP headers a fake ASGI
transport can't meaningfully spoof) lives in
scripts/validate/mcp_streamable_http_smoke.py.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx2
import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.server.transport_security import TransportSecuritySettings

from mcp_server import __main__ as mcp_main
from mcp_server.config import DEFAULT_ALLOWED_HOSTS, DEFAULT_ALLOWED_ORIGINS, StreamableHttpConfig
from mcp_server.server_app import build_server

# ---------------- CLI parsing ----------------


def test_default_transport_is_stdio_with_no_args():
    args = mcp_main._parse_args([])
    assert args.transport == "stdio"
    assert args.host is None and args.port is None and args.path is None


def test_transport_flag_selects_streamable_http():
    args = mcp_main._parse_args(["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "9999", "--path", "/foo"])
    assert args.transport == "streamable-http"
    assert args.host == "0.0.0.0"
    assert args.port == 9999
    assert args.path == "/foo"


def test_rejects_unknown_transport():
    with pytest.raises(SystemExit):
        mcp_main._parse_args(["--transport", "carrier-pigeon"])


def test_transport_env_var_sets_default(monkeypatch):
    monkeypatch.setenv("REDLINE_MCP_TRANSPORT", "streamable-http")
    args = mcp_main._parse_args([])
    assert args.transport == "streamable-http"


# ---------------- StreamableHttpConfig ----------------


def test_streamable_http_config_defaults(monkeypatch):
    for var in (
        "REDLINE_MCP_HTTP_HOST",
        "REDLINE_MCP_HTTP_PORT",
        "REDLINE_MCP_HTTP_PATH",
        "REDLINE_MCP_ALLOWED_HOSTS",
        "REDLINE_MCP_ALLOWED_ORIGINS",
        "REDLINE_MCP_ENABLE_DNS_REBINDING_PROTECTION",
    ):
        monkeypatch.delenv(var, raising=False)
    config = StreamableHttpConfig.from_env()
    assert config.host == "127.0.0.1"
    assert config.port == 8080
    assert config.path == "/mcp"
    assert config.enable_dns_rebinding_protection is True
    assert config.allowed_hosts == DEFAULT_ALLOWED_HOSTS
    assert config.allowed_origins == DEFAULT_ALLOWED_ORIGINS


def test_streamable_http_config_reads_env_overrides(monkeypatch):
    monkeypatch.setenv("REDLINE_MCP_HTTP_HOST", "0.0.0.0")
    monkeypatch.setenv("REDLINE_MCP_HTTP_PORT", "9090")
    monkeypatch.setenv("REDLINE_MCP_HTTP_PATH", "/custom")
    monkeypatch.setenv("REDLINE_MCP_ALLOWED_HOSTS", "example.com:*, other.test:1234")
    monkeypatch.setenv("REDLINE_MCP_ALLOWED_ORIGINS", "https://example.com")
    monkeypatch.setenv("REDLINE_MCP_ENABLE_DNS_REBINDING_PROTECTION", "false")
    config = StreamableHttpConfig.from_env()
    assert config.host == "0.0.0.0"
    assert config.port == 9090
    assert config.path == "/custom"
    assert config.allowed_hosts == ["example.com:*", "other.test:1234"]
    assert config.allowed_origins == ["https://example.com"]
    assert config.enable_dns_rebinding_protection is False


# ---------------- transport dispatch ----------------


class _FakeApp:
    """Captures the kwargs `_run_streamable_http` would hand to a real
    MCPServer.run("streamable-http", ...), without opening a real socket."""

    def __init__(self):
        self.run_calls: list[tuple[str, dict]] = []

    def run(self, transport, **kwargs):
        self.run_calls.append((transport, kwargs))


def test_run_streamable_http_always_builds_explicit_transport_security(monkeypatch):
    # The mcp SDK only auto-enables DNS-rebinding protection when the bind
    # host is literally "127.0.0.1"/"localhost"/"::1" — a container binding
    # "0.0.0.0" must not silently end up with protection OFF.
    for var in ("REDLINE_MCP_ALLOWED_HOSTS", "REDLINE_MCP_ALLOWED_ORIGINS"):
        monkeypatch.delenv(var, raising=False)
    fake_app = _FakeApp()
    args = mcp_main._parse_args(["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8080"])
    mcp_main._run_streamable_http(fake_app, args)

    assert len(fake_app.run_calls) == 1
    transport, kwargs = fake_app.run_calls[0]
    assert transport == "streamable-http"
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 8080
    assert kwargs["streamable_http_path"] == "/mcp"
    security = kwargs["transport_security"]
    assert isinstance(security, TransportSecuritySettings)
    assert security.enable_dns_rebinding_protection is True
    assert security.allowed_hosts == DEFAULT_ALLOWED_HOSTS
    assert security.allowed_origins == DEFAULT_ALLOWED_ORIGINS


def test_cli_args_override_env_config(monkeypatch):
    monkeypatch.setenv("REDLINE_MCP_HTTP_PORT", "1111")
    fake_app = _FakeApp()
    args = mcp_main._parse_args(["--transport", "streamable-http", "--port", "2222"])
    mcp_main._run_streamable_http(fake_app, args)
    assert fake_app.run_calls[0][1]["port"] == 2222


# ---------------- in-process protocol round trip ----------------


@pytest.fixture
async def http_app():
    app, _ctx = build_server()
    # Disabled here on purpose: this fixture talks over an in-process ASGI
    # transport with a synthetic "testserver" Host the real DNS-rebinding
    # check would (correctly) reject. That rejection behavior itself is
    # exercised over a real socket in mcp_streamable_http_smoke.py.
    starlette_app = app.streamable_http_app(
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)
    )
    # The streamable-http session manager's task group only exists while its
    # ASGI lifespan is active (normally driven by uvicorn); drive it
    # manually here since there's no real ASGI server running in this test.
    async with starlette_app.router.lifespan_context(starlette_app):
        yield starlette_app


@pytest.mark.anyio
async def test_health_route_ok(http_app):
    transport = httpx2.ASGITransport(app=http_app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "server": "redline-mcp"}


@pytest.mark.anyio
async def test_streamable_http_initialize_list_tools_call_tool_round_trip(http_app):
    transport = httpx2.ASGITransport(app=http_app)
    http_client = httpx2.AsyncClient(transport=transport, base_url="http://testserver")
    async with streamable_http_client("http://testserver/mcp", http_client=http_client) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            assert init.server_info.name == "redline"

            tools = await session.list_tools()
            assert len(tools.tools) == 32

            resources = await session.list_resources()
            assert any(str(r.uri) == "redline://rules" for r in resources.resources)

            # get_rules_text needs no REDLINE backend (reads rules.md off
            # disk) — deliberately chosen so this test has zero network
            # dependency beyond the in-process ASGI transport itself.
            result = await session.call_tool("get_rules_text", {})
            assert result.is_error is not True
            payload = result.content[0].text
            assert "REDLINE" in payload or "紅軍" in payload
