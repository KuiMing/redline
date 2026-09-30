import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game, GamePhase, TurnPhase


def _card(game, name):
    return game._starter_card(name)


def _game(player_count=4):
    game = Game([(f"p{i}", f"P{i}") for i in range(1, player_count + 1)])
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.current_player_index = 0
    game.pending_base_choices = {}
    game.current_event = None
    game.event_progress = {}
    game.pending_choice = None
    for player in game.players:
        player.faction_id = None
        player.hand = []
        player.deck.discard_pile = []
    actor = game.players[0]
    actor.hand = [_card(game, "離間")]
    return game


def _conflicts(player):
    return sum(card.name == "內鬥" for card in player.deck.discard_pile)


def test_divide_places_one_conflict_on_each_selected_distinct_player_only():
    game = _game(4)
    actor, selected_a, unselected, selected_b = game.players
    supply_before = game.static_purchase_supply["內鬥"]

    result = game.play_card(
        0,
        mode="action",
        target_player_ids=[selected_a.id, selected_b.id],
    )

    assert result.get("success") is True
    assert [_conflicts(player) for player in game.players] == [0, 1, 0, 1]
    assert game.static_purchase_supply["內鬥"] == supply_before - 2
    assert actor.hand == []


def test_divide_rejects_duplicate_targets_before_committing_card():
    game = _game(4)
    actor, target, *_ = game.players
    supply_before = game.static_purchase_supply["內鬥"]

    result = game.play_card(
        0,
        mode="action",
        target_player_ids=[target.id, target.id],
    )

    assert result.get("error")
    assert [card.name for card in actor.hand] == ["離間"]
    assert [_conflicts(player) for player in game.players] == [0, 0, 0, 0]
    assert game.static_purchase_supply["內鬥"] == supply_before


def test_divide_rejects_more_than_three_targets_before_committing_card():
    game = _game(4)
    actor = game.players[0]

    result = game.play_card(
        0,
        mode="action",
        target_player_ids=[player.id for player in game.players[1:]] + ["unknown"],
    )

    assert result.get("error")
    assert [card.name for card in actor.hand] == ["離間"]
    assert [_conflicts(player) for player in game.players] == [0, 0, 0, 0]


@pytest.mark.parametrize(
    "selected_ids",
    [[], ["p1"], ["unknown"], [None]],
)
def test_divide_rejects_empty_self_unknown_or_malformed_targets(selected_ids):
    game = _game(4)
    actor = game.players[0]

    result = game.play_card(0, mode="action", target_player_ids=selected_ids)

    assert result.get("error")
    assert [card.name for card in actor.hand] == ["離間"]
    assert [_conflicts(player) for player in game.players] == [0, 0, 0, 0]


def test_divide_requires_explicit_selection_when_multiple_other_players_exist():
    game = _game(3)
    actor = game.players[0]

    result = game.play_card(0, mode="action")

    assert result.get("error")
    assert [card.name for card in actor.hand] == ["離間"]
    assert [_conflicts(player) for player in game.players] == [0, 0, 0]


def test_divide_two_player_game_uses_only_other_player_when_selection_is_omitted():
    game = _game(2)
    actor, target = game.players

    result = game.play_card(0, mode="action")

    assert result.get("success") is True
    assert _conflicts(actor) == 0
    assert _conflicts(target) == 1


def test_business_network_borrowed_divide_uses_selected_targets_and_returns_to_purchase_area():
    game = _game(4)
    actor, selected_a, unselected, selected_b = game.players
    actor.hand = [_card(game, "企業人脈")]
    game.purchase_area = [_card(game, "離間")]

    started = game.play_card(0, mode="action")
    assert started.get("pending_choice") is True
    assert game.pending_choice is not None
    assert game.pending_choice["choice_key"] == "use_purchase_area_card"

    resolved = game.resolve_pending_choice(
        actor.id,
        0,
        target_player_ids=[selected_a.id, selected_b.id],
    )

    assert resolved.get("success") is True
    assert [_conflicts(player) for player in game.players] == [0, 1, 0, 1]
    assert [card.name for card in actor.hand] == []
    assert [card.name for card in game.purchase_area] == ["離間"]
    assert [card.name for card in unselected.deck.discard_pile] == []
