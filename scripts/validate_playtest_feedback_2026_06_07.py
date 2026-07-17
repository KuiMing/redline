import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase, STATIC_PURCHASE_CARD_SUPPLY
from server.cards import Card

OUT_DIR = ROOT / "docs" / "records" / "playtest-feedback"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def make_game(faction="hong_kong"):
    game = Game([
        ("ben", "Ben"),
        ("red", "Red"),
    ])
    for player in game.players:
        if player.name == "Ben":
            player.faction_id = faction
        elif player.name == "Red":
            player.faction_id = "red_army"
    game.turn_phase = TurnPhase.ACTION
    # 開局隨機抽的事件可能是互動型（如 一帶一路 auto build），會在打牌時插入事件自己的
    # pending choice 污染這些單元檢查；固定換成無效果的歲月靜好。
    game.current_event = dict(game._event_by_name("歲月靜好"))
    game.event_progress = {"count": 0, "required": 0, "succeeded": True, "settled": True, "status": "idle"}
    game.event_modifiers = []
    return game


def check_static_purchase_repeats():
    game = make_game()
    player = game.current_player()
    # 2026-06-26 起 buy_card 僅限購買（END）階段。
    game.turn_phase = TurnPhase.END
    idx = game.state()["purchase_area"].index("宣傳家")
    before = game.static_purchase_supply["宣傳家"]
    player.resources = {"money": 0, "propaganda": 30}
    first = game.buy_card(idx)
    player.resources = {"money": 0, "propaganda": 30}
    second = game.buy_card(idx)
    after = game.static_purchase_supply["宣傳家"]
    return {
        "name": "static_propagandist_can_be_bought_after_first_round_and_supply_decrements",
        "passed": first.get("success") and second.get("success") and before == STATIC_PURCHASE_CARD_SUPPLY["宣傳家"] and after == before - 2,
        "details": {"before": before, "after": after, "first": first, "second": second},
    }


def check_propagandist_action():
    game = make_game(faction="taiwan_green")
    player = game.current_player()
    player.base = "臺北"
    player.organizations = {"臺北": 1}
    player.hand = [Card("宣傳家", "propaganda", {"propaganda": 2})]
    before_supply = game.static_purchase_supply["宣傳家"]
    result = game.play_card(0, mode="action")
    # 建組織現在是互動式選城鎮（card_build_organization），選臺北完成建造。
    build_choice_ok = bool(
        result.get("pending_choice")
        and game.pending_choice
        and game.pending_choice.get("choice_key") == "card_build_organization"
    )
    resolve_result = {}
    if build_choice_ok:
        towns = [entry["town"] for entry in game.pending_choice.get("towns", [])]
        if "臺北" in towns:
            resolve_result = game.resolve_pending_choice(player.id, towns.index("臺北"))
    after_supply = game.static_purchase_supply["宣傳家"]
    return {
        "name": "propagandist_action_returns_card_then_builds_via_town_choice_and_grants_one_move",
        "passed": result.get("success") and build_choice_ok and resolve_result.get("success") and after_supply == before_supply + 1 and player.organizations.get("臺北") == 2 and player.moves_left == 1,
        "details": {"result": result, "resolve_result": resolve_result, "before_supply": before_supply, "after_supply": after_supply, "orgs": player.organizations, "moves_left": player.moves_left, "pending_choice": game.state().get("pending_choice")},
    }


def check_press_advantage_pending_choice():
    game = make_game()
    player = game.current_player()
    player.hand = [Card("乘勝追擊", "command", {"money": 1})]
    player.deck.discard_pile = [Card("宣傳家", "propaganda", {"propaganda": 2})]
    result = game.play_card(0, mode="action")
    choice = game.state().get("pending_choice")
    return {
        "name": "press_advantage_opens_discard_gain_choice",
        "passed": result.get("success") and result.get("pending_choice") and choice and choice.get("choice_key") == "gain_from_discard" and choice.get("cards") == ["宣傳家"],
        "details": {"result": result, "pending_choice": choice},
    }


def check_support_resource_noop_and_random_buy_removes_slot():
    game = make_game()
    player = game.current_player()
    player.hand = [game._make_support_card("北國奧援")]
    player.resources = {"money": 0, "propaganda": 0}
    resource_result = game.play_card(0, mode="resource")
    support_resources_after = dict(player.resources)
    no_resource = support_resources_after == {"money": 0, "propaganda": 0}

    game = make_game()
    player = game.current_player()
    # buy_card 僅限購買（END）階段。
    game.turn_phase = TurnPhase.END
    player.resources = {"money": 10, "propaganda": 10}
    game.purchase_area = game._static_purchase_cards() + [game._make_support_card("北國奧援")]
    before_area = game.state()["purchase_area"]
    buy_result = game.buy_card(len(game._static_purchase_cards()))
    after_area = game.state()["purchase_area"]
    return {
        "name": "support_resource_gives_no_resources_and_support_purchase_removes_random_slot",
        "passed": resource_result.get("success") and no_resource and buy_result.get("success") and "北國奧援" in before_area and "北國奧援" not in after_area,
        "details": {"resource_result": resource_result, "resources_after": support_resources_after, "before_area": before_area, "buy_result": buy_result, "after_area": after_area},
    }


def check_east_turkestan_failure_discards_non_red():
    game = make_game()
    for index, player in enumerate(game.players):
        player.hand = [Card(f"手牌{index}", "command", {})]
    game.current_event = {
        "name": "東突厥集中營",
        "type": "mission",
        "trigger": {"type": "play_card_with_propaganda", "count": 1},
        "success": {"type": "gain_card", "card": "宣傳家", "count": 1},
        "failure": {"type": "discard_random", "count": 1},
    }
    game.event_progress = {"count": 0, "required": 1, "succeeded": False, "settled": False, "status": "active"}
    result = game._settle_current_event()
    non_red = next(p for p in game.players if p.faction_id != "red_army")
    red = next(p for p in game.players if p.faction_id == "red_army")
    return {
        "name": "east_turkestan_failure_random_discards_non_red_not_red",
        "passed": result.get("success") and len(non_red.hand) == 0 and len(non_red.deck.discard_pile) == 1 and len(red.hand) == 1,
        "details": {"result": result, "non_red_hand": [c.name for c in non_red.hand], "non_red_discard": [c.name for c in non_red.deck.discard_pile], "red_hand": [c.name for c in red.hand]},
    }


def main():
    checks = [
        check_static_purchase_repeats(),
        check_propagandist_action(),
        check_press_advantage_pending_choice(),
        check_support_resource_noop_and_random_buy_removes_slot(),
        check_east_turkestan_failure_discards_non_red(),
    ]
    summary = {"total": len(checks), "passed": sum(1 for c in checks if c["passed"]), "failed": sum(1 for c in checks if not c["passed"])}
    payload = {"summary": summary, "checks": checks}
    (OUT_DIR / "PLAYTEST_FEEDBACK_2026_06_07_VALIDATION.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# Playtest feedback validation — 2026-06-07", "", f"Summary: {summary['passed']}/{summary['total']} passed", ""]
    for check in checks:
        md.append(f"- [{'x' if check['passed'] else ' '}] {check['name']}")
    (OUT_DIR / "PLAYTEST_FEEDBACK_2026_06_07_VALIDATION.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "json": str(OUT_DIR / "PLAYTEST_FEEDBACK_2026_06_07_VALIDATION.json"), "md": str(OUT_DIR / "PLAYTEST_FEEDBACK_2026_06_07_VALIDATION.md")}, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
