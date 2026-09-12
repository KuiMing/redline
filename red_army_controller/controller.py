from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Protocol

from red_army_controller.config import ControllerConfig
from red_army_controller.hermes_runner import AgentRunResult, HermesRunner, build_agent_prompt
from red_army_controller.mcp_gateway import MCPGateway, MCPGatewayError
from red_army_controller.state_store import SeatCredentials, StateStore

LOG = logging.getLogger("redline-red-army")


class AgentRunner(Protocol):
    async def run(self, prompt: str) -> AgentRunResult: ...


class ControllerStopped(RuntimeError):
    pass


@dataclass(frozen=True)
class SafeStatus:
    game_id: str
    phase: str | None
    turn_phase: str | None
    is_red_army_turn: bool
    waiting_on: str | None
    game_over: bool


def state_fingerprint(state_result: dict, legal_result: dict) -> str:
    material = {"state": state_result.get("state"), "legal": legal_result}
    raw = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def trigger_reason(state_result: dict) -> str | None:
    state = state_result.get("state") or {}
    if state.get("game_over"):
        return None
    pending = state.get("pending_choice") or {}
    if pending:
        if pending.get("is_mine_to_resolve"):
            return "red_army_pending_choice"
        return None
    if state.get("is_my_turn"):
        return "red_army_turn"
    return None


def safe_status(credentials: SeatCredentials, state_result: dict, legal_result: dict) -> SafeStatus:
    state = state_result.get("state") or {}
    legal_kinds = state_result.get("legal_action_kinds") or {}
    return SafeStatus(
        game_id=credentials.game_id,
        phase=state.get("game_phase"),
        turn_phase=state.get("turn_phase"),
        is_red_army_turn=bool(state.get("is_my_turn")),
        waiting_on=legal_result.get("waiting_on") or legal_kinds.get("waiting_on"),
        game_over=bool(state.get("game_over")),
    )


