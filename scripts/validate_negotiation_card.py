#!/usr/bin/env python3
"""Rule-level validator for 合作談判.

Canonical rule used by the live game:
Choose any one OTHER player, including an enemy. The actor and chosen target
each draw 1 card; no third player draws; the actor gains 2 propaganda.
Invalid, missing, or self targets must fail before any card/resource mutation.
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
EXPECTED_ERROR = "合作談判必須指定任意一名其他玩家"


def make_game():
    game = Game([
        ("actor", "Actor"),
        ("ally", "Ally"),
        ("enemy", "Enemy"),
        ("observer", "Observer"),
    ])
    actor, ally, enemy, observer = game.players
    actor.faction_id = "liberals"
    ally.faction_id = "hong_kong"
    enemy.faction_id = "red_army"
    observer.faction_id = "taiwan_green"
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.pending_choice = None
    game._player_effective_abilities = lambda player: []

    card_def = next(card for card in game.structured_cards if card["name"] == "合作談判")
    actor.hand = [Card("合作談判", card_def["type"], card_def.get("resources", {}))]
    actor.deck.draw_pile = [Card("actor_draw", "test", {})]
    ally.deck.draw_pile = [Card("ally_draw", "test", {})]
    enemy.deck.draw_pile = [Card("enemy_draw", "test", {})]
    observer.deck.draw_pile = [Card("observer_draw", "test", {})]
    for player in game.players:
        if player is not actor:
            player.hand = []
        player.deck.discard_pile = []
        player.resources = {"money": 0, "propaganda": 0}
    return game


def snapshot(game):
    return {
        "hands": {player.id: [card.name for card in player.hand] for player in game.players},
        "decks": {player.id: [card.name for card in player.deck.draw_pile] for player in game.players},
        "resources": {player.id: dict(player.resources) for player in game.players},
        "discard": {player.id: [card.name for card in player.deck.discard_pile] for player in game.players},
        "pending_choice": game.pending_choice,
        "action_log": list(game.action_log),
    }


def enemy_target_check():
    game = make_game()
    result = game.play_card(0, mode="action", target_player_id="enemy")
    details = {"result": result, **snapshot(game)}
    passed = (
        result.get("success") is True
        and details["hands"]["actor"] == ["actor_draw"]
        and details["hands"]["enemy"] == ["enemy_draw"]
        and details["hands"]["ally"] == []
        and details["hands"]["observer"] == []
        and details["decks"]["ally"] == ["ally_draw"]
        and details["decks"]["observer"] == ["observer_draw"]
        and details["resources"]["actor"] == {"money": 0, "propaganda": 2}
        and details["resources"]["enemy"] == {"money": 0, "propaganda": 0}
        and details["discard"]["actor"] == ["合作談判"]
    )
    return {
        "name": "enemy_is_a_legal_target_and_only_actor_and_enemy_draw",
        "passed": passed,
        "details": details,
    }


def invalid_target_check(name, target_player_id):
    game = make_game()
    before = snapshot(game)
    result = game.play_card(0, mode="action", target_player_id=target_player_id)
    after = snapshot(game)
    return {
        "name": name,
        "passed": result.get("error") == EXPECTED_ERROR and after == before,
        "details": {"target_player_id": target_player_id, "result": result, "before": before, "after": after},
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    checks = [
        enemy_target_check(),
        invalid_target_check("missing_target_is_rejected_without_mutation", None),
        invalid_target_check("self_target_is_rejected_without_mutation", "actor"),
        invalid_target_check("unknown_target_is_rejected_without_mutation", "missing-player"),
    ]
    summary = {
        "total": len(checks),
        "passed": sum(1 for check in checks if check["passed"]),
        "failed": sum(1 for check in checks if not check["passed"]),
    }
    report = {"summary": summary, "checks": checks}
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 合作談判規則驗證",
        "",
        f"- 結果：**{summary['passed']}/{summary['total']} passed**",
        "- 規則：可指定任意其他玩家，包含敵對玩家；行動者與指定者各抽1張，行動者獲得2宣傳。",
        "- Fail closed：缺少、自身或不存在的目標在卡牌／牌庫／資源變動前拒絕。",
        "",
        "## Checks",
    ]
    lines.extend(f"- {'PASS' if check['passed'] else 'FAIL'} `{check['name']}`" for check in checks)
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"summary": summary}, ensure_ascii=False))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
