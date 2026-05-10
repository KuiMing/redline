#!/usr/bin/env python3
"""Rule-level validator for 合作談判.

Raw card text:
選擇任1位玩家，您與該玩家各抽1張牌。您獲得2點宣傳。

Current MVP target semantics for this validator: when no explicit UI target is
provided, the engine should choose the first other player as a deterministic
default. The important rule being protected is that the effect is not a global
all-player draw and that the actor gains the printed-in-effect 2 propaganda in
action mode.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase

OUT_JSON = ROOT / "NEGOTIATION_CARD_VALIDATION.json"
OUT_MD = ROOT / "NEGOTIATION_CARD_VALIDATION.md"


def make_game():
    game = Game([("p1", "P1"), ("p2", "P2"), ("p3", "P3")])
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    # Keep this focused on card text, not faction bonus side effects.
    game._player_effective_abilities = lambda player: []

    actor, target, third = game.players
    card_def = next(c for c in game.structured_cards if c["name"] == "合作談判")
    actor.hand = [Card("合作談判", card_def["type"], card_def.get("resources", {}))]
    actor.deck.draw_pile = [Card("actor_bottom", "test", {}), Card("actor_draw", "test", {})]
    target.hand = []
    target.deck.draw_pile = [Card("target_bottom", "test", {}), Card("target_draw", "test", {})]
    third.hand = []
    third.deck.draw_pile = [Card("third_bottom", "test", {}), Card("third_should_not_draw", "test", {})]
    for player in game.players:
        player.deck.discard_pile = []
        player.resources = {"money": 0, "propaganda": 0}
    return game


def run_validation():
    game = make_game()
    actor, target, third = game.players
    result = game.play_card(0, mode="action")
    details = {
        "result": result,
        "actor_hand": [c.name for c in actor.hand],
        "target_hand": [c.name for c in target.hand],
        "third_hand": [c.name for c in third.hand],
        "actor_deck": [c.name for c in actor.deck.draw_pile],
        "target_deck": [c.name for c in target.deck.draw_pile],
        "third_deck": [c.name for c in third.deck.draw_pile],
        "actor_resources": dict(actor.resources),
        "actor_discard": [c.name for c in actor.deck.discard_pile],
        "action_log_tail": game.action_log[-8:],
    }
    passed = (
        result.get("success") is True
        and details["actor_hand"] == ["actor_draw"]
        and details["target_hand"] == ["target_draw"]
        and details["third_hand"] == []
        and details["third_deck"] == ["third_bottom", "third_should_not_draw"]
        and details["actor_resources"] == {"money": 0, "propaganda": 2}
        and details["actor_discard"] == ["合作談判"]
    )
    return {
        "name": "negotiation_draws_actor_and_one_target_only_and_grants_2_propaganda",
        "passed": passed,
        "details": details,
    }


def main():
    checks = [run_validation()]
    summary = {
        "total": len(checks),
        "passed": sum(1 for c in checks if c["passed"]),
        "failed": sum(1 for c in checks if not c["passed"]),
    }
    report = {"summary": summary, "checks": checks}
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Negotiation Card Validation",
        "",
        f"- total: {summary['total']}",
        f"- passed: {summary['passed']}",
        f"- failed: {summary['failed']}",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.extend([
            f"## {status} — {check['name']}",
            "",
            "```json",
            json.dumps(check["details"], ensure_ascii=False, indent=2),
            "```",
            "",
        ])
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"summary": summary}, ensure_ascii=False))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
