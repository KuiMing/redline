#!/usr/bin/env python3
"""Validate Redline card-use mode rules.

Rule: every hand card is played in exactly one mode:
- resource mode: gain printed money/propaganda only
- action mode: execute card effect only

Unspent turn resources reset at end of turn.
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

OUT_JSON = ROOT / "CARD_USE_MODES_VALIDATION.json"
OUT_MD = ROOT / "CARD_USE_MODES_VALIDATION.md"


def names(cards):
    return [getattr(c, "name", str(c)) for c in cards]


def make_game():
    random.seed(20260510)
    game = Game([("p1", "actor"), ("p2", "other")])
    player = game.players[0]
    other = game.players[1]
    player.faction_id = "tibet_dehradun"
    player.base = "德拉敦"
    player.organizations = {"德拉敦": 1}
    player.resources = {"money": 0, "propaganda": 0}
    player.moves_left = 0
    player.deck.draw_pile = []
    player.deck.discard_pile = []
    other.faction_id = "red_army"
    other.base = "北京"
    other.organizations = {"北京": 1}
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.pending_choice = None
    return game, player


def structured_card(game, card_name):
    row = next(c for c in game.structured_cards if c.get("name") == card_name)
    return Card(row["name"], row["type"], row.get("resources", {}))


def check(label, passed, details):
    return {"name": label, "passed": bool(passed), "details": details}


def check_resource_mode_grants_only_printed_resources():
    game, player = make_game()
    player.hand = [structured_card(game, "地下黨")]
    game.purchase_deck.draw_pile = [Card("候選三", "command", {}), Card("候選二", "command", {}), Card("候選一", "command", {})]
    before_draw = names(game.purchase_deck.draw_pile)

    result = game.play_card(0, mode="resource")

    return check(
        "resource_mode_grants_printed_resources_without_action_effect",
        result.get("success") is True
        and player.resources == {"money": 1, "propaganda": 2}
        and game.pending_choice is None
        and names(game.purchase_deck.draw_pile) == before_draw
        and names(player.deck.discard_pile).count("地下黨") == 1,
        {
            "result": result,
            "resources": dict(player.resources),
            "pending_choice": game.pending_choice,
            "purchase_draw_before": before_draw,
            "purchase_draw_after": names(game.purchase_deck.draw_pile),
            "discard": names(player.deck.discard_pile),
        },
    )


def check_action_mode_executes_only_effect_without_printed_resources():
    game, player = make_game()
    player.hand = [structured_card(game, "地下黨")]
    game.purchase_deck.draw_pile = [
        Card("底牌", "command", {}),
        Card("候選三", "command", {}),
        Card("候選二", "command", {}),
        Card("候選一", "command", {}),
    ]

    result = game.play_card(0, mode="action")
    pending = game.state().get("pending_choice")

    return check(
        "action_mode_executes_effect_without_printed_resources",
        result.get("success") is True
        and player.resources == {"money": 0, "propaganda": 0}
        and pending is not None
        and pending.get("cards") == ["候選一", "候選二", "候選三"],
        {
            "result": result,
            "resources": dict(player.resources),
            "pending_choice": pending,
            "purchase_draw_after": names(game.purchase_deck.draw_pile),
            "discard": names(player.deck.discard_pile),
        },
    )


def check_default_play_requires_explicit_mode():
    game, player = make_game()
    player.hand = [structured_card(game, "領導")]
    player.deck.draw_pile = [Card("補牌", "command", {})]

    result = game.play_card(0)

    return check(
        "play_card_requires_explicit_resource_or_action_mode",
        result.get("error") == "Card play mode must be resource or action"
        and names(player.hand) == ["領導"]
        and player.resources == {"money": 0, "propaganda": 0}
        and names(player.deck.draw_pile) == ["補牌"],
        {
            "result": result,
            "hand": names(player.hand),
            "resources": dict(player.resources),
            "draw_pile": names(player.deck.draw_pile),
        },
    )


def check_resources_clear_at_end_turn():
    game, player = make_game()
    player.hand = []
    player.resources = {"money": 3, "propaganda": 4}
    player.moves_left = 2
    game.advance_turn_phase()  # ACTION -> END
    game.advance_turn_phase()  # END -> next player's EVENT

    return check(
        "unspent_resources_clear_at_end_turn",
        player.resources == {"money": 0, "propaganda": 0} and player.moves_left == 0,
        {
            "resources_after_end_turn": dict(player.resources),
            "moves_left_after_end_turn": player.moves_left,
            "turn_phase": getattr(game.turn_phase, "value", str(game.turn_phase)),
            "current_player": game.current_player().name,
        },
    )


def write_report(results):
    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
    }
    payload = {"summary": summary, "results": results}
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 卡牌用途二選一規則驗證", "", f"- total: {summary['total']}", f"- passed: {summary['passed']}", f"- failed: {summary['failed']}", ""]
    for r in results:
        lines.append(f"## {'PASS' if r['passed'] else 'FAIL'} — {r['name']}")
        for k, v in r["details"].items():
            lines.append(f"- {k}: {v}")
        lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"summary": summary}, ensure_ascii=False))
    return summary["failed"] == 0


def main():
    results = [
        check_resource_mode_grants_only_printed_resources(),
        check_action_mode_executes_only_effect_without_printed_resources(),
        check_default_play_requires_explicit_mode(),
        check_resources_clear_at_end_turn(),
    ]
    return 0 if write_report(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
