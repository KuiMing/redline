#!/usr/bin/env python3
"""Regression for 一帶一路 auto build on Red Army turn.

The browser map normally resolves the event town choice with resolve_choice.
If a stale map/control sends the generic build action instead, the backend must
consume the pending event build choice rather than building a normal org and
leaving the turn blocked by pending_choice.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, GamePhase, Player, TurnPhase

OUT_DIR = ROOT / "docs" / "records" / "event-cards"
OUT_JSON = OUT_DIR / "BELT_ROAD_RED_TURN_BUILD_GATING.json"
OUT_MD = OUT_DIR / "BELT_ROAD_RED_TURN_BUILD_GATING.md"


def setup_game() -> tuple[Game, Player, Player]:
    game = Game([(str(uuid4()), "BEN"), (str(uuid4()), "紅軍")], market_mode="all_cards")
    viewer, red = game.players
    viewer.faction_id = "liberals"
    red.faction_id = "red_army"
    viewer.base = "臺北"
    red.base = "北京"
    viewer.organizations = {"臺北": 1}
    red.organizations = {"北京": 1}
    viewer.hand = [Card("BEN 保留手牌", "money", {"money": 1})]
    red.hand = [Card("紅軍保留手牌", "propaganda", {"propaganda": 1})]
    game.pending_base_choices = {}
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 0
    game.round_start_player_index = 0
    game.turn_phase = TurnPhase.EVENT
    event = game._event_by_name("一帶一路 南洋")
    assert event, "event fixture missing"
    game.event_deck.draw_pile = [event]
    game.event_deck.discard_pile = []
    game.current_event = None
    game.event_progress = None
    game.event_notification = None
    game.pending_choice = None
    return game, viewer, red


def advance_to_red_auto_build(game: Game):
    results = []
    for label in ["draw_event", "to_action", "to_purchase", "to_red_turn"]:
        result = game.advance_turn_phase()
        results.append({
            "label": label,
            "result": result,
            "current_player": game.current_player().name,
            "turn_phase": str(game.turn_phase),
            "pending_choice": (game.pending_choice or {}).get("choice_key"),
            "event_progress": dict(game.event_progress or {}),
        })
    return results


def run_case(mode: str):
    game, viewer, red = setup_game()
    advance_results = advance_to_red_auto_build(game)
    choice_before = dict(game.pending_choice or {})
    assert choice_before.get("choice_key") == "event_build_organization", choice_before
    assert choice_before.get("player_id") == red.id, choice_before
    bangkok_index = next(i for i, entry in enumerate(choice_before.get("towns") or []) if entry.get("town") == "曼谷")

    if mode == "resolve_choice":
        build_result = game.resolve_pending_choice(red.id, bangkok_index)
    elif mode == "generic_build":
        build_result = game.build_organization("曼谷")
    elif mode == "stale_visual_build_recovery":
        # Simulate a live playtest state produced before the backend fix: the org
        # already appears on the board, but pending_choice still blocks purchase.
        red.organizations["曼谷"] = 1
        build_result = game.build_organization("曼谷")
    elif mode == "stale_advance_recovery":
        red.organizations["曼谷"] = 1
        build_result = game.advance_turn_phase()
    else:
        raise ValueError(mode)

    after_build = {
        "pending_choice": game.pending_choice,
        "red_bangkok_orgs": red.organizations.get("曼谷", 0),
        "turn_phase": str(game.turn_phase),
        "event_progress": dict(game.event_progress or {}),
        "log_tail": game.action_log[-6:],
    }
    advance_result = build_result if mode == "stale_advance_recovery" else game.advance_turn_phase()
    after_advance = {
        "advance_result": advance_result,
        "turn_phase": str(game.turn_phase),
        "pending_choice": game.pending_choice,
        "red_bangkok_orgs": red.organizations.get("曼谷", 0),
        "log_tail": game.action_log[-6:],
    }

    assert build_result.get("success"), build_result
    assert after_build["pending_choice"] is None, after_build
    assert after_build["red_bangkok_orgs"] == 1, after_build
    assert advance_result.get("success") and not advance_result.get("error"), advance_result
    assert game.turn_phase == TurnPhase.END, after_advance

    return {
        "mode": mode,
        "advance_to_red": advance_results,
        "choice_before": {
            "choice_key": choice_before.get("choice_key"),
            "player_id": choice_before.get("player_id"),
            "town_count": len(choice_before.get("towns") or []),
            "bangkok_index": bangkok_index,
            "prompt": choice_before.get("prompt"),
        },
        "build_result": build_result,
        "after_build": after_build,
        "after_advance": after_advance,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cases = [
        run_case("resolve_choice"),
        run_case("generic_build"),
        run_case("stale_visual_build_recovery"),
        run_case("stale_advance_recovery"),
    ]
    report = {"success": True, "cases": cases}
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text(
        "# 一帶一路南洋：紅軍事件建立組織 gating regression\n\n"
        "- resolve_choice path: passed\n"
        "- generic build fallback path: passed\n"
        "- stale visual-build recovery path: passed\n"
        "- stale advance-button recovery path: passed\n"
        "- Verified: 建立曼谷後 pending_choice 清空，按開始購買階段可進入 TurnPhase.END。\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
