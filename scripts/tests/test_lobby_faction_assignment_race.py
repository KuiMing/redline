"""Regression tests for the lobby-vs-Game-construction faction assignment race.

Game.__init__ may resolve the game's first event card (some "auto" events are
restricted to a specific faction, e.g. player_faction: "red_army") before
returning. _assign_factions() previously always picked a *random* interim
faction combination during construction, and the real lobby-chosen factions
were applied by overriding player.faction_id only *after* Game() returned —
too late if the very first event card had already resolved (or misattributed
a deferred choice) against whichever player construction's own random
assignment happened to designate as red_army, rather than the player who
actually chose that faction in the lobby.

Game.__init__ / _assign_factions now accept an optional `factions` mapping so
a caller that already knows the real chosen factions (the lobby) can hand
them in directly, skipping the random placeholder assignment entirely.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server import main
from server.game import Game

EVENTS = json.loads((ROOT / "data" / "events_structured.v1.1.json").read_text(encoding="utf-8")).get("events", [])
BELT_ROAD_SOUTHEAST = next(e for e in EVENTS if e.get("id") == "belt_road_southeast")


def test_game_constructor_uses_the_given_factions_verbatim_when_provided():
    players_data = [("p1", "苑"), ("p2", "host")]
    game = Game(players_data, factions={"p1": "wan", "p2": "red_army"})
    assigned = {p.id: p.faction_id for p in game.players}
    assert assigned == {"p1": "wan", "p2": "red_army"}


def test_first_auto_event_never_misattributes_to_the_non_target_player():
    """Reproduces the reported bug: a red-army-only auto event ('一帶一路 南洋')
    resolving against whoever the round's current player happens to be, instead
    of deferring until it is genuinely the red army player's turn."""
    players_data = [("p1", "苑"), ("p2", "host")]
    game = Game(players_data, factions={"p1": "wan", "p2": "red_army"})
    assert game.current_player().id == "p1"  # round 1 opens on the first-listed player

    game.current_event = dict(BELT_ROAD_SOUTHEAST)
    game.event_progress = {"count": 0, "required": 0, "succeeded": False, "settled": False, "status": "active"}
    deferred_result = game._apply_auto_event_if_ready()

    assert deferred_result.get("deferred") is True
    assert deferred_result.get("target_player_id") == "p2"
    # Must not hand the wan player (p1) a pending choice meant for red army.
    assert game.pending_choice is None

    game.current_player_index = 1  # now genuinely red army's turn
    settled_result = game._apply_auto_event_if_ready()

    assert settled_result.get("pending_choice") is True
    assert game.pending_choice["player_id"] == "p2"


def test_assign_factions_without_a_mapping_still_randomizes_for_legacy_callers():
    """Test/debug routes construct Game(players) then override faction_id
    afterward and explicitly reset pending_choice/game_phase themselves, so
    they are unaffected by (and must keep working without) the new parameter."""
    players_data = [("p1", "a"), ("p2", "b")]
    game = Game(players_data)
    assert sum(1 for p in game.players if p.faction_id == "red_army") == 1


def _start_two_player_lobby_game(client, host_faction, host_base, guest_faction, guest_base=None):
    created = client.post("/create", json={"name": "Host", "device_id": "race-host"}).json()
    game_id = created["game_id"]
    host_id = created["host_id"]
    joined = client.post("/join", json={
        "game_id": game_id,
        "name": "Guest",
        "device_id": "race-guest",
    }).json()
    guest_id = joined["player_id"]

    host_payload = {"game_id": game_id, "player_id": host_id, "faction_id": host_faction}
    if host_base:
        host_payload["base_name"] = host_base
    client.post("/choose-faction", json=host_payload)

    guest_payload = {"game_id": game_id, "player_id": guest_id, "faction_id": guest_faction}
    if guest_base:
        guest_payload["base_name"] = guest_base
    client.post("/choose-faction", json=guest_payload)

    client.post("/ready", json={"game_id": game_id, "player_id": host_id, "ready": True})
    client.post("/ready", json={"game_id": game_id, "player_id": guest_id, "ready": True})
    result = client.post("/start", json={"game_id": game_id, "player_id": host_id}).json()
    assert result.get("success") is True, result
    return game_id, host_id, guest_id


def test_lobby_start_assigns_the_real_chosen_factions_not_a_randomized_placeholder():
    client = TestClient(main.app)
    game_id, host_id, guest_id = _start_two_player_lobby_game(
        client, host_faction="wan", host_base="南陽", guest_faction="red_army",
    )
    game = main.manager.games[game_id]
    factions_by_id = {p.id: p.faction_id for p in game.players}
    assert factions_by_id == {host_id: "wan", guest_id: "red_army"}
