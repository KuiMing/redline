#!/usr/bin/env python3
"""Validate first P1 card-effect audit findings.

Focus: card effects where raw card text says "抽1張牌" but structured/runtime
currently does not draw. These are rule-level checks, not smoke tests.
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

OUT_JSON = ROOT / "CARD_EFFECT_AUDIT_P1_VALIDATION.json"
OUT_MD = ROOT / "CARD_EFFECT_AUDIT_P1_VALIDATION.md"


def make_game(card_name: str):
    game = Game([("p1", "P1"), ("p2", "P2")])
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    # Keep this validator focused on the card text, not faction first-card bonuses.
    game._player_effective_abilities = lambda player: []

    player = game.players[0]
    card_def = next(c for c in game.structured_cards if c["name"] == card_name)
    player.hand = [Card(card_name, card_def["type"], card_def.get("resources", {}))]
    player.deck.draw_pile = [
        Card("牌庫底", "test", {}),
        Card("應抽到的牌", "test", {}),
    ]
    player.deck.discard_pile = []
    player.resources = {"money": 0, "propaganda": 0}
    return game, player


def run_case(card_name: str, extra_assert=None):
    game, player = make_game(card_name)
    before_deck = [c.name for c in player.deck.draw_pile]
    result = game.play_card(0, mode="action")
    hand_names = [c.name for c in player.hand]
    after_deck = [c.name for c in player.deck.draw_pile]
    discard_names = [c.name for c in player.deck.discard_pile]
    passed = (
        result.get("success") is True
        and "應抽到的牌" in hand_names
        and after_deck == ["牌庫底"]
    )
    details = {
        "result": result,
        "before_deck": before_deck,
        "hand_after": hand_names,
        "deck_after": after_deck,
        "discard_after": discard_names,
        "resources_after": dict(player.resources),
        "build_range_bonus": getattr(player, "build_range_bonus", 0),
        "action_log_tail": game.action_log[-6:],
    }
    if extra_assert:
        extra_ok, extra_details = extra_assert(game, player)
        passed = passed and extra_ok
        details.update(extra_details)
    return {
        "name": f"{card_name}_action_mode_draws_one_card_from_raw_text",
        "passed": passed,
        "details": details,
    }


def assert_thought_building(game, player):
    return getattr(player, "build_range_bonus", 0) == 1, {
        "expected_build_range_bonus": 1,
    }


def main():
    checks = [
        run_case("思想建設", assert_thought_building),
        run_case("誘導虛耗"),
    ]
    summary = {
        "total": len(checks),
        "passed": sum(1 for c in checks if c["passed"]),
        "failed": sum(1 for c in checks if not c["passed"]),
    }
    report = {"summary": summary, "checks": checks}
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Card Effect Audit P1 Validation",
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
