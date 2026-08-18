#!/usr/bin/env python3
"""Regression checks for support-card cancel reactions and phase gating.

Originally (2026-07-04) this guarded a workaround that suppressed cancel-reaction
prompts for support cards entirely, because prompting *after* the support effect had
already resolved left a stale pending_choice that blocked 開始購買階段.

2026-08-05 (playtest report P2 "先使用宣傳家再使用東洋奧援，第二次爆料黑幕沒有跳出通知")
reversed that user-facing behavior: support cards MUST offer the cancel reaction like any
other card. The stale-pending root cause is now fixed properly — the reaction window opens
*before* the support card mutates the board (support execution is deferred into
_resume_reaction_pending_action), so declining resolves cleanly and the phase can still
advance. This file now asserts that new behavior AND the preserved phase-gating guarantee.
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


def test_support_card_prompts_cancel_reaction_then_declined_does_not_block_purchase():
    game, red, f = make_game()
    red.hand = [Card("爆料黑幕", "action", {})]
    f.hand = [
        Card("追隨者", "propaganda", {"propaganda": 1}),
        Card("南洋奧援", "support", {}),
        Card("內鬥", "disruption", {}),
    ]

    result = game.play_card(0, "resource")
    assert_true(result.get("success"), f"resource play failed: {result}")
    # Playing the support card must now open a cancel-reaction window for the holder of
    # 爆料黑幕 (report P2), *before* the support effect resolves — no stale pending.
    result = game.play_card(0, "action")
    assert_true(result.get("pending_choice") is True, f"support play should prompt reaction: {result}")
    pending = game.pending_choice or {}
    assert_true(pending.get("type") == "reaction_choice", f"support card must prompt cancel reaction now: {pending}")
    assert_true(pending.get("player_id") == red.id, f"reaction offered to wrong player: {pending}")
    assert_true(pending.get("played_card_name") == "南洋奧援", f"unexpected reacted card: {pending}")

    # Decline: the support effect resolves now (南洋奧援 I 級 opens a legitimate discard
    # choice); resolving it must leave no stale pending choice.
    declined = game.resolve_pending_choice(red.id, 0)
    assert_true(declined.get("success"), f"decline resolve failed: {declined}")
    pending = game.pending_choice or {}
    assert_true(pending.get("type") != "reaction_choice", f"reaction should be gone after decline: {pending}")
    if pending.get("choice_key") == "draw_then_discard_choice":
        resolved = game.resolve_pending_choice(f.id, 0)
        assert_true(resolved.get("success"), f"discard choice resolve failed: {resolved}")
    assert_true(game.pending_choice is None, f"stale pending choice after support: {game.pending_choice}")

    result = game.play_card(0, "resource")
    assert_true(result.get("success"), f"post-support resource play failed: {result}")
    result = game.advance_turn_phase()
    assert_true(result.get("success"), f"phase advance blocked after support: {result}")
    # 出牌與購買已合併：購買全程可用，advance 就是唯一一次「結束行動階段」，
    # 沒有殘留 pending_choice 時它會乾淨地結束回合並把席位交出去。
    assert_true(game.turn_phase == TurnPhase.ACTION, f"expected next player ACTION phase, got {game.turn_phase}")


def test_support_card_cancel_reaction_prevents_effect_and_does_not_block_purchase():
    game, red, f = make_game()
    red.hand = [Card("爆料黑幕", "action", {})]
    f.hand = [Card("南洋奧援", "support", {})]
    hand_before = len(f.hand)

    result = game.play_card(0, "action")
    assert_true(result.get("pending_choice") is True, f"support play should prompt reaction: {result}")
    assert_true((game.pending_choice or {}).get("type") == "reaction_choice", game.pending_choice)

    # Cancel with 爆料黑幕 (option index 1): the support effect must NOT resolve, and no
    # stale pending choice may remain to block phase advance.
    canceled = game.resolve_pending_choice(red.id, 1)
    assert_true(canceled.get("canceled") is True, f"expected cancellation: {canceled}")
    assert_true(game.pending_choice is None, f"stale pending choice after cancel: {game.pending_choice}")
    assert_true("爆料黑幕" in [getattr(c, "name", str(c)) for c in red.deck.discard_pile], "reaction card should be discarded")
    # 南洋奧援 was played (out of hand) but its draw/discard effect never ran.
    assert_true(len(f.hand) == hand_before - 1, f"support card should have left hand: {len(f.hand)}")

    result = game.advance_turn_phase()
    assert_true(result.get("success"), f"phase advance blocked after cancel: {result}")
    # 出牌與購買已合併：購買全程可用，advance 就是唯一一次「結束行動階段」，
    # 沒有殘留 pending_choice 時它會乾淨地結束回合並把席位交出去。
    assert_true(game.turn_phase == TurnPhase.ACTION, f"expected next player ACTION phase, got {game.turn_phase}")


def main():
    tests = [
        test_support_card_prompts_cancel_reaction_then_declined_does_not_block_purchase,
        test_support_card_cancel_reaction_prevents_effect_and_does_not_block_purchase,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
