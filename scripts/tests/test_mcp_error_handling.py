"""Error-shaping contract: a rejected game/lobby action must come back as a
normal `{"ok": False, ...}` tool result (so the model keeps full context and
can just try something else), while a transport failure must raise
`ToolError` (so the model treats it differently — reconnect/retry, not "try
another move"). See mcp_server/tools/errors.py for the rationale.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from mcp_server.redline_client import RedlineConnectionError, RedlineError
from mcp_server.tools import gameplay, lobby
from mcp_server.tools.errors import call_guarded, game_error_result


class _FakeClient:
    def __init__(self, *, raise_connection_error=False, raise_game_error=False):
        self.raise_connection_error = raise_connection_error
        self.raise_game_error = raise_game_error

    async def create_room(self, name):
        if self.raise_game_error:
            raise RedlineError("Name required", code="create_room_failed")
        if self.raise_connection_error:
            raise RedlineConnectionError("Cannot reach REDLINE server at http://example")
        return {"game_id": "g1", "host_id": "p1", "resume_token": "tok"}

    async def get_state(self, game_id, player_id, resume_token=None):
        raise RedlineConnectionError("No response to 'get_state' within 8.0s")


class _FakeRules:
    async def factions(self):
        return {"categories": []}


class _Ctx:
    def __init__(self, client):
        self.client = client
        self.rules = _FakeRules()


def test_game_error_result_shape():
    exc = RedlineError("Room full", code="join_room_failed")
    result = game_error_result(exc)
    assert result == {"ok": False, "error": "Room full", "error_code": "join_room_failed"}


@pytest.mark.anyio
async def test_redline_error_becomes_ok_false_result_not_tool_error():
    ctx = _Ctx(_FakeClient(raise_game_error=True))
    result = await lobby.create_room(ctx, "")
    assert result == {"ok": False, "error": "Name required", "error_code": "create_room_failed"}


@pytest.mark.anyio
async def test_connection_error_raises_tool_error_with_message_preserved():
    ctx = _Ctx(_FakeClient(raise_connection_error=True))
    with pytest.raises(ToolError, match="Cannot reach REDLINE server"):
        await lobby.create_room(ctx, "Alice")


@pytest.mark.anyio
async def test_action_timeout_raises_tool_error_via_get_state():
    ctx = _Ctx(_FakeClient())
    with pytest.raises(ToolError, match="No response to 'get_state'"):
        await gameplay.get_state(ctx, "g1", "p1")


@pytest.mark.anyio
async def test_call_guarded_passes_through_successful_result():
    async def ok():
        return {"success": True}

    assert await call_guarded(ok()) == {"success": True}


@pytest.mark.anyio
async def test_resolve_pending_choice_requires_exactly_one_of_index_or_indices():
    ctx = _Ctx(_FakeClient())
    both = await gameplay.resolve_pending_choice(ctx, "g1", "p1", index=0, indices=[0, 1])
    neither = await gameplay.resolve_pending_choice(ctx, "g1", "p1")
    assert both == {"ok": False, "error": "Provide exactly one of index or indices"}
    assert neither == {"ok": False, "error": "Provide exactly one of index or indices"}
