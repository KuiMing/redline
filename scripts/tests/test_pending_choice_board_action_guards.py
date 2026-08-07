from copy import deepcopy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Card, Deck, Game, TurnPhase


PENDING_BOARD_ACTION_ERROR = "請先完成目前的選擇"


def make_game():
    game = Game([("actor", "actor"), ("defender", "defender")])
    actor, defender = game.players
    actor.faction_id = "taiwan_green"
    actor.base = "臺北"
    defender.faction_id = "red_army"
    defender.base = "北京"
    actor.deck = Deck([])
    defender.deck = Deck([])
    actor.organizations = {"臺北": 1, "桃園": 1}
    defender.organizations = {"北京": 1, "上海": 1}
    actor.moves_left = 3
    game.players = [actor, defender]
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.current_event = {
        "id": "pending-guard-noop",
        "name": "守門測試事件",
        "type": "noop",
        "trigger": {},
        "success_effect": {"type": "none"},
        "failure_effect": {"type": "none"},
    }
    game.event_progress = {"count": 0, "required": 0, "succeeded": True, "settled": True, "status": "idle"}
    return game, actor, defender


def snapshot(game, actor, defender):
    pending = game.pending_choice or {}
    pending_projection = {
        "type": pending.get("type"),
        "choice_key": pending.get("choice_key"),
        "player_id": pending.get("player_id"),
        "prompt": pending.get("prompt"),
        "cards": [getattr(card, "name", str(card)) for card in pending.get("cards", [])],
    } if pending else None
    return {
        "actor_orgs": deepcopy(actor.organizations),
        "defender_orgs": deepcopy(defender.organizations),
        "moves": actor.moves_left,
        "resources": deepcopy(actor.resources),
        "actor_base": actor.base,
        "defender_base": defender.base,
        "pending_choice": pending_projection,
        "action_log": list(game.action_log),
    }


def test_unrelated_board_actions_are_blocked_while_a_card_choice_is_pending():
    game, actor, defender = make_game()
    legal_moves = game._legal_organization_moves()
    origin = next(town for town in legal_moves if town != actor.base)
    move = next(
        (origin, option["town"], mode)
        for mode, options in legal_moves[origin].items()
        for option in options
    )
    game.pending_choice = {
        "type": "card_choice",
        "choice_key": "recruit_talent",
        "player_id": actor.id,
        "cards": [Card("候選牌", "command", {})],
        "prompt": "網羅人才：請選擇一張牌。",
    }
    before = snapshot(game, actor, defender)

    results = {
        "direct_build": game.build_organization("臺北"),
        "supported_build": game.build_organization_with_support("臺北", "桃園"),
        "move": game.move_organization(*move),
        "dissolve": game.dissolve_organization(actor, defender, "上海", source="faction_action"),
    }

    original_faction = actor.faction_id
    actor.faction_id = "hong_kong"
    relocate = game.relocate_hong_kong_base(actor.id, "倫敦")
    actor.faction_id = original_faction
    results["relocate_base"] = relocate

    assert {name: result.get("error") for name, result in results.items()} == {
        "direct_build": PENDING_BOARD_ACTION_ERROR,
        "supported_build": PENDING_BOARD_ACTION_ERROR,
        "move": PENDING_BOARD_ACTION_ERROR,
        "dissolve": PENDING_BOARD_ACTION_ERROR,
        "relocate_base": PENDING_BOARD_ACTION_ERROR,
    }
    assert snapshot(game, actor, defender) == before


def test_matching_pending_build_still_resolves_through_build_entrypoint():
    game, actor, _ = make_game()
    effect = {"type": "build", "range": "ignore_distance", "count": 1}
    towns = game._card_build_town_choices(actor, effect)
    assert towns
    game._set_pending_town_choice(
        actor,
        "card_build_organization",
        towns,
        "選擇要建立組織的城鎮。",
        source_name="宣傳家",
        count=1,
        context={"effect": effect},
    )
    target = game.pending_choice["towns"][0]["town"]

    result = game.build_organization(target)

    assert result.get("success") is True
    assert actor.organizations.get(target) == 1
    assert game.pending_choice is None
