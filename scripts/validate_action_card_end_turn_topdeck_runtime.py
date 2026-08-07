#!/usr/bin/env python3
"""Runtime validation for the 行動預告 / 行動募資 topdeck-right flow.

2026-08-07 使用者要求改版：打出這兩張卡時立刻拿到宣傳/資金（本回合可花用），頂牌對象
改成玩家主動觸發的獨立動作（use_pending_topdeck_right），可以在購買後、回合結束前的
任何時間點使用；同一回合打出多張各自累積成獨立的頂牌權利，可分次使用；沒手動用掉的
權利在按下「結束回合」時自動逐一跳出選擇處理，沒有候選牌時則作廢、不卡住回合。
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
JSON_PATH = RECORD_DIR / "ACTION_CARD_END_TURN_TOPDECK_RUNTIME_VALIDATION.json"
MD_PATH = RECORD_DIR / "ACTION_CARD_END_TURN_TOPDECK_RUNTIME_VALIDATION.md"


def names(cards: List[Any]) -> List[str]:
    result = []
    for c in cards:
        if isinstance(c, dict) and 'card' in c:
            c = c['card']
        result.append(getattr(c, "name", str(c)))
    return result


def pin_noop_event(g: Game) -> Game:
    # Game 初始化會隨機抽該輪事件；抽到互動型事件會插入自己的 pending choice，
    # 污染這裡只想驗證頂牌流程的測試。固定換成無效果的歲月靜好，與事件運氣脫鉤。
    g.current_event = dict(g._event_by_name('歲月靜好'))
    g.event_progress = {"count": 0, "required": 0, "succeeded": True, "settled": True, "status": "idle"}
    g.event_modifiers = []
    g.pending_choice = None
    return g


def make_game(turn_phase: str = TurnPhase.ACTION) -> Game:
    g = Game([("p1", "P1"), ("p2", "P2")])
    g.game_phase = GamePhase.MAIN
    g.turn_phase = turn_phase
    g.current_player_index = 0
    g.pending_base_choices = {}
    g.players[0].faction_id = "red_army"
    return pin_noop_event(g)


def action_card(g: Game, name: str) -> Card:
    c = next(c for c in g.structured_cards if c["name"] == name)
    return Card(c["name"], c["type"], c.get("resources", {}))


def serializable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: serializable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serializable(v) for v in value]
    if hasattr(value, 'name'):
        return getattr(value, 'name', str(value))
    return value


def snapshot(g: Game, player_index: int = 0) -> Dict[str, Any]:
    p = g.players[player_index]
    pending = g.pending_choice
    pending_summary = None
    if pending:
        pending_summary = {
            "type": pending.get("type"),
            "choice_key": pending.get("choice_key"),
            "player_id": pending.get("player_id"),
            "prompt": pending.get("prompt"),
            "cards": names(pending.get("cards") or []),
        }
    return {
        "turn_phase": g.turn_phase,
        "current_player_index": g.current_player_index,
        "hand": names(p.hand),
        "draw_pile": names(p.deck.draw_pile),
        "discard_pile": names(p.deck.discard_pile),
        "resources": dict(p.resources),
        "pending_topdeck_uses": g.turn_log.get("pending_topdeck_uses", 0),
        "pending_choice": pending_summary,
        "action_log_tail": list(g.action_log[-8:]),
    }


def run_play_grants_resource_and_banks_right() -> Dict[str, Any]:
    """打出行動預告：宣傳立刻到手、頂牌權利銀行化，沒有 pending choice。"""
    g = make_game()
    p = g.current_player()
    p.hand = [action_card(g, "行動預告")]
    p.resources = {"money": 0, "propaganda": 0}

    before = snapshot(g)
    result = g.play_card(0, mode="action")
    after = snapshot(g)

    failures: List[str] = []
    if not result.get("success") or result.get("pending_choice"):
        failures.append(f"play_card did not succeed cleanly: {result}")
    if after["resources"].get("propaganda") != 1:
        failures.append(f"propaganda not granted immediately: {after['resources']}")
    if after["pending_topdeck_uses"] != 1:
        failures.append(f"topdeck right not banked: {after['pending_topdeck_uses']}")
    if after["pending_choice"] is not None:
        failures.append("unexpected pending choice right after playing the card")

    return {
        "name": "play_announce_action_grants_propaganda_and_banks_right",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "before": before,
        "after": after,
    }


def run_manual_use_with_single_candidate() -> Dict[str, Any]:
    """打出後買 1 張牌，主動點頂牌：單一候選自動置頂，不開選擇視窗。"""
    g = make_game()
    p = g.current_player()
    p.hand = [action_card(g, "行動募資")]
    p.resources = {"money": 0, "propaganda": 0}
    g.play_card(0, mode="action")

    bought = Card("PurchasedCard", "command", {})
    p.deck.discard_pile = [bought]
    g.turn_log["purchased_cards_this_turn"] = [bought]

    before = snapshot(g)
    result = g.use_pending_topdeck_right()
    after = snapshot(g)

    failures: List[str] = []
    if not result.get("success") or result.get("pending_choice"):
        failures.append(f"manual use did not auto-resolve: {result}")
    if "PurchasedCard" not in after["draw_pile"]:
        failures.append("purchased card was not placed on deck top")
    if "PurchasedCard" in after["discard_pile"]:
        failures.append("purchased card remained in discard")
    if after["pending_topdeck_uses"] != 0:
        failures.append(f"right was not consumed: {after['pending_topdeck_uses']}")

    return {
        "name": "manual_use_with_single_candidate_auto_placed",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "before": before,
        "after": after,
    }


def run_manual_use_before_any_purchase_errors() -> Dict[str, Any]:
    """打出行動預告但還沒買任何牌就點頂牌：回錯誤，權利不被消耗。"""
    g = make_game()
    p = g.current_player()
    p.hand = [action_card(g, "行動預告")]
    p.resources = {"money": 0, "propaganda": 0}
    g.play_card(0, mode="action")

    before = snapshot(g)
    result = g.use_pending_topdeck_right()
    after = snapshot(g)

    failures: List[str] = []
    if not result.get("error"):
        failures.append(f"expected an error when no purchased card exists yet, got: {result}")
    if after["pending_topdeck_uses"] != 1:
        failures.append(f"right should remain banked, got: {after['pending_topdeck_uses']}")

    return {
        "name": "manual_use_before_any_purchase_errors_without_losing_right",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "before": before,
        "after": after,
    }


def run_end_turn_auto_drains_two_stacked_rights() -> Dict[str, Any]:
    """打出兩張行動預告都沒手動點頂牌，買了 3 張牌（候選數 > 權利數，兩次都是真選擇），
    直接按結束回合：系統自動逐一跳出選擇處理 2 次頂牌權利，選完才真正結束回合、換人。"""
    g = make_game()
    p = g.current_player()
    p.hand = [action_card(g, "行動預告"), action_card(g, "行動預告")]
    p.resources = {"money": 0, "propaganda": 0}
    g.play_card(0, mode="action")
    g.play_card(0, mode="action")

    bought1 = Card("第一張買的牌", "command", {})
    bought2 = Card("第二張買的牌", "command", {})
    bought3 = Card("第三張買的牌", "command", {})
    p.deck.discard_pile = [bought1, bought2, bought3]
    g.turn_log["purchased_cards_this_turn"] = [bought1, bought2, bought3]
    p.deck.draw_pile = [Card(f"Bottom{i}", "command", {}) for i in range(1, 8)]
    g.turn_phase = TurnPhase.END

    after_plays = snapshot(g)
    failures: List[str] = []
    if after_plays["resources"].get("propaganda") != 2:
        failures.append(f"expected 2 propaganda from two plays, got {after_plays['resources']}")
    if after_plays["pending_topdeck_uses"] != 2:
        failures.append(f"expected 2 banked rights, got {after_plays['pending_topdeck_uses']}")

    first_prompt = g.advance_turn_phase()
    first_prompted = snapshot(g)
    if not first_prompt.get("pending_choice"):
        failures.append(f"advance_turn_phase did not auto-prompt for the first right: {first_prompt}")
    first_options = names((g.pending_choice or {}).get("cards") or [])
    if set(first_options) != {"第一張買的牌", "第二張買的牌", "第三張買的牌"}:
        failures.append(f"first prompt candidates mismatch: {first_options}")
    first_resolve = g.resolve_pending_choice(p.id, first_options.index("第一張買的牌")) if "第一張買的牌" in first_options else {}

    second_prompted = snapshot(g)
    if not second_prompted["pending_choice"]:
        failures.append("expected a second real choice among the remaining 2 candidates, but turn already ended")
    else:
        second_options = names((g.pending_choice or {}).get("cards") or [])
        if set(second_options) != {"第三張買的牌", "第二張買的牌"}:
            failures.append(f"second prompt should offer the 2 remaining candidates, got {second_options}")
        second_resolve = g.resolve_pending_choice(p.id, second_options.index("第二張買的牌")) if "第二張買的牌" in second_options else {}
        if not second_resolve.get("success"):
            failures.append(f"second resolve failed: {second_resolve}")

    after = snapshot(g)
    if g.current_player_index != 1:
        failures.append(f"turn did not pass to next player after draining both rights: current_player_index={g.current_player_index}")
    if "第一張買的牌" not in after["hand"] or "第二張買的牌" not in after["hand"]:
        failures.append(f"both topdecked cards should have been drawn into P1's refilled hand: {after['hand']}")
    if "第三張買的牌" not in after["discard_pile"]:
        failures.append("the untouched third purchased card should remain in discard")

    return {
        "name": "end_turn_auto_drains_two_stacked_rights_before_advancing",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "after_plays": after_plays,
        "first_prompted": first_prompted,
        "first_resolve": first_resolve,
        "second_prompted": second_prompted,
        "after": after,
    }


def run_end_turn_drops_right_with_no_candidates() -> Dict[str, Any]:
    """打出行動募資但整回合都沒買牌就結束回合：權利作廢、不卡住回合。"""
    g = make_game()
    p = g.current_player()
    p.hand = [action_card(g, "行動募資")]
    p.resources = {"money": 0, "propaganda": 0}
    g.play_card(0, mode="action")
    p.deck.draw_pile = [Card(f"Bottom{i}", "command", {}) for i in range(1, 8)]
    g.turn_phase = TurnPhase.END

    before = snapshot(g)
    result = g.advance_turn_phase()
    after = snapshot(g)

    failures: List[str] = []
    if result.get("pending_choice"):
        failures.append(f"should not prompt when there is no candidate to topdeck: {result}")
    if g.current_player_index != 1:
        failures.append(f"turn should still complete and pass to next player, got current_player_index={g.current_player_index}")
    if not any("沒有可頂的牌，作廢" in line for line in after["action_log_tail"]):
        failures.append("missing action log noting the dropped topdeck right")

    return {
        "name": "end_turn_drops_unused_right_with_no_candidates",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "before": before,
        "after": after,
    }


def write_reports(results: List[Dict[str, Any]]) -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == "passed"),
        "failed": sum(1 for r in results if r["status"] != "passed"),
        "results": results,
    }
    JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    lines = [
        "# Action Card Topdeck-Right Runtime Validation",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        f"Summary: {summary['passed']} passed / {summary['failed']} failed / {summary['total']} total.",
        "",
        "## Scope (2026-08-07 改版)",
        "- 打出 `行動預告`/`行動募資` 時立刻拿到宣傳/資金（本回合可花用），頂牌變成玩家主動觸發的獨立動作。",
        "- 買牌前點頂牌：回傳錯誤、不消耗權利。買牌後點頂牌：候選牌只有 1 張時自動置頂；2+ 張時開選擇視窗。",
        "- 同一回合打出多張，各自累積成獨立的頂牌權利，可分次使用；沒用完的權利在按下「結束回合」時自動逐一跳出選擇，選完才真正結束回合。",
        "- 完全沒有候選牌時，剩餘權利在回合結束時直接作廢，不會卡住回合推進。",
        "",
    ]
    for r in results:
        lines.extend([
            f"## {r['name']} — {r['status']}",
            "",
        ])
        for key, value in r.items():
            if key in ("name", "status"):
                continue
            lines.append(f"- {key}: `{value}`")
        lines.append("")
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    results = [
        run_play_grants_resource_and_banks_right(),
        run_manual_use_with_single_candidate(),
        run_manual_use_before_any_purchase_errors(),
        run_end_turn_auto_drains_two_stacked_rights(),
        run_end_turn_drops_right_with_no_candidates(),
    ]
    write_reports(results)
    passed = sum(1 for r in results if r["status"] == "passed")
    failed = len(results) - passed
    print(f"Action card topdeck-right runtime validation: {passed} passed / {failed} failed")
    print(f"Wrote {JSON_PATH.relative_to(ROOT)}")
    print(f"Wrote {MD_PATH.relative_to(ROOT)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
