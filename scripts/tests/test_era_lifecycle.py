import random
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from server.era_engine import EraEngine
from server.game import Game, GamePhase, TurnPhase


def _make_game(actor_faction="taiwan_green"):
    random.seed(20260728)
    game = Game([("actor", "actor"), ("red", "red")], market_mode="all_cards")
    actor, red = game.players
    actor.id = "actor"
    actor.name = "actor"
    actor.faction_id = actor_faction
    actor.organizations = {}
    red.id = "red"
    red.name = "red"
    red.faction_id = "red_army"
    red.organizations = {"北京": 1}
    game.current_player_index = 0
    game.round_start_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.winner = None
    game.pending_choice = None
    # Keep this focused on public lifecycle advancement rather than event effects.
    game.current_event = {"id": "test-idle", "name": "test idle", "type": "idle"}
    game.event_progress = {
        "count": 0,
        "required": 0,
        "succeeded": True,
        "settled": True,
        "status": "idle",
    }
    return game, actor, red


def _advance_current_player_turn(game):
    assert game.turn_phase == TurnPhase.ACTION
    assert game.advance_turn_phase() == {"success": True}
    assert game.turn_phase == TurnPhase.END
    assert game.advance_turn_phase() == {"success": True}
    assert game.turn_phase == TurnPhase.ACTION


def _legal_inside_wall_towns(game, player):
    return [
        town
        for town in game._towns_for_region_alias("china")
        if game.can_faction_develop_in_town(player.faction_id, town)
    ]


def test_taiwan_era_triggers_at_seven_distinct_inside_wall_organizations_via_phase_lifecycle():
    game, taiwan, _red = _make_game()
    legal_inside_towns = _legal_inside_wall_towns(game, taiwan)
    assert len(legal_inside_towns) >= 7

    taiwan.organizations = {town: 1 for town in legal_inside_towns[:6]}
    _advance_current_player_turn(game)
    assert "taiwan" not in game.era_engine.get_active_eras()

    taiwan.organizations[legal_inside_towns[6]] = 1
    _advance_current_player_turn(game)
    assert "taiwan" in game.era_engine.get_active_eras()
    assert game.era_engine.get_active_era_details()[0]["remaining"] == 2


def test_timed_era_is_not_consumed_on_activation_boundary_or_reactivated_after_expiry():
    game, taiwan, _red = _make_game()
    legal_inside_towns = _legal_inside_wall_towns(game, taiwan)
    taiwan.organizations = {town: 1 for town in legal_inside_towns[:7]}

    _advance_current_player_turn(game)
    assert game.era_engine.get_active_era_details()[0]["remaining"] == 2
    activation_discard_count = len(taiwan.deck.discard_pile)

    _advance_current_player_turn(game)
    assert game.era_engine.get_active_era_details()[0]["remaining"] == 1
    game.current_event = {"id": "next-idle", "name": "next idle", "type": "idle"}
    game.event_progress = {
        "count": 0,
        "required": 0,
        "succeeded": True,
        "settled": True,
        "status": "idle",
    }
    _advance_current_player_turn(game)
    assert "taiwan" not in game.era_engine.get_active_eras()
    assert "taiwan" in game.era_engine.get_activated_eras()
    assert len(taiwan.deck.discard_pile) == activation_discard_count


def test_expired_one_time_era_is_achieved_but_not_active_in_viewer_public_state():
    game, taiwan, _red = _make_game()
    legal_inside_towns = _legal_inside_wall_towns(game, taiwan)
    taiwan.organizations = {town: 1 for town in legal_inside_towns[:7]}
    _advance_current_player_turn(game)
    game.era_engine.tick()
    game.era_engine.tick()

    stage = game.state(viewer_player_id=taiwan.id)["my_era_stage"]
    assert stage["id"] == "taiwan"
    assert stage["achieved"] is True
    assert stage["active"] is False
    assert stage["remaining"] is None


def test_era_engine_without_activation_history_treats_active_eras_as_activated():
    engine = EraEngine([{
        "id": "legacy-era",
        "name": "legacy era",
        "duration": {"type": "turns", "value": 1},
    }])
    engine.active["legacy-era"] = {
        "remaining": 1,
        "definition": engine.get_definition("legacy-era"),
    }
    del engine.activated

    assert engine.get_activated_eras() == ["legacy-era"]
    assert engine.activate_era("legacy-era") is False
    engine.tick()
    assert engine.get_active_eras() == []
    assert engine.get_activated_eras() == ["legacy-era"]


def test_era_activation_effect_failure_is_not_retried_after_partial_mutation():
    game, taiwan, _red = _make_game()
    legal_inside_towns = _legal_inside_wall_towns(game, taiwan)
    taiwan.organizations = {town: 1 for town in legal_inside_towns[:7]}
    apply_calls = []

    def fail_after_partial_mutation(era):
        apply_calls.append(era["id"])
        taiwan.deck.discard_pile.append("partial activation mutation")
        raise RuntimeError("test partial activation failure")

    game._apply_era_activation_effects = fail_after_partial_mutation
    try:
        game._check_era_trigger()
    except RuntimeError as exc:
        assert str(exc) == "test partial activation failure"
    else:
        raise AssertionError("partial activation failure was not propagated")

    assert "taiwan" in game.era_engine.get_activated_eras()
    assert game._pending_era_activations == []
    assert apply_calls == ["taiwan"]
    assert taiwan.deck.discard_pile[-1] == "partial activation mutation"

    assert game._continue_era_activation_queue() == {
        "success": True,
        "pending_choice": False,
        "queued": [],
    }
    assert apply_calls == ["taiwan"]
    assert taiwan.deck.discard_pile.count("partial activation mutation") == 1


