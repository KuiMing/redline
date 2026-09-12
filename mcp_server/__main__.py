"""Entry point: `uv run python -m mcp_server` (stdio transport).

See docs/mcp_server.md for environment variables and client configuration.
"""

from __future__ import annotations

import asyncio

from mcp_server.server_app import build_server


def main() -> None:
    app, ctx = build_server()
    try:
        app.run("stdio")
    finally:
        asyncio.run(ctx.client.aclose())


if __name__ == "__main__":
    main()
