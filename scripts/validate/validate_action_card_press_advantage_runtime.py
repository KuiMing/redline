#!/usr/bin/env python3
"""Runtime validation for Redline 乘勝追擊.

Covers the discard-pile pick flow with before / pending-choice / after state
snapshots and action-log evidence. Reports are written under docs/records.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card  # noqa: E402
from server.game import Game, GamePhase, TurnPhase  # noqa: E402

RECORD_DIR = ROOT / "docs" / "records" / "action-cards"
JSON_PATH = RECORD_DIR / "ACTION_CARD_PRESS_ADVANTAGE_RUNTIME_VALIDATION.json"
MD_PATH = RECORD_DIR / "ACTION_CARD_PRESS_ADVANTAGE_RUNTIME_VALIDATION.md"


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
    player = game.players[0]
    pending = game.pending_choice
    pending_summary = None
    if pending:
        pending_summary = {
            "type": pending.get("type"),
            "choice_key": pending.get("choice_key"),
            "player_id": pending.get("player_id"),
            "source_name": pending.get("source_name"),
            "max_cost": pending.get("max_cost"),
            "cards": names(pending.get("cards") or []),
            "prompt": pending.get("prompt"),
        }
    return {
        "hand": names(player.hand),
        "discard_pile": names(player.deck.discard_pile),
        "draw_pile": names(player.deck.draw_pile),
        "resources": dict(player.resources),
        "turn_log": dict(game.turn_log),
        "pending_choice": pending_summary,
        "action_log_tail": list(game.action_log[-8:]),
    }


def assert_condition(condition: bool, message: str, failures: List[str]) -> None:
    if not condition:
        failures.append(message)


def run_scenario() -> Dict[str, Any]:
    game = make_game()
    player = game.players[0]
    player.hand = [action_card(game, "乘勝追擊")]
    player.deck.discard_pile = [
        action_card(game, "宣傳家"),      # total cost 3: eligible
        action_card(game, "合作談判"),    # total cost 4: ineligible
        action_card(game, "走漏風聲"),    # total cost 2: eligible; selected below
    ]

    before = snapshot(game)
    play_result = game.play_card(0, mode="action")
    pending_state = snapshot(game)
    resolve_result = game.resolve_pending_choice(player.id, 1)
    after = snapshot(game)

    failures: List[str] = []
    assert_condition(play_result.get("success") is True, f"play_card did not succeed: {play_result}", failures)
    assert_condition(play_result.get("pending_choice") is True, "play_card did not return pending_choice", failures)

    pending = pending_state.get("pending_choice") or {}
    assert_condition(pending.get("type") == "card_choice", f"wrong pending type: {pending}", failures)
    assert_condition(pending.get("choice_key") == "gain_from_discard", f"wrong choice key: {pending}", failures)
    assert_condition(pending.get("source_name") == "乘勝追擊", f"wrong source name: {pending}", failures)
    assert_condition(pending.get("max_cost") == 3, f"wrong max_cost: {pending}", failures)
    assert_condition(pending.get("cards") == ["宣傳家", "走漏風聲"], f"eligible cards mismatch: {pending.get('cards')}", failures)
    assert_condition("合作談判" not in (pending.get("cards") or []), "ineligible total-cost-4 card was offered", failures)
    assert_condition(
        pending_state["discard_pile"] == ["宣傳家", "合作談判", "走漏風聲", "乘勝追擊"],
        f"discard pile should still contain candidates plus played card before resolution: {pending_state['discard_pile']}",
        failures,
    )

    assert_condition(resolve_result.get("success") is True, f"resolve did not succeed: {resolve_result}", failures)
    assert_condition(resolve_result.get("chosen_card") == "走漏風聲", f"wrong chosen card: {resolve_result}", failures)
    assert_condition(after["hand"] == ["走漏風聲"], f"hand after mismatch: {after['hand']}", failures)
    assert_condition(after["discard_pile"] == ["宣傳家", "合作談判", "乘勝追擊"], f"discard after mismatch: {after['discard_pile']}", failures)
    assert_condition(after["pending_choice"] is None, f"pending choice was not cleared: {after['pending_choice']}", failures)
    assert_condition(
        any("gained 走漏風聲 from discard via 乘勝追擊" in line for line in after["action_log_tail"]),
        f"missing gain action log: {after['action_log_tail']}",
        failures,
    )

    return {
        "card_name": "乘勝追擊",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "play_result": play_result,
        "resolve_result": resolve_result,
        "before": before,
        "pending": pending_state,
        "after": after,
    }


def write_reports(result: Dict[str, Any]) -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": 1,
        "passed": 1 if result["status"] == "passed" else 0,
        "failed": 0 if result["status"] == "passed" else 1,
        "results": [result],
    }
    JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Action Card Press Advantage Runtime Validation",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        f"Summary: {summary['passed']} passed / {summary['failed']} failed / {summary['total']} total.",
        "",
        "## Scope",
        "- 乘勝追擊：從己方棄牌堆任選 1 張總費用 3 點以下的牌加入手牌。",
        "- 總費用以資金費用 + 宣傳費用計算；本驗證同時放入總費用 3、2 的 eligible 卡，以及總費用 4 的 ineligible 卡。",
        "- 驗證 pending choice 候選清單、選牌解析後的手牌／棄牌堆、以及 action log。",
        "",
        f"## {result['card_name']} — {result['status']}",
        "",
        f"- Play result: `{result['play_result']}`",
        f"- Resolve result: `{result['resolve_result']}`",
        f"- Before: hand `{result['before']['hand']}`, discard `{result['before']['discard_pile']}`",
        f"- Pending: `{result['pending']['pending_choice']}`, discard `{result['pending']['discard_pile']}`",
        f"- After: hand `{result['after']['hand']}`, discard `{result['after']['discard_pile']}`",
        f"- Action log tail: `{result['after']['action_log_tail']}`",
    ]
    if result["failures"]:
        lines.append(f"- Failures: `{result['failures']}`")
    lines.append("")
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    result = run_scenario()
    write_reports(result)
    passed = 1 if result["status"] == "passed" else 0
    failed = 1 - passed
    print(f"Action card press-advantage runtime validation: {passed} passed / {failed} failed")
    print(f"Wrote {JSON_PATH.relative_to(ROOT)}")
    print(f"Wrote {MD_PATH.relative_to(ROOT)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