def _configure_same_boundary_auto_discard_event(game):
    game.current_event = {"id": "old-idle", "name": "old idle", "type": "idle"}
    game.event_progress = {
        "count": 0,
        "required": 0,
        "succeeded": True,
        "settled": True,
        "status": "idle",
    }
    game.event_deck.draw_pile = [{
        "id": "test-auto-discard",
        "name": "test auto discard",
        "type": "auto",
        "effect": {"type": "discard_self", "count": 1},
    }]
    game.event_deck.discard_pile = []
    # Ending the final player wraps the round and draws the configured auto event.
    game.current_player_index = 1
    game.round_start_player_index = 0


def test_tibet_activation_choice_completes_before_same_boundary_auto_event_choice():
    game, tibet, red = _make_game("tibet_dharamsala")
    inside_towns = [town for town in _legal_inside_wall_towns(game, tibet) if game._shared_org_count(red, town) == 0]
    assert len(inside_towns) >= 7
    tibet.organizations = {town: 1 for town in inside_towns[:7]}
    _configure_same_boundary_auto_discard_event(game)

    _advance_current_player_turn(game)
    assert "tibet" in game.era_engine.get_active_eras()
    pending = game.pending_choice
    assert pending is not None
    assert pending["choice_key"] == "era_red_discard_to_build_near_target"
    assert game.event_progress["status"] == "auto_deferred"

    first = game.resolve_pending_choice(red.id, [0])
    assert first.get("pending_choice") is True
    pending = game.pending_choice
    assert pending is not None
    assert pending["choice_key"] == "era_red_build_near_target"
    second = game.resolve_pending_choice(red.id, 0)
    assert second.get("pending_choice") is True
    pending = game.pending_choice
    assert pending is not None
    assert pending["choice_key"] == "event_discard_self"
    assert pending["player_id"] == tibet.id
    assert game.event_progress["settled"] is True


def test_manchuria_activation_choice_completes_before_same_boundary_auto_event_choice():
    game, manchuria, _red = _make_game("manchuria")
    inside_towns = [town for town in _legal_inside_wall_towns(game, manchuria) if game._shared_org_count(_red, town) == 0]
    assert len(inside_towns) >= 10
    manchuria.organizations = {town: 1 for town in inside_towns[:10]}
    _configure_same_boundary_auto_discard_event(game)

    _advance_current_player_turn(game)
    assert "manchuria" in game.era_engine.get_active_eras()
    pending = game.pending_choice
    assert pending is not None
    assert pending["choice_key"] == "era_inspect_deck_top_and_reorder"
    assert game.event_progress["status"] == "auto_deferred"

    result = game.resolve_pending_choice(manchuria.id, [0, 1])
    assert result.get("pending_choice") is True
    pending = game.pending_choice
    assert pending is not None
    assert pending["choice_key"] == "event_discard_self"
    assert pending["player_id"] == manchuria.id
    assert game.event_progress["settled"] is True


def test_simultaneous_tibet_and_manchuria_eras_serialize_before_auto_event():
    random.seed(20260728)
    game = Game([("tibet", "tibet"), ("manchuria", "manchuria"), ("red", "red")], market_mode="all_cards")
    tibet, manchuria, red = game.players
    for player, player_id, faction_id in (
        (tibet, "tibet", "tibet_dharamsala"),
        (manchuria, "manchuria", "manchuria"),
        (red, "red", "red_army"),
    ):
        player.id = player_id
        player.name = player_id
        player.faction_id = faction_id
        player.organizations = {}
    inside_towns = [town for town in _legal_inside_wall_towns(game, tibet) if town != "北京"]
    tibet.organizations = {town: 1 for town in inside_towns[:7]}
    manchuria.organizations = {town: 1 for town in inside_towns[7:17]}
    red.organizations = {"北京": 1}
    game.current_player_index = 2
    game.round_start_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.winner = None
    game.pending_choice = None
    _configure_same_boundary_auto_discard_event(game)
    game.current_player_index = 2

    _advance_current_player_turn(game)
    assert game.era_engine.get_activated_eras() == ["tibet"]
    assert game._pending_era_activations == ["manchuria"]
    assert game.pending_choice["choice_key"] == "era_red_discard_to_build_near_target"
    assert game.event_progress["status"] == "auto_deferred"

    first_tibet = game.resolve_pending_choice(red.id, [0])
    assert first_tibet.get("pending_choice") is True
    assert game.pending_choice["choice_key"] == "era_red_build_near_target"
    assert "manchuria" not in game.era_engine.get_activated_eras()

    second_tibet = game.resolve_pending_choice(red.id, 0)
    assert second_tibet.get("pending_choice") is True
    assert set(game.era_engine.get_activated_eras()) == {"tibet", "manchuria"}
    assert game._pending_era_activations == []
    assert game.pending_choice["choice_key"] == "era_inspect_deck_top_and_reorder"

    manchuria_result = game.resolve_pending_choice(manchuria.id, [0, 1])
    assert manchuria_result.get("pending_choice") is True
    assert game.pending_choice["choice_key"] == "event_discard_self"
    assert game.pending_choice["player_id"] == tibet.id
    assert game.event_progress["settled"] is True
