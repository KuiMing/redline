#!/usr/bin/env python3
"""Runtime validation for 行動預告 / 行動募資 end-turn prompt flow."""
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
    return [getattr(card, "name", str(card)) for card in cards]


def make_game() -> Game:
    g = Game([("p1", "P1"), ("p2", "P2")])
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.END
    g.current_player_index = 0
    g.pending_base_choices = {}
    g.players[0].faction_id = "red_army"
    return g


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
            "options": list(pending.get("options") or []),
        }
    return {
        "turn_phase": g.turn_phase,
        "current_player": p.name,
        "hand": names(p.hand),
        "draw_pile": names(p.deck.draw_pile),
        "discard_pile": names(p.deck.discard_pile),
        "turn_log": serializable(dict(g.turn_log)),
        "pending_choice": pending_summary,
        "action_log_tail": list(g.action_log[-8:]),
    }


def run_use_scenario(card_name: str, choose_index: int) -> Dict[str, Any]:
    g = make_game()
    p = g.current_player()
    bought = Card("PurchasedCard", "command", {})
    p.hand = [action_card(g, card_name), Card("Filler", "command", {})]
    p.deck.draw_pile = [Card(f"Bottom{i}", "command", {}) for i in range(1, 6)]
    p.deck.discard_pile = [bought]
    g.turn_log["purchased_cards_this_turn"] = [bought]

    before = snapshot(g)
    prompt_result = g.advance_turn_phase()
    prompted = snapshot(g)
    resolve_result = g.resolve_pending_choice(p.id, choose_index)
    after = snapshot(g)

    failures: List[str] = []
    expected_label = f"使用 {card_name}"
    options = [option.get("label") for option in (prompted.get("pending_choice") or {}).get("options") or []]
    if prompt_result.get("pending_choice") is not True:
        failures.append(f"{card_name}: end-turn advance did not prompt")
    if options != ["不使用", expected_label]:
        failures.append(f"{card_name}: options mismatch {options}")
    if not resolve_result.get("success"):
        failures.append(f"{card_name}: resolve failed {resolve_result}")
    if "PurchasedCard" not in after["hand"]:
        failures.append(f"{card_name}: purchased card was not drawn into hand")
    if "PurchasedCard" in after["discard_pile"]:
        failures.append(f"{card_name}: purchased card remained in discard")
    if card_name not in after["discard_pile"]:
        failures.append(f"{card_name}: used action card was not discarded")
    if after["turn_phase"] != TurnPhase.EVENT:
        failures.append(f"{card_name}: turn did not advance to EVENT")
    if not any(f"used {card_name} before drawing new hand" in line for line in after["action_log_tail"]):
        failures.append(f"{card_name}: missing action log")

    return {
        "name": f"{card_name}_end_turn_use",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "prompt_result": prompt_result,
        "resolve_result": resolve_result,
        "before": before,
        "prompted": prompted,
        "after": after,
    }


def run_skip_scenario() -> Dict[str, Any]:
    g = make_game()
    p = g.current_player()
    bought = Card("PurchasedCard", "command", {})
    p.hand = [action_card(g, "行動募資")]
    p.deck.draw_pile = [Card(f"Draw{i}", "command", {}) for i in range(1, 6)]
    p.deck.discard_pile = [bought]
    g.turn_log["purchased_cards_this_turn"] = [bought]

    before = snapshot(g)
    prompt_result = g.advance_turn_phase()
    prompted = snapshot(g)
    resolve_result = g.resolve_pending_choice(p.id, 0)
    after = snapshot(g)

    failures: List[str] = []
    if prompt_result.get("pending_choice") is not True:
        failures.append("skip: end-turn advance did not prompt")
    if not resolve_result.get("success") or not resolve_result.get("skipped"):
        failures.append(f"skip: resolve did not skip {resolve_result}")
    if "PurchasedCard" in after["hand"]:
        failures.append("skip: purchased card should not be drawn")
    if "PurchasedCard" not in after["discard_pile"]:
        failures.append("skip: purchased card should remain discarded")
    if not any("skipped end-turn action topdeck prompt" in line for line in after["action_log_tail"]):
        failures.append("skip: missing action log")

    return {
        "name": "skip_end_turn_prompt",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "prompt_result": prompt_result,
        "resolve_result": resolve_result,
        "before": before,
        "prompted": prompted,
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
    JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Action Card End-Turn Topdeck Runtime Validation",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        f"Summary: {summary['passed']} passed / {summary['failed']} failed / {summary['total']} total.",
        "",
        "## Scope",
        "- 回合 END 階段進入真正結束回合前，若玩家手上有 `行動預告` / `行動募資` 且本回合購得的牌仍在棄牌堆，先提示可使用。",
        "- 選擇使用後，該行動卡把本回合購得牌置頂；同一次 end-turn 補牌會把該購得牌抽入手牌。",
        "- 玩家也可以選擇不使用，購得牌維持在棄牌堆。",
        "",
    ]
    for r in results:
        lines.extend([
            f"## {r['name']} — {r['status']}",
            "",
            f"- Prompt result: `{r['prompt_result']}`",
            f"- Resolve result: `{r['resolve_result']}`",
            f"- Before: `{r['before']}`",
            f"- Prompted: `{r['prompted']['pending_choice']}`",
            f"- After: `{r['after']}`",
        ])
        if r["failures"]:
            lines.append(f"- Failures: `{r['failures']}`")
        lines.append("")
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    results = [
        run_use_scenario("行動預告", 1),
        run_use_scenario("行動募資", 1),
        run_skip_scenario(),
    ]
    write_reports(results)
    passed = sum(1 for r in results if r["status"] == "passed")
    failed = len(results) - passed
    print(f"Action card end-turn topdeck validation: {passed} passed / {failed} failed")
    print(f"Wrote {JSON_PATH.relative_to(ROOT)}")
    print(f"Wrote {MD_PATH.relative_to(ROOT)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
