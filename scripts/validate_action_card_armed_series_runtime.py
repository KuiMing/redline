#!/usr/bin/env python3
"""Runtime validation for Redline armed-series action cards.

Covers 武裝者、武裝小隊、武裝集團 with before / pending-choice / after
state snapshots and action-log evidence. Reports are written under docs/records.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card  # noqa: E402
from server.game import Game, GamePhase, TurnPhase  # noqa: E402

RECORD_DIR = ROOT / "docs" / "records" / "action-cards"
JSON_PATH = RECORD_DIR / "ACTION_CARD_ARMED_SERIES_RUNTIME_VALIDATION.json"
MD_PATH = RECORD_DIR / "ACTION_CARD_ARMED_SERIES_RUNTIME_VALIDATION.md"


def names(cards: List[Any]) -> List[str]:
    return [getattr(card, "name", str(card)) for card in cards]


def make_game() -> Game:
    game = Game([("p1", "P1"), ("p2", "P2")])
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.current_player_index = 0
    game.pending_base_choices = {}
    game.players[0].faction_id = "red_army"
    return game


def action_card(game: Game, name: str) -> Card:
    card_data = next(card for card in game.structured_cards if card["name"] == name)
    return Card(card_data["name"], card_data["type"], card_data.get("resources", {}))


def snapshot(game: Game) -> Dict[str, Any]:
    p1, p2 = game.players
    pending = game.pending_choice
    pending_summary = None
    if pending:
        pending_summary = {
            "type": pending.get("type"),
            "choice_key": pending.get("choice_key"),
            "player_id": pending.get("player_id"),
            "count": pending.get("count"),
            "cards": names(pending.get("cards") or []),
            "prompt": pending.get("prompt"),
        }
    return {
        "p1_hand": names(p1.hand),
        "p1_draw_pile": names(p1.deck.draw_pile),
        "p1_discard_pile": names(p1.deck.discard_pile),
        "p1_organizations": dict(p1.organizations),
        "p2_hand": names(p2.hand),
        "p2_discard_pile": names(p2.deck.discard_pile),
        "p2_organizations": dict(p2.organizations),
        "turn_log": dict(game.turn_log),
        "pending_choice": pending_summary,
        "action_log_tail": list(game.action_log[-8:]),
    }


def assert_condition(condition: bool, message: str, failures: List[str]) -> None:
    if not condition:
        failures.append(message)


def run_scenario(config: Dict[str, Any]) -> Dict[str, Any]:
    game = make_game()
    p1, p2 = game.players
    card_name = config["card_name"]
    p1.hand = [action_card(game, card_name)]
    p1.organizations = {"北京": 1}
    p2.organizations = {"天津": 1}
    p2.hand = [Card(name, "command", {}) for name in config["target_hand"]]
    p1.deck.draw_pile = [Card(name, "command", {}) for name in config.get("actor_draw_pile", [])]

    before = snapshot(game)
    play_result = game.play_card(0, mode="action", target_player_id=p2.id)
    pending_state = snapshot(game)
    resolve_result = game.resolve_pending_choice(p2.id, config["choice_indices"])
    after = snapshot(game)

    failures: List[str] = []
    assert_condition(play_result.get("success") is True, f"{card_name}: play_card did not succeed: {play_result}", failures)
    assert_condition(play_result.get("pending_choice") is True, f"{card_name}: play_card did not return pending_choice", failures)
    pending = pending_state.get("pending_choice") or {}
    assert_condition(pending.get("choice_key") == "armed_target_discard", f"{card_name}: wrong pending choice key {pending}", failures)
    assert_condition(pending.get("type") == config["pending_type"], f"{card_name}: wrong pending type {pending.get('type')}", failures)
    if config.get("pending_count") is not None:
        assert_condition(pending.get("count") == config["pending_count"], f"{card_name}: wrong pending count {pending.get('count')}", failures)
    assert_condition(pending.get("cards") == config["target_hand"], f"{card_name}: pending cards mismatch {pending.get('cards')}", failures)
    assert_condition(resolve_result.get("success") is True, f"{card_name}: resolve did not succeed: {resolve_result}", failures)
    assert_condition(after["p2_hand"] == config["expected_target_hand_after"], f"{card_name}: target hand after mismatch {after['p2_hand']}", failures)
    assert_condition(after["p2_discard_pile"] == config["expected_target_discard_after"], f"{card_name}: target discard after mismatch {after['p2_discard_pile']}", failures)
    assert_condition(after["turn_log"].get("successful_discard") is True, f"{card_name}: successful_discard was not set", failures)
    for expected in config.get("expected_actor_hand_contains", []):
        assert_condition(expected in after["p1_hand"], f"{card_name}: actor hand missing {expected}: {after['p1_hand']}", failures)
    for expected in config["expected_log_contains"]:
        assert_condition(any(expected in line for line in after["action_log_tail"]), f"{card_name}: missing log text {expected!r}", failures)

    return {
        "card_name": card_name,
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "play_result": play_result,
        "resolve_result": resolve_result,
        "before": before,
        "pending": pending_state,
        "after": after,
    }


def write_reports(results: List[Dict[str, Any]]) -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(results),
        "passed": sum(1 for result in results if result["status"] == "passed"),
        "failed": sum(1 for result in results if result["status"] != "passed"),
        "results": results,
    }
    JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Action Card Armed Series Runtime Validation",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        f"Summary: {summary['passed']} passed / {summary['failed']} failed / {summary['total']} total.",
        "",
        "## Scope",
        "- 武裝者：指定 1 格內有組織的對手，目標玩家自選棄 1 張牌。",
        "- 武裝小隊：指定 1 格內有組織的對手，目標玩家自選棄 2 張牌。",
        "- 武裝集團：指定 1 格內有組織的對手，目標玩家自選棄 2 張牌；成功棄牌後，出牌者抽 1 張牌。",
        "",
    ]
    for result in results:
        lines.extend([
            f"## {result['card_name']} — {result['status']}",
            "",
            f"- Play result: `{result['play_result']}`",
            f"- Resolve result: `{result['resolve_result']}`",
            f"- Before: P2 hand `{result['before']['p2_hand']}`, P2 discard `{result['before']['p2_discard_pile']}`, P1 hand `{result['before']['p1_hand']}`",
            f"- Pending: `{result['pending']['pending_choice']}`",
            f"- After: P2 hand `{result['after']['p2_hand']}`, P2 discard `{result['after']['p2_discard_pile']}`, P1 hand `{result['after']['p1_hand']}`, turn_log `{result['after']['turn_log']}`",
            f"- Action log tail: `{result['after']['action_log_tail']}`",
        ])
        if result["failures"]:
            lines.append(f"- Failures: `{result['failures']}`")
        lines.append("")
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    scenarios = [
        {
            "card_name": "武裝者",
            "target_hand": ["Enemy1", "Enemy2"],
            "choice_indices": 0,
            "pending_type": "card_choice",
            "pending_count": None,
            "expected_target_hand_after": ["Enemy2"],
            "expected_target_discard_after": ["Enemy1"],
            "expected_log_contains": ["P1 used 武裝者 to force P2 to discard Enemy1"],
        },
        {
            "card_name": "武裝小隊",
            "target_hand": ["Enemy1", "Enemy2", "Enemy3"],
            "choice_indices": [0, 2],
            "pending_type": "multi_card_choice",
            "pending_count": 2,
            "expected_target_hand_after": ["Enemy2"],
            "expected_target_discard_after": ["Enemy1", "Enemy3"],
            "expected_log_contains": ["P1 used 武裝小隊 to force P2 to discard 2 card(s)"],
        },
        {
            "card_name": "武裝集團",
            "target_hand": ["Enemy1", "Enemy2"],
            "actor_draw_pile": ["RewardDraw"],
            "choice_indices": [0, 1],
            "pending_type": "multi_card_choice",
            "pending_count": 2,
            "expected_target_hand_after": [],
            "expected_target_discard_after": ["Enemy1", "Enemy2"],
            "expected_actor_hand_contains": ["RewardDraw"],
            "expected_log_contains": ["P1 used 武裝集團 to force P2 to discard 2 card(s)"],
        },
    ]
    results = [run_scenario(scenario) for scenario in scenarios]
    write_reports(results)
    passed = sum(1 for result in results if result["status"] == "passed")
    failed = len(results) - passed
    print(f"Action card armed-series runtime validation: {passed} passed / {failed} failed")
    print(f"Wrote {JSON_PATH.relative_to(ROOT)}")
    print(f"Wrote {MD_PATH.relative_to(ROOT)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
