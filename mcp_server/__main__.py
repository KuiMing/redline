"""Entry point: `uv run python -m mcp_server` (stdio, the default) or
`uv run python -m mcp_server --transport streamable-http` (HTTP transport).

See docs/mcp_server.md for environment variables and client configuration.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import os

from mcp.server.transport_security import TransportSecuritySettings

from mcp_server.config import StreamableHttpConfig
from mcp_server.server_app import build_server


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m mcp_server", description="REDLINE MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=os.environ.get("REDLINE_MCP_TRANSPORT", "stdio"),
        help="Transport to serve on. Default: stdio (or $REDLINE_MCP_TRANSPORT).",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Bind host for --transport streamable-http. Default: $REDLINE_MCP_HTTP_HOST or 127.0.0.1.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Bind port for --transport streamable-http. Default: $REDLINE_MCP_HTTP_PORT or 8080.",
    )
    parser.add_argument(
        "--path",
        default=None,
        help="HTTP path for the MCP endpoint. Default: $REDLINE_MCP_HTTP_PATH or /mcp.",
    )
    return parser.parse_args(argv)


def _run_streamable_http(app, args: argparse.Namespace) -> None:
    http_config = StreamableHttpConfig.from_env()
    overrides = {}
    if args.host is not None:
        overrides["host"] = args.host
    if args.port is not None:
        overrides["port"] = args.port
    if args.path is not None:
        overrides["path"] = args.path
    if overrides:
        http_config = dataclasses.replace(http_config, **overrides)

    # Always build an explicit TransportSecuritySettings: the mcp SDK only
    # auto-enables DNS-rebinding protection when the bind host is literally
    # "127.0.0.1"/"localhost"/"::1" (see
    # mcp.server.lowlevel.server.Server.streamable_http_app). A container
    # binds "0.0.0.0" so that auto-detection never fires and, left
    # unspecified, protection defaults OFF — so this must be explicit.
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=http_config.enable_dns_rebinding_protection,
        allowed_hosts=http_config.allowed_hosts,
        allowed_origins=http_config.allowed_origins,
    )
    app.run(
        "streamable-http",
        host=http_config.host,
        port=http_config.port,
        streamable_http_path=http_config.path,
        transport_security=security,
    )


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    app, ctx = build_server()
    try:
        if args.transport == "streamable-http":
            _run_streamable_http(app, args)
        else:
            app.run("stdio")
    finally:
        asyncio.run(ctx.client.aclose())


if __name__ == "__main__":
    main()
