"""RedlineClient connection-lifecycle correctness, tested against a fake
WebSocket (no real network) so these stay fast and deterministic. The live
subprocess-backed reconnect path is covered by
scripts/tests/test_mcp_e2e_smoke.py's `disconnect_session` case.
"""

import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from mcp_server.redline_client import PlayerSession, RedlineClient, RedlineConnectionError


class _FakeWS:
    """A fake socket whose `send` succeeds but never produces a reply, so the
    session's revision never advances — used to simulate "the connection
    died between send and response" without touching real sockets."""

    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(message)


def _install_session(client: RedlineClient, game_id: str, player_id: str) -> PlayerSession:
    session = PlayerSession(game_id=game_id, player_id=player_id, resume_token="tok")
    session.ws = _FakeWS()
    session.closed = False
    session.latest_state = {"turn": 1, "game_phase": "main"}
    client._sessions[(game_id, player_id)] = session
    return session


@pytest.mark.anyio
async def test_send_action_raises_when_connection_closes_mid_wait_instead_of_returning_stale_state():
    client = RedlineClient(base_url="http://127.0.0.1:1")  # never dialed; session is pre-installed
    session = _install_session(client, "g1", "p1")

    async def _drop_connection_shortly_after_send():
        await asyncio.sleep(0.05)
        session.closed = True
        session.updated_event.set()
        session.updated_event.clear()

    dropper = asyncio.create_task(_drop_connection_shortly_after_send())
    try:
        with pytest.raises(RedlineConnectionError, match="Connection closed while waiting"):
            await client.send_action("g1", "p1", "advance", {})
    finally:
        await dropper


@pytest.mark.anyio
async def test_send_action_returns_fresh_state_when_reader_delivers_it():
    client = RedlineClient(base_url="http://127.0.0.1:1")
    session = _install_session(client, "g1", "p1")

    async def _deliver_fresh_state_shortly_after_send():
        await asyncio.sleep(0.05)
        session.latest_state = {"turn": 2, "game_phase": "main"}
        session.revision += 1
        session.updated_event.set()
        session.updated_event.clear()

    deliverer = asyncio.create_task(_deliver_fresh_state_shortly_after_send())
    try:
        state, error = await client.send_action("g1", "p1", "advance", {})
    finally:
        await deliverer
    assert error is None
    assert state["turn"] == 2


@pytest.mark.anyio
async def test_send_action_times_out_with_actionable_message_when_nothing_arrives():
    client = RedlineClient(base_url="http://127.0.0.1:1", action_wait_timeout=0.1)
    _install_session(client, "g1", "p1")
    with pytest.raises(RedlineConnectionError, match="No response to 'advance'"):
        await client.send_action("g1", "p1", "advance", {})


@pytest.mark.anyio
async def test_ensure_connected_serializes_concurrent_first_connects_for_same_session():
    # An MCP host can dispatch several tool calls from one model turn
    # concurrently; two calls hitting the same not-yet-connected
    # (game_id, player_id) must not both open a WebSocket for it (that would
    # orphan one connection + reader task — see ensure_connected's lock).
    client = RedlineClient(base_url="http://127.0.0.1:1")
    open_calls: list[PlayerSession] = []

    async def _fake_open_ws(session: PlayerSession) -> None:
        open_calls.append(session)
        await asyncio.sleep(0.05)
        session.ws = _FakeWS()
        session.closed = False
        session.latest_state = {"turn": 1, "game_phase": "main"}

    client._open_ws = _fake_open_ws  # type: ignore[method-assign]

    first, second = await asyncio.gather(
        client.ensure_connected("g1", "p1"),
        client.ensure_connected("g1", "p1"),
    )
    assert first is second
    assert len(open_calls) == 1
