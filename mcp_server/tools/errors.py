"""Shared error-shaping helpers for tool implementations.

Design (see docs/mcp_server.md "Error handling"):
- A rejected game/lobby action (illegal move, wrong turn, room full, ...) is
  NOT an MCP-protocol error. It comes back as a normal, successful tool
  result `{"ok": False, "error": "<server message>", ...}` so the model still
  gets full next-step context (state/legal actions) alongside the reason,
  and can just try a different action.
- A transport failure (server unreachable, WS auth rejected, action timed
  out) raises `ToolError` — there is no useful game state to attach, and the
  correct model response (reconnect/retry) is genuinely different from
  "pick another legal action".
"""

from __future__ import annotations

from mcp.server.mcpserver.exceptions import ToolError

from mcp_server.redline_client import RedlineConnectionError, RedlineError


async def call_guarded(coro):
    """Await `coro`; translate RedlineConnectionError into ToolError.

    RedlineError is deliberately left to propagate — callers catch it
    themselves so they can shape the `{"ok": False, ...}` result with
    whatever extra context (e.g. a state summary) is appropriate there.
    """
    try:
        return await coro
    except RedlineConnectionError as exc:
        raise ToolError(str(exc)) from exc


def game_error_result(exc: RedlineError, **extra) -> dict:
    return {"ok": False, "error": exc.message, "error_code": exc.code, **extra}
