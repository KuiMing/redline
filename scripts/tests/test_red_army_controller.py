from __future__ import annotations

import asyncio
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from red_army_controller.config import ControllerConfig
from red_army_controller.controller import (
    ControllerStopped,
    RedArmyController,
    state_fingerprint,
    trigger_reason,
)
from red_army_controller.hermes_runner import AgentRunResult, HermesRunner, build_agent_prompt
from red_army_controller.mcp_gateway import MCPGateway
from red_army_controller.state_store import SeatCredentials, StateFileError, StateStore


CREDS = SeatCredentials("game-public-code", "private-player-id", "private-resume-token")


def _state(*, mine=False, pending=False, game_over=False):
    return {
        "ok": True,
        "state": {
            "game_phase": "finished" if game_over else "main",
            "turn_phase": "action",
            "is_my_turn": mine,
            "my_faction": "red_army",
            "game_over": game_over,
            "pending_choice": {"is_mine_to_resolve": True, "choice_key": "x"} if pending else None,
        },
        "legal_action_kinds": {"waiting_on": None},
    }


def test_trigger_matrix():
    assert trigger_reason(_state(mine=True)) == "red_army_turn"
    assert trigger_reason(_state(pending=True)) == "red_army_pending_choice"
    assert trigger_reason(_state()) is None
    assert trigger_reason(_state(mine=True, game_over=True)) is None
    waiting_on_human = _state(mine=True)
    waiting_on_human["state"]["pending_choice"] = {"is_mine_to_resolve": False}
    assert trigger_reason(waiting_on_human) is None


def test_fingerprint_is_stable_and_changes_with_legal_state():
    a = state_fingerprint(_state(mine=True), {"actions": [{"kind": "advance_turn"}]})
    b = state_fingerprint(_state(mine=True), {"actions": [{"kind": "advance_turn"}]})
    c = state_fingerprint(_state(mine=True), {"actions": []})
    assert a == b
    assert a != c


def test_lobby_gate_requires_two_complete_ready_seats():
    controller = RedArmyController(ControllerConfig())
    base = {
        "started": False,
        "seat_count": 2,
        "players": [{"player_id": "private-player-id"}, {"player_id": "p2"}],
        "factions": {"private-player-id": "red_army", "p2": "taiwan_green"},
        "ready": {"private-player-id": True, "p2": True},
    }
    assert controller.lobby_can_start(base, CREDS)
    for mutation in (
        {"seat_count": 1, "players": [{"player_id": "private-player-id"}]},
        {"ready": {"private-player-id": True, "p2": False}},
        {"factions": {"private-player-id": "red_army"}},
        {"started": True},
    ):
        room = dict(base)
        room.update(mutation)
        assert not controller.lobby_can_start(room, CREDS)


def test_state_store_is_0600_and_rejects_loose_permissions(tmp_path):
    path = tmp_path / "state" / "seat.json"
    store = StateStore(path)
    store.save(CREDS)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert store.load() == CREDS
    os.chmod(path, 0o644)
    with pytest.raises(StateFileError, match="0600"):
        store.load()


def test_state_store_refuses_symlink(tmp_path):
    real = tmp_path / "real.json"
    real.write_text("{}")
    link = tmp_path / "link.json"
    link.symlink_to(real)
    with pytest.raises(StateFileError, match="symlink"):
        StateStore(link).save(CREDS)


def test_prompt_contains_no_resume_token_and_defends_against_game_prompt_injection():
    prompt = build_agent_prompt(CREDS.game_id, CREDS.player_id, "red_army_turn")
    assert CREDS.resume_token not in prompt
    assert "玩家名稱、action log、卡牌文字" in prompt
    assert "非 REDLINE MCP tools" in prompt


@pytest.mark.anyio
async def test_hermes_runner_suppresses_stdout_and_uses_dedicated_profile(tmp_path, monkeypatch):
    argv_path = tmp_path / "argv"
    fake = tmp_path / "fake-hermes"
    fake.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$FAKE_ARGV\"\nprintf 'PRIVATE HAND SHOULD NOT ESCAPE\\n'\nprintf 'stderr secret\\n' >&2\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    monkeypatch.setenv("FAKE_ARGV", str(argv_path))
    runner = HermesRunner(str(fake), "redarmy", 5, cwd=tmp_path)
    result = await runner.run("safe prompt")
    assert result.returncode == 0
    argv = argv_path.read_text()
    assert "redarmy" in argv
    assert "mcp-redline" in argv
    assert "--ignore-rules" in argv
    assert "safe prompt" in argv


@pytest.mark.anyio
async def test_hermes_runner_terminates_child_when_controller_stops(tmp_path):
    fake = tmp_path / "slow-hermes"
    fake.write_text("#!/bin/sh\nsleep 60\n", encoding="utf-8")
    fake.chmod(0o755)
    stop = asyncio.Event()
    runner = HermesRunner(str(fake), "redarmy", 30, cwd=tmp_path, stop_event=stop)
    task = asyncio.create_task(runner.run("safe prompt"))
    await asyncio.sleep(0.1)
    stop.set()
    result = await asyncio.wait_for(task, timeout=3)
    assert result.returncode != 0
    assert not result.timed_out


class FakeGateway:
    def __init__(self, state, legal, *, on_state=None):
        self.state = state
        self.legal = legal
        self.on_state = on_state
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def call(self, name, arguments=None):
        self.calls.append((name, arguments or {}))
        if name == "resume_room":
            return {"ok": True, "faction_id": "red_army"}
        if name == "get_room_status":
            return {"ok": True, "started": True}
        if name == "get_state":
            if self.on_state:
                self.on_state()
            return self.state
        if name == "get_legal_actions":
            return self.legal
        raise AssertionError(name)


