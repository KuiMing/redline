#!/usr/bin/env python3
"""Rule-level validation for the 地下黨 card.

地下黨 source rule:
從購買區牌庫頂拿取3張牌，任選其中1張加入手牌，其餘移除。

Project rule for removed cards:
removed cards return to the purchase/supply area instead of vanishing.
"""

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase

JSON_OUT = ROOT / "UNDERGROUND_PARTY_VALIDATION.json"
MD_OUT = ROOT / "UNDERGROUND_PARTY_VALIDATION.md"


def card_names(cards):
    return [getattr(card, "name", str(card)) for card in cards]


def make_game():
    random.seed(20260510)
    game = Game([("p1", "player1"), ("p2", "player2")])
    player = game.players[0]
    player.faction_id = "tibet_dehradun"
    player.base = "德拉敦"
    player.organizations = {"德拉敦": 1}
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.pending_choice = None
    return game, player


def check_structured_effect_is_dedicated():
    game, _ = make_game()
    card_def = next(c for c in game.structured_cards if c.get("name") == "地下黨")
    effect_types = [e.get("type") for e in card_def.get("effect", [])]
    expected = ["choose_from_purchase_deck"]
    return {
        "name": "structured_effect_uses_purchase_deck_choice_not_discard_gain",
        "passed": effect_types == expected,
        "details": {
            "effect_types": effect_types,
            "expected": expected,
            "reason": "地下黨應是購買區牌庫選牌效果，不應殘留 gain_any_from_discard。",
        },
    }


def check_play_opens_choice_from_purchase_deck_only():
    game, player = make_game()
    card_def = next(c for c in game.structured_cards if c.get("name") == "地下黨")
    player.hand = [Card("地下黨", card_def["type"], card_def.get("resources", {}))]
    player.deck.discard_pile = [Card("不該取得的棄牌", "command", {})]
    player.resources = {"money": 0, "propaganda": 0}
    game.purchase_deck.draw_pile = [
        Card("底牌", "command", {}),
        Card("候選三", "command", {}),
        Card("候選二", "command", {}),
        Card("候選一", "command", {}),
    ]
    game.purchase_deck.discard_pile = []

    result = game.play_card(0, mode="action")
    state_choice = game.state().get("pending_choice")
    expected_choices = ["候選一", "候選二", "候選三"]
    return {
        "name": "play_reveals_top_three_purchase_deck_cards_and_not_player_discard",
        "passed": (
            result.get("success") is True
            and state_choice is not None
            and state_choice.get("cards") == expected_choices
            and "不該取得的棄牌" not in card_names(player.hand)
            and player.resources == {"money": 0, "propaganda": 0}
        ),
        "details": {
            "play_result": result,
            "pending_choice": state_choice,
            "expected_choices": expected_choices,
            "player_hand": card_names(player.hand),
            "player_discard": card_names(player.deck.discard_pile),
            "resources": dict(player.resources),
            "purchase_draw_remaining": card_names(game.purchase_deck.draw_pile),
        },
    }


def check_resolve_choice_keeps_one_and_returns_rest_to_purchase_area():
    game, player = make_game()
    card_def = next(c for c in game.structured_cards if c.get("name") == "地下黨")
    player.hand = [Card("地下黨", card_def["type"], card_def.get("resources", {}))]
    player.deck.discard_pile = []
    player.resources = {"money": 0, "propaganda": 0}
    game.purchase_deck.draw_pile = [
        Card("底牌", "command", {}),
        Card("候選三", "command", {}),
        Card("候選二", "command", {}),
        Card("候選一", "command", {}),
    ]
    game.purchase_deck.discard_pile = []

    game.play_card(0, mode="action")
    result = game.resolve_pending_choice(player.id, 1)
    removed_cards = result.get("removed_cards", []) if isinstance(result, dict) else []
    removed_zones = [r.get("zone") for r in removed_cards if isinstance(r, dict)]
    return {
        "name": "resolve_choice_adds_selected_to_hand_and_returns_unselected_to_purchase_deck_discard",
        "passed": (
            result.get("success") is True
            and result.get("chosen_card") == "候選二"
            and "候選二" in card_names(player.hand)
            and set(card_names(game.purchase_deck.discard_pile)) == {"候選一", "候選三"}
            and set(removed_zones) == {"deck_discard"}
            and game.pending_choice is None
        ),
        "details": {
            "resolve_result": result,
            "player_hand": card_names(player.hand),
            "player_discard": card_names(player.deck.discard_pile),
            "purchase_draw_remaining": card_names(game.purchase_deck.draw_pile),
            "purchase_discard": card_names(game.purchase_deck.discard_pile),
            "removed_zones": removed_zones,
            "pending_choice_after": game.pending_choice,
        },
    }


def write_report(results):
    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
    }
    payload = {"summary": summary, "results": results}
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 地下黨規則驗證", "", f"- total: {summary['total']}", f"- passed: {summary['passed']}", f"- failed: {summary['failed']}", ""]
    for r in results:
        lines.append(f"## {'PASS' if r['passed'] else 'FAIL'} — {r['name']}")
        for key, value in r.get("details", {}).items():
            lines.append(f"- {key}: {value}")
        lines.append("")
    MD_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"summary": summary}, ensure_ascii=False))
    return summary["failed"] == 0


def main():
    results = [
        check_structured_effect_is_dedicated(),
        check_play_opens_choice_from_purchase_deck_only(),
        check_resolve_choice_keeps_one_and_returns_rest_to_purchase_area(),
    ]
    return 0 if write_report(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
