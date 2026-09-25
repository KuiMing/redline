# syntax=docker/dockerfile:1
#
# Separate image for the REDLINE MCP server — a *client* of the REDLINE game
# server (see the root Dockerfile), never the game server itself. Build from
# the repo root so it can read pyproject.toml/uv.lock (shared dependency
# pins) and rules.md (the rulebook the `redline://rules` resource serves):
#
#   docker build -f mcp_server/Dockerfile -t redline-mcp .
#
# Does not copy server/, static/, or data/ — this image never imports
# server.game or any other server/*.py module, and never touches /test/*
# routes; it only talks to a REDLINE server over HTTP+WebSocket at whatever
# REDLINE_BASE_URL points to (see docker-compose.yml).

FROM python:3.11-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY mcp_server/ ./mcp_server/
COPY rules.md ./rules.md

# Bind 0.0.0.0 inside the container so Docker's port mapping can reach it;
# see mcp_server/__main__.py's _run_streamable_http for why
# TransportSecuritySettings is always built explicitly (the SDK's
# auto-protection only fires for a literal 127.0.0.1/localhost/::1 bind
# host, which 0.0.0.0 is not). REDLINE_MCP_ALLOWED_HOSTS/_ORIGINS keep their
# safe localhost-only defaults unless the operator overrides them — see
# docs/mcp_server.md's Docker section before exposing this beyond
# 127.0.0.1 on the host.
ENV REDLINE_MCP_HTTP_HOST=0.0.0.0
ENV REDLINE_MCP_HTTP_PORT=8080

EXPOSE 8080

CMD ["uv", "run", "--no-dev", "python", "-m", "mcp_server", "--transport", "streamable-http"]
