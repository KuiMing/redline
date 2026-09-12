"""Async client for the real REDLINE HTTP + WebSocket boundary.

This module never imports server.game (or any other server/*.py module) and
never calls a /test/* route. Every call here goes through the same endpoints
a browser client uses: server/lobby_routes.py's HTTP routes for lobby setup,
and server/main.py's `/ws/{game_id}/{player_id}` for gameplay. The privacy
scoping the MCP layer relies on (hidden hands, redacted reaction windows,
etc.) is therefore exactly whatever `Game.state(viewer_player_id)` already
enforces server-side — this client cannot see or leak more than that.
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

import websockets


class RedlineError(Exception):
    """A REDLINE game/lobby-level error the caller can act on (not a transport failure).

    `message` is the server's own error string (already the same text a
    browser client would show), so it is safe to hand straight back to an
    LLM tool caller as actionable feedback.
    """

    def __init__(self, message: str, *, code: str = "game_error"):
        super().__init__(message)
        self.code = code
        self.message = message


class RedlineConnectionError(Exception):
    """Transport-level failure talking to the REDLINE server: unreachable,
    timed out, auth rejected, or the socket dropped. Distinct from
    RedlineError so callers can tell "your move was illegal" apart from
    "we couldn't even ask the server" — the retry/recovery advice differs.
    """


def _http_call(url: str, method: str, payload: dict | None, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else "{}"
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise RedlineConnectionError(f"HTTP {exc.code} from {url}: {body[:200]}") from exc
    except urllib.error.URLError as exc:
        raise RedlineConnectionError(f"Cannot reach REDLINE server at {url}: {exc.reason}") from exc
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RedlineConnectionError(f"Non-JSON response from {url}: {body[:200]}") from exc


@dataclass
class PlayerSession:
    game_id: str
    player_id: str
    resume_token: str | None
    ws: Any = None
    reader_task: asyncio.Task | None = None
    latest_state: dict | None = None
    latest_error: str | None = None
    revision: int = 0
    updated_event: asyncio.Event = field(default_factory=asyncio.Event)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    closed: bool = True


class RedlineClient:
    """One instance per MCP server process. Keeps at most one live WebSocket
    per (game_id, player_id) the process has touched, reconnecting lazily on
    demand. Room "discovery" is deliberately session-local bookkeeping only —
    see docs/mcp_server.md for why no global room-listing endpoint exists.
    """

    def __init__(
        self,
        base_url: str,
        ws_base_url: str | None = None,
        http_timeout: float = 10.0,
        ws_connect_timeout: float = 10.0,
        action_wait_timeout: float = 8.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.ws_base_url = (ws_base_url or self._derive_ws_base(self.base_url)).rstrip("/")
        self.http_timeout = http_timeout
        self.ws_connect_timeout = ws_connect_timeout
        self.action_wait_timeout = action_wait_timeout
        self._sessions: dict[tuple[str, str], PlayerSession] = {}
        self._known_rooms: dict[str, float] = {}
        self._resume_tokens: dict[tuple[str, str], str] = {}
        self._connect_locks: dict[tuple[str, str], asyncio.Lock] = {}

    @staticmethod
    def _derive_ws_base(http_base: str) -> str:
        if http_base.startswith("https://"):
            return "wss://" + http_base[len("https://"):]
        if http_base.startswith("http://"):
            return "ws://" + http_base[len("http://"):]
        return http_base

    async def _http(self, method: str, path: str, payload: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        return await asyncio.to_thread(_http_call, url, method, payload, self.http_timeout)

    def _remember_room(self, game_id: str) -> None:
        self._known_rooms[game_id] = time.time()

    def _remember_resume_token(self, game_id: str, player_id: str | None, resume_token: str | None) -> None:
        if player_id and resume_token:
            self._resume_tokens[self._key(game_id, player_id)] = resume_token

    def known_room_ids(self) -> list[str]:
        return sorted(self._known_rooms, key=self._known_rooms.get, reverse=True)

    # ---------------- lobby (HTTP) ----------------

    async def create_room(self, name: str) -> dict:
        data = await self._http("POST", "/create", {"name": name})
        if data.get("error"):
            raise RedlineError(data["error"], code="create_room_failed")
        self._remember_room(data["game_id"])
        self._remember_resume_token(data["game_id"], data.get("host_id"), data.get("resume_token"))
        return data

    async def join_room(
        self,
        game_id: str,
        name: str,
        player_id: str | None = None,
        resume_token: str | None = None,
        device_id: str | None = None,
    ) -> dict:
        payload: dict[str, Any] = {"game_id": game_id, "name": name}
        if player_id:
            payload["player_id"] = player_id
        if resume_token:
            payload["resume_token"] = resume_token
        if device_id:
            payload["device_id"] = device_id
        data = await self._http("POST", "/join", payload)
        if data.get("error"):
            raise RedlineError(data["error"], code="join_room_failed")
        self._remember_room(game_id)
        self._remember_resume_token(game_id, data.get("player_id"), data.get("resume_token"))
        return data

    async def resume_room(
        self, game_id: str, player_id: str, resume_token: str, device_id: str | None = None
    ) -> dict:
        payload = {"game_id": game_id, "player_id": player_id, "resume_token": resume_token}
        if device_id:
            payload["device_id"] = device_id
        data = await self._http("POST", "/resume", payload)
        if data.get("error"):
            raise RedlineError(data["error"], code="resume_failed")
        self._remember_room(game_id)
        self._remember_resume_token(game_id, data.get("player_id"), data.get("resume_token"))
        return data

    async def room_status(self, game_id: str) -> dict:
        data = await self._http("GET", f"/lobby/{game_id}")
        if data.get("error"):
            raise RedlineError(data["error"], code="room_not_found")
        self._remember_room(game_id)
        return data

    async def choose_faction(
        self, game_id: str, player_id: str, faction_id: str, base_name: str | None = None
    ) -> dict:
        payload: dict[str, Any] = {"game_id": game_id, "player_id": player_id, "faction_id": faction_id}
        if base_name:
            payload["base_name"] = base_name
        data = await self._http("POST", "/choose-faction", payload)
        if data.get("error"):
            raise RedlineError(data["error"], code="choose_faction_failed")
        return data

    async def set_ready(self, game_id: str, player_id: str, ready: bool = True) -> dict:
        data = await self._http("POST", "/ready", {"game_id": game_id, "player_id": player_id, "ready": ready})
        if data.get("error"):
            raise RedlineError(data["error"], code="set_ready_failed")
        return data

    async def set_market_mode(self, game_id: str, player_id: str, market_mode: str) -> dict:
        data = await self._http(
            "POST", "/market-mode", {"game_id": game_id, "player_id": player_id, "market_mode": market_mode}
        )
        if data.get("error"):
            raise RedlineError(data["error"], code="set_market_mode_failed")
        return data

    async def start_game(self, game_id: str, player_id: str, market_mode: str | None = None) -> dict:
        payload: dict[str, Any] = {"game_id": game_id, "player_id": player_id}
        if market_mode:
            payload["market_mode"] = market_mode
        data = await self._http("POST", "/start", payload)
        if data.get("error"):
            raise RedlineError(data["error"], code="start_game_failed")
        return data

    async def list_factions(self) -> dict:
        return await self._http("GET", "/factions")

    async def card_presentation(self) -> dict:
        return await self._http("GET", "/card-presentation")

    # ---------------- gameplay (WebSocket) ----------------

    def _key(self, game_id: str, player_id: str) -> tuple[str, str]:
        return (game_id, player_id)

    async def ensure_connected(
        self, game_id: str, player_id: str, resume_token: str | None = None
    ) -> PlayerSession:
        key = self._key(game_id, player_id)
        session = self._sessions.get(key)
        if session is not None and not session.closed:
            return session
        # Two tool calls for the same not-yet-connected (game_id, player_id)
        # can genuinely race here (an MCP host may dispatch several tool
        # calls from one model turn concurrently) — without this lock both
        # would call _open_ws on the same/a fresh PlayerSession, orphaning
        # one WebSocket + reader task. Re-check after acquiring, since the
        # first racer may have already finished connecting by then.
        lock = self._connect_locks.setdefault(key, asyncio.Lock())
        async with lock:
            session = self._sessions.get(key)
            if session is not None and not session.closed:
                return session
            resume_token = resume_token or self._resume_tokens.get(key)
            if session is None:
                session = PlayerSession(game_id=game_id, player_id=player_id, resume_token=resume_token)
                self._sessions[key] = session
            elif resume_token:
                session.resume_token = resume_token
            await self._open_ws(session)
            return session

    async def _open_ws(self, session: PlayerSession) -> None:
        uri = f"{self.ws_base_url}/ws/{session.game_id}/{session.player_id}"
        subprotocols = [session.resume_token] if session.resume_token else None
        try:
            ws = await asyncio.wait_for(
                websockets.connect(uri, subprotocols=subprotocols),
                timeout=self.ws_connect_timeout,
            )
        except (TimeoutError, OSError, websockets.exceptions.WebSocketException) as exc:
            raise RedlineConnectionError(
                f"Cannot open game connection for player {session.player_id} in game {session.game_id}: {exc}"
            ) from exc
        session.ws = ws
        session.closed = False
        session.revision = 0
        session.latest_state = None
        session.latest_error = None
        session.reader_task = asyncio.create_task(self._read_loop(session))
        try:
            await asyncio.wait_for(self._wait_for_revision_above(session, 0), timeout=self.ws_connect_timeout)
        except TimeoutError as exc:
            await self._close_session(session)
            raise RedlineConnectionError("Connected but no initial state was received in time") from exc
        if session.latest_state is None:
            # _read_loop only ever populates latest_state from a payload that
            # has "turn" in it; anything else (auth rejection, "Game not
            # ready") only sets latest_error, so latest_state staying None
            # here means the first push was one of those.
            message = session.latest_error or "Game not ready"
            await self._close_session(session)
            raise RedlineConnectionError(f"Connection rejected: {message}")

    async def _read_loop(self, session: PlayerSession) -> None:
        try:
            async for raw in session.ws:
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                if "turn" in payload:
                    session.latest_state = payload
                    session.latest_error = payload.get("error")
                else:
                    session.latest_error = payload.get("error") or "Unknown error"
                session.revision += 1
                session.updated_event.set()
                session.updated_event.clear()
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            session.closed = True

    async def _wait_for_revision_above(self, session: PlayerSession, baseline: int) -> None:
        while session.revision <= baseline and not session.closed:
            try:
                await asyncio.wait_for(session.updated_event.wait(), timeout=0.5)
            except TimeoutError:
                continue

    async def get_state(self, game_id: str, player_id: str, resume_token: str | None = None) -> dict:
        self._remember_resume_token(game_id, player_id, resume_token)
        session = await self.ensure_connected(game_id, player_id, resume_token=resume_token)
        if session.latest_state is None:
            raise RedlineConnectionError("No state received yet for this session")
        return session.latest_state

    async def send_action(
        self,
        game_id: str,
        player_id: str,
        action: str,
        payload: dict | None = None,
        resume_token: str | None = None,
    ) -> tuple[dict, str | None]:
        """Send one WS action and wait for the resulting state (or error).

        Returns (state, error) — error is the server's own message string, or
        None on success. This mirrors the real client contract: a rejected
        action still comes back as a full, privacy-scoped state plus an
        `error` string, never a bare exception, so the caller (and in turn
        the LLM) always has enough context to pick a different next move.
        """
        self._remember_resume_token(game_id, player_id, resume_token)
        session = await self.ensure_connected(game_id, player_id, resume_token=resume_token)
        async with session.lock:
            message = {"action": action, **(payload or {})}
            before_revision = session.revision
            try:
                await session.ws.send(json.dumps(message))
            except websockets.exceptions.ConnectionClosed as exc:
                session.closed = True
                raise RedlineConnectionError(
                    f"Connection lost while sending '{action}'; the next tool call will reconnect automatically"
                ) from exc
            try:
                await asyncio.wait_for(
                    self._wait_for_revision_above(session, before_revision), timeout=self.action_wait_timeout
                )
            except TimeoutError as exc:
                raise RedlineConnectionError(
                    f"No response to '{action}' within {self.action_wait_timeout}s; "
                    "call get_state to check whether it actually applied before retrying"
                ) from exc
            if session.revision <= before_revision:
                # The wait loop only exits without a fresh revision when the
                # connection closed mid-wait (see _wait_for_revision_above) —
                # never silently return pre-action stale state as if it were
                # the result.
                raise RedlineConnectionError(
                    f"Connection closed while waiting for a response to '{action}'; "
                    "call get_state to check whether it actually applied before retrying"
                )
            state = session.latest_state or {}
            return state, state.get("error")

    async def close_session(self, game_id: str, player_id: str) -> None:
        session = self._sessions.pop(self._key(game_id, player_id), None)
        if session is not None:
            await self._close_session(session)

    async def _close_session(self, session: PlayerSession) -> None:
        session.closed = True
        if session.reader_task is not None:
            session.reader_task.cancel()
        if session.ws is not None:
            try:
                await session.ws.close()
            except Exception:
                pass

    async def aclose(self) -> None:
        for session in list(self._sessions.values()):
            await self._close_session(session)
        self._sessions.clear()
