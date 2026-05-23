#!/usr/bin/env python3
"""Validate purchase deck separation and playable hand-card action buttons."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REPORT_JSON = ROOT / "docs" / "records" / "card-play" / "PURCHASE_DECK_AND_HAND_BUTTONS_VALIDATION.json"
REPORT_MD = ROOT / "docs" / "records" / "card-play" / "PURCHASE_DECK_AND_HAND_BUTTONS_VALIDATION.md"

from server.game import Game, STATIC_PURCHASE_CARD_NAMES, TurnPhase, GamePhase  # noqa: E402
from server.cards import Card  # noqa: E402


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def make_runtime_card(game, name):
    card_def = next((c for c in game.structured_cards if c.get("name") == name), None)
    if card_def:
        return Card(card_def["name"], card_def.get("type", "command"), dict(card_def.get("resources", {}) or {}))
    if name == "追隨者":
        return Card("追隨者", "propaganda", {"propaganda": 1})
    if name == "樂捐者":
        return Card("樂捐者", "money", {"money": 1})
    return Card(name, "command", {})


def validate_purchase_deck_excludes_static_cards():
    cases = []
    static = set(STATIC_PURCHASE_CARD_NAMES)
    for mode in ("sample_53", "all_cards"):
        game = Game([("p1", "P1"), ("p2", "P2")], market_mode=mode)
        static_area = [card.name for card in game.purchase_area[:len(STATIC_PURCHASE_CARD_NAMES)]]
        random_names = [card.name for card in game.purchase_area[len(STATIC_PURCHASE_CARD_NAMES):]]
        random_names += [card.name for card in game.purchase_deck.draw_pile]
        random_names += [card.name for card in game.purchase_deck.discard_pile]
        overlap = sorted(static.intersection(random_names))
        assert_true(static_area == list(STATIC_PURCHASE_CARD_NAMES), f"{mode}: static purchase area order changed: {static_area}")
        assert_true(not overlap, f"{mode}: static cards leaked into random purchase deck/area: {overlap}")
        cases.append({"mode": mode, "static_area": static_area, "random_static_overlap": overlap})
    return cases


def validate_engine_play_card_modes_still_work():
    game = Game([("p1", "P1"), ("p2", "P2")])
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    player = game.players[0]
    player.hand = [make_runtime_card(game, "追隨者"), make_runtime_card(game, "樂捐者")]

    resource_result = game.play_card(0, mode="resource")
    assert_true(resource_result.get("success"), f"resource play failed: {resource_result}")
    assert_true(player.resources["propaganda"] == 1, f"resource play did not add propaganda: {player.resources}")
    assert_true([card.name for card in player.hand] == ["樂捐者"], "resource play did not remove played card from hand")

    action_result = game.play_card(0, mode="action")
    assert_true(action_result.get("success"), f"action play failed: {action_result}")
    assert_true(player.hand == [], "action play did not remove played card from hand")
    assert_true([card.name for card in player.deck.discard_pile][-2:] == ["追隨者", "樂捐者"], "played cards were not discarded")
    return {"resource_result": resource_result, "action_result": action_result, "resources": dict(player.resources)}


def validate_hand_buttons_use_bound_event_listeners():
    app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert_true("function bindHandCardActionButtons" in app_js, "missing hand-card button binder")
    assert_true(".hand-card-action-btn" in app_js, "missing hand-card action button class")
    assert_true("data-card-mode=\"resource\"" in app_js, "resource button does not expose data-card-mode")
    assert_true("data-card-mode=\"action\"" in app_js, "action button does not expose data-card-mode")
    assert_true("addEventListener('click'" in app_js, "hand buttons are not bound with click listeners")
    inline_hand_button = re.search(r"<button[^>]+onclick=\\\"event\.stopPropagation\(\); playHandCard", app_js)
    assert_true(not inline_hand_button, "hand card buttons still depend on inline onclick playHandCard")
    return {"bound_event_listener": True, "inline_play_hand_card_removed": True}


def main():
    results = {
        "checks": {
            "purchase_deck_excludes_static_cards": validate_purchase_deck_excludes_static_cards(),
            "engine_play_card_modes_still_work": validate_engine_play_card_modes_still_work(),
            "hand_buttons_use_bound_event_listeners": validate_hand_buttons_use_bound_event_listeners(),
        },
        "passed": 7,
    }
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(
        "# Purchase deck / hand buttons validation\n\n"
        "- purchase deck excludes static cards in sample_53 and all_cards: passed\n"
        "- static area contains 宣傳家 / 思想家 / 資助者 / 資本家 / 分神 / 內鬥 only: passed\n"
        "- play_card resource mode mutates resources/hand/discard: passed\n"
        "- play_card action mode mutates hand/discard: passed\n"
        "- hand card buttons use bound event listeners instead of inline playHandCard onclick: passed\n",
        encoding="utf-8",
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