class RedArmyController:
    def __init__(self, config: ControllerConfig, runner: AgentRunner | None = None):
        self.config = config
        self.store = StateStore(config.state_file)
        self._stop = asyncio.Event()
        self.runner = runner or HermesRunner(
            config.hermes_binary,
            config.hermes_profile,
            config.agent_timeout_seconds,
            stop_event=self._stop,
            mcp_server_name=config.mcp_server_name,
        )

    def stop(self) -> None:
        self._stop.set()

    async def create(self) -> SeatCredentials:
        async with MCPGateway(self.config.mcp_url) as gateway:
            created = await gateway.call("create_room", {"player_name": self.config.player_name})
            if not created.get("ok"):
                raise MCPGatewayError(str(created.get("error") or "Could not create room"))
            credentials = SeatCredentials(
                game_id=str(created["game_id"]),
                player_id=str(created["player_id"]),
                resume_token=str(created["resume_token"]),
                role=str(created.get("role") or "host"),
                player_name=self.config.player_name,
            )
            chosen = await gateway.call("choose_faction", {
                "game_id": credentials.game_id,
                "player_id": credentials.player_id,
                "faction_id": "red_army",
            })
            if not chosen.get("ok"):
                raise MCPGatewayError(str(chosen.get("error") or "Could not choose Red Army"))
            ready = await gateway.call("set_ready", {
                "game_id": credentials.game_id,
                "player_id": credentials.player_id,
                "ready": True,
            })
            if not ready.get("ok"):
                raise MCPGatewayError(str(ready.get("error") or "Could not mark Red Army ready"))
            self.store.save(credentials)
            return credentials

    async def hydrate(self, gateway: MCPGateway, credentials: SeatCredentials) -> None:
        resumed = await gateway.call("resume_room", {
            "game_id": credentials.game_id,
            "player_id": credentials.player_id,
            "resume_token": credentials.resume_token,
        })
        if not resumed.get("ok"):
            raise MCPGatewayError(str(resumed.get("error") or "Could not resume Red Army seat"))
        if resumed.get("faction_id") not in (None, "red_army"):
            raise MCPGatewayError("Saved seat is not the Red Army seat")

    @staticmethod
    def lobby_can_start(room: dict, credentials: SeatCredentials) -> bool:
        if room.get("started") or credentials.role != "host":
            return False
        seat_count = int(room.get("seat_count") or 0)
        if seat_count < 2:
            return False
        players = room.get("players") or []
        player_ids = {str(row.get("player_id")) for row in players}
        factions = room.get("factions") or {}
        ready = room.get("ready") or {}
        return (
            len(player_ids) == seat_count
            and set(map(str, factions.keys())) == player_ids
            and all(bool(ready.get(pid)) for pid in player_ids)
            and sum(1 for faction in factions.values() if faction == "red_army") == 1
        )

    async def _ensure_started(self, gateway: MCPGateway, credentials: SeatCredentials) -> bool:
        room = await gateway.call("get_room_status", {"game_id": credentials.game_id})
        if not room.get("ok"):
            raise MCPGatewayError(str(room.get("error") or "Could not read lobby"))
        if room.get("started"):
            return True
        if self.lobby_can_start(room, credentials):
            result = await gateway.call("start_game", {
                "game_id": credentials.game_id,
                "player_id": credentials.player_id,
            })
            if not result.get("ok"):
                raise MCPGatewayError(str(result.get("error") or "Could not start game"))
            LOG.info("All seats are ready; game started")
            return True
        return False

    async def _read_turn(self, gateway: MCPGateway, credentials: SeatCredentials) -> tuple[dict, dict]:
        state = await gateway.call("get_state", {
            "game_id": credentials.game_id,
            "player_id": credentials.player_id,
        })
        legal = await gateway.call("get_legal_actions", {
            "game_id": credentials.game_id,
            "player_id": credentials.player_id,
        })
        if (state.get("state") or {}).get("my_faction") != "red_army":
            raise MCPGatewayError("Saved seat is not the Red Army seat")
        return state, legal

    async def status(self) -> SafeStatus | None:
        credentials = self.store.load()
        async with MCPGateway(self.config.mcp_url) as gateway:
            await self.hydrate(gateway, credentials)
            room = await gateway.call("get_room_status", {"game_id": credentials.game_id})
            if not room.get("started"):
                return SafeStatus(credentials.game_id, "lobby", None, False, "players", False)
            state, legal = await self._read_turn(gateway, credentials)
            return safe_status(credentials, state, legal)

    async def run(self, credentials: SeatCredentials | None = None) -> None:
        credentials = credentials or self.store.load()
        same_fingerprint: str | None = None
        invocations_for_fingerprint = 0
        invocations_for_action_window = 0
        consecutive_failures = 0

        while not self._stop.is_set():
            try:
                async with MCPGateway(self.config.mcp_url) as gateway:
                    await self.hydrate(gateway, credentials)
                    while not self._stop.is_set():
                        if not await self._ensure_started(gateway, credentials):
                            await self._sleep()
                            continue

                        state, legal = await self._read_turn(gateway, credentials)
                        status = safe_status(credentials, state, legal)
                        if status.game_over:
                            LOG.info("Game over; controller stopped")
                            return
                        reason = trigger_reason(state)
                        if reason is None:
                            same_fingerprint = None
                            invocations_for_fingerprint = 0
                            summary = state.get("state") or {}
                            pending = summary.get("pending_choice") or {}
                            if not summary.get("is_my_turn") and not pending.get("is_mine_to_resolve"):
                                invocations_for_action_window = 0
                            consecutive_failures = 0
                            await self._sleep()
                            continue

                        fingerprint = state_fingerprint(state, legal)
                        if fingerprint != same_fingerprint:
                            same_fingerprint = fingerprint
                            invocations_for_fingerprint = 0
                        if invocations_for_fingerprint >= self.config.max_agent_invocations_per_state:
                            raise ControllerStopped("Agent left the same actionable state unchanged too many times")
                        if invocations_for_action_window >= self.config.max_agent_invocations_per_action_window:
                            raise ControllerStopped("Agent exceeded the invocation budget for one Red Army action window")

                        invocations_for_fingerprint += 1
                        invocations_for_action_window += 1
                        LOG.info("Red Army decision required: %s", reason)
                        result = await self.runner.run(
                            build_agent_prompt(
                                credentials.game_id,
                                credentials.player_id,
                                reason,
                                self.config.mcp_server_name,
                            )
                        )
                        if result.returncode != 0 or result.timed_out:
                            consecutive_failures += 1
                            if consecutive_failures >= self.config.max_consecutive_agent_failures:
                                raise ControllerStopped("Hermes Agent failed repeatedly; controller stopped safely")
                            await self._sleep(self.config.failure_backoff_seconds * consecutive_failures)
                            continue
                        consecutive_failures = 0
                        await self._sleep(self.config.post_agent_settle_seconds)
            except ControllerStopped:
                raise
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                LOG.warning("MCP/REDLINE temporarily unavailable: %s", type(exc).__name__)
                await self._sleep(self.config.failure_backoff_seconds)

    async def _sleep(self, seconds: float | None = None) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds if seconds is not None else self.config.poll_seconds)
        except TimeoutError:
            pass
