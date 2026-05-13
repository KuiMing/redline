#!/usr/bin/env python3
"""Rule-level validator for 合作談判.

Raw card text:
選擇任1位玩家，您與該玩家各抽1張牌。您獲得2點宣傳。

This validator protects both behavior layers:
1. If no explicit target is provided, the engine uses a deterministic fallback
   target instead of incorrectly drawing all players.
2. In 4-player games, callers can explicitly choose the draw target.
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

RECORD_DIR = ROOT / "docs" / "records" / "shared-actions"
OUT_JSON = RECORD_DIR / "NEGOTIATION_CARD_VALIDATION.json"
OUT_MD = RECORD_DIR / "NEGOTIATION_CARD_VALIDATION.md"


def make_game(player_count=3):
    game = Game([(f"p{i}", f"P{i}") for i in range(1, player_count + 1)])
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    # Keep this focused on card text, not faction bonus side effects.
    game._player_effective_abilities = lambda player: []

    card_def = next(c for c in game.structured_cards if c["name"] == "合作談判")
    actor = game.players[0]
    actor.hand = [Card("合作談判", card_def["type"], card_def.get("resources", {}))]
    actor.deck.draw_pile = [Card("actor_bottom", "test", {}), Card("actor_draw", "test", {})]
    for idx, player in enumerate(game.players[1:], start=2):
        player.hand = []
        player.deck.draw_pile = [
            Card(f"p{idx}_bottom", "test", {}),
            Card(f"p{idx}_draw", "test", {}),
        ]
    for player in game.players:
        player.deck.discard_pile = []
        player.resources = {"money": 0, "propaganda": 0}
    return game


def snapshot(game):
    return {
        "hands": {p.id: [c.name for c in p.hand] for p in game.players},
        "decks": {p.id: [c.name for c in p.deck.draw_pile] for p in game.players},
        "resources": {p.id: dict(p.resources) for p in game.players},
        "discard": {p.id: [c.name for c in p.deck.discard_pile] for p in game.players},
        "action_log_tail": game.action_log[-8:],
    }


def run_default_target_validation():
    game = make_game(player_count=3)
    result = game.play_card(0, mode="action")
    details = {"result": result, **snapshot(game)}
    passed = (
        result.get("success") is True
        and details["hands"]["p1"] == ["actor_draw"]
        and details["hands"]["p2"] == ["p2_draw"]
        and details["hands"]["p3"] == []
        and details["decks"]["p3"] == ["p3_bottom", "p3_draw"]
        and details["resources"]["p1"] == {"money": 0, "propaganda": 2}
        and details["discard"]["p1"] == ["合作談判"]
    )
    return {
        "name": "negotiation_default_target_does_not_draw_all_players_and_grants_2_propaganda",
        "passed": passed,
        "details": details,
    }


def run_explicit_target_validation():
    game = make_game(player_count=4)
    target_id = "p4"
    result = game.play_card(0, mode="action", target_player_id=target_id)
    details = {"result": result, "target_player_id": target_id, **snapshot(game)}
    passed = (
        result.get("success") is True
        and details["hands"]["p1"] == ["actor_draw"]
        and details["hands"]["p2"] == []
        and details["hands"]["p3"] == []
        and details["hands"]["p4"] == ["p4_draw"]
        and details["decks"]["p2"] == ["p2_bottom", "p2_draw"]
        and details["decks"]["p3"] == ["p3_bottom", "p3_draw"]
        and details["resources"]["p1"] == {"money": 0, "propaganda": 2}
        and details["discard"]["p1"] == ["合作談判"]
    )
    return {
        "name": "negotiation_can_choose_draw_target_in_four_player_game",
        "passed": passed,
        "details": details,
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    checks = [run_default_target_validation(), run_explicit_target_validation()]
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