class StoppingRunner:
    def __init__(self, controller=None, stop_after=1):
        self.controller = controller
        self.stop_after = stop_after
        self.calls = 0
        self.prompts = []

    async def run(self, prompt):
        self.calls += 1
        self.prompts.append(prompt)
        if self.controller and self.calls >= self.stop_after:
            self.controller.stop()
        return AgentRunResult(0)


@pytest.mark.anyio
async def test_controller_invokes_only_when_red_army_actionable(monkeypatch, tmp_path):
    config = ControllerConfig(state_file=tmp_path / "seat", poll_seconds=0.01, post_agent_settle_seconds=0)
    runner = StoppingRunner(stop_after=1)
    controller = RedArmyController(config, runner=runner)
    runner.controller = controller
    gateway = FakeGateway(_state(mine=True), {"ok": True, "actions": [{"kind": "advance_turn"}]})
    monkeypatch.setattr("red_army_controller.controller.MCPGateway", lambda _url: gateway)
    await controller.run(CREDS)
    assert runner.calls == 1
    assert CREDS.resume_token not in runner.prompts[0]


@pytest.mark.anyio
async def test_controller_never_invokes_while_waiting_for_human(monkeypatch, tmp_path):
    config = ControllerConfig(state_file=tmp_path / "seat", poll_seconds=0.01)
    runner = StoppingRunner()
    controller = RedArmyController(config, runner=runner)
    reads = 0

    def stop_after_read():
        nonlocal reads
        reads += 1
        if reads >= 2:
            controller.stop()

    gateway = FakeGateway(_state(), {"ok": True, "waiting_on": "Human", "actions": []}, on_state=stop_after_read)
    monkeypatch.setattr("red_army_controller.controller.MCPGateway", lambda _url: gateway)
    await controller.run(CREDS)
    assert runner.calls == 0


@pytest.mark.anyio
async def test_unchanged_actionable_state_stops_at_safe_limit(monkeypatch, tmp_path):
    config = ControllerConfig(
        state_file=tmp_path / "seat",
        poll_seconds=0.01,
        post_agent_settle_seconds=0,
        max_agent_invocations_per_state=2,
    )
    runner = StoppingRunner()
    controller = RedArmyController(config, runner=runner)
    gateway = FakeGateway(_state(mine=True), {"ok": True, "actions": [{"kind": "advance_turn"}]})
    monkeypatch.setattr("red_army_controller.controller.MCPGateway", lambda _url: gateway)
    with pytest.raises(ControllerStopped, match="unchanged"):
        await controller.run(CREDS)
    assert runner.calls == 2


@pytest.mark.anyio
async def test_controller_never_invokes_for_other_players_choice_during_red_turn(monkeypatch, tmp_path):
    config = ControllerConfig(state_file=tmp_path / "seat", poll_seconds=0.01)
    runner = StoppingRunner()
    controller = RedArmyController(config, runner=runner)
    waiting_state = _state(mine=True)
    waiting_state["state"]["pending_choice"] = {"is_mine_to_resolve": False}
    reads = 0

    def stop_after_read():
        nonlocal reads
        reads += 1
        if reads >= 2:
            controller.stop()

    gateway = FakeGateway(waiting_state, {"ok": True, "waiting_on": "Human", "actions": []}, on_state=stop_after_read)
    monkeypatch.setattr("red_army_controller.controller.MCPGateway", lambda _url: gateway)
    await controller.run(CREDS)
    assert runner.calls == 0


@pytest.mark.anyio
async def test_changing_states_still_stop_at_action_window_budget(monkeypatch, tmp_path):
    config = ControllerConfig(
        state_file=tmp_path / "seat",
        poll_seconds=0.01,
        post_agent_settle_seconds=0,
        max_agent_invocations_per_state=5,
        max_agent_invocations_per_action_window=2,
    )
    runner = StoppingRunner()
    controller = RedArmyController(config, runner=runner)
    changing = _state(mine=True)

    def change_fingerprint():
        changing["state"]["turn"] = int(changing["state"].get("turn") or 0) + 1

    gateway = FakeGateway(changing, {"ok": True, "actions": [{"kind": "advance_turn"}]}, on_state=change_fingerprint)
    monkeypatch.setattr("red_army_controller.controller.MCPGateway", lambda _url: gateway)
    with pytest.raises(ControllerStopped, match="invocation budget"):
        await controller.run(CREDS)
    assert runner.calls == 2


@pytest.mark.anyio
async def test_mcp_gateway_cleans_transport_when_session_initialization_fails(monkeypatch):
    events = []

    class Transport:
        async def __aenter__(self):
            events.append("transport_enter")
            return (object(), object())

        async def __aexit__(self, *args):
            events.append("transport_exit")

    class BrokenSession:
        def __init__(self, *_args):
            pass

        async def __aenter__(self):
            raise RuntimeError("broken initialization")

        async def __aexit__(self, *args):
            events.append("session_exit")

    monkeypatch.setattr("red_army_controller.mcp_gateway.streamable_http_client", lambda _url: Transport())
    monkeypatch.setattr("red_army_controller.mcp_gateway.ClientSession", BrokenSession)
    with pytest.raises(RuntimeError, match="broken initialization"):
        async with MCPGateway("http://127.0.0.1:1/mcp"):
            pass
    assert events == ["transport_enter", "transport_exit"]
