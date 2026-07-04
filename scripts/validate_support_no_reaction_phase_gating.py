#!/usr/bin/env python3
"""Regression checks for support-card reactions and phase gating.

Covers the playtest failure where playing 南洋奧援 while another player held a
cancel reaction created a stale pending_choice after the support effect had
already resolved. The player could keep playing cards, but 開始購買階段 was blocked.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, TurnPhase


def make_game():
    game = Game([("red", "red_army"), ("f", "taiwan_green")])
    red = game.players[0]
    f = game.players[1]
    red.name = "red"
    red.faction_id = "red_army"
    f.name = "f"
    f.faction_id = "taiwan_green"
    game.current_player_index = 1
    game.turn = 12
    game.turn_phase = TurnPhase.ACTION
    game.current_event = game._event_by_name("紅軍權貴出逃")
    game.event_progress = {
        "count": 0,
        "required": 3,
        "succeeded": False,
        "settled": False,
        "status": "active",
    }
    return game, red, f


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def test_support_card_does_not_prompt_cancel_reaction_or_block_purchase():
    game, red, f = make_game()
    red.hand = [Card("爆料黑幕", "action", {})]
    f.hand = [
        Card("追隨者", "propaganda", {"propaganda": 1}),
        Card("南洋奧援", "support", {}),
        Card("內鬥", "disruption", {}),
    ]

    result = game.play_card(0, "resource")
    assert_true(result.get("success"), f"resource play failed: {result}")
    result = game.play_card(0, "action")
    assert_true(result.get("success"), f"support play failed: {result}")
    assert_true(not result.get("pending_choice"), f"support card should not prompt cancel reaction: {result}")
    assert_true(game.pending_choice is None, f"stale pending choice after support: {game.pending_choice}")

    result = game.play_card(0, "resource")
    assert_true(result.get("success"), f"post-support resource play failed: {result}")
    result = game.advance_turn_phase()
    assert_true(result.get("success"), f"phase advance blocked after support: {result}")
    assert_true(game.turn_phase == TurnPhase.END, f"expected purchase/END phase, got {game.turn_phase}")


def main():
    tests = [
        test_support_card_does_not_prompt_cancel_reaction_or_block_purchase,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
