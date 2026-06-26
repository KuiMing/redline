import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from server.cards import Card
from server.game import Game, TurnPhase

BUILD_CARDS = {
    "宣傳家": {"builds": 1, "moves": 1, "town_count_min": 1},
    "思想家": {"builds": 1, "moves": 3, "town_count_min": 1},
    "組織經驗丙": {"builds": 1, "moves": 0, "town_count_min": 1},
    "組織經驗乙": {"builds": 2, "moves": 0, "town_count_min": 1},
    "組織經驗甲": {"builds": 1, "moves": 0, "town_count_min": 1},
}


def card_def(game, name):
    return next(c for c in game.structured_cards if c["name"] == name)


def make_game(card_name):
    game = Game([("red", "red"), ("hk", "hk")])
    player = next(p for p in game.players if p.id == "hk")
    player.faction_id = "hong_kong"
    player.base = "香港城"
    player.organizations = {"香港城": 1}
    player.resources = {"money": 0, "propaganda": 0}
    player.moves_left = 0
    game.current_player_index = game.players.index(player)
    game.turn_phase = TurnPhase.ACTION
    definition = card_def(game, card_name)
    player.hand = [Card(definition["name"], definition.get("type", "test"), definition.get("resources", {}))]
    return game, player


def validate_card(card_name, expected):
    game, player = make_game(card_name)
    before_orgs = sum(player.organizations.values())
    initial_result = game.play_card(0, mode="action")
    prompts = []
    resolved = []
    for _ in range(10):
        choice = game.pending_choice
        if not choice:
            break
        prompts.append({
            "type": choice.get("type"),
            "choice_key": choice.get("choice_key"),
            "prompt": choice.get("prompt"),
            "town_count": len(choice.get("towns") or []),
        })
        if choice.get("type") != "town_choice" or choice.get("choice_key") != "card_build_organization":
            break
        towns = choice.get("towns") or []
        if not towns:
            raise AssertionError(f"{card_name}: no legal build towns in pending choice")
        # Prefer building into a new town to prove expansion from the base works.
        index = next(
            (idx for idx, entry in enumerate(towns) if entry.get("town") != player.base and player.organizations.get(entry.get("town"), 0) == 0),
            0,
        )
        result = game.resolve_pending_choice(player.id, index)
        if result.get("error"):
            raise AssertionError(f"{card_name}: resolve failed: {result}")
        resolved.append(result)
    after_orgs = sum(player.organizations.values())
    ok = (
        initial_result.get("pending_choice") is True
        and not game.pending_choice
        and len(prompts) == expected["builds"]
        and all(item["choice_key"] == "card_build_organization" for item in prompts)
        and all(item["town_count"] >= expected["town_count_min"] for item in prompts)
        and after_orgs == before_orgs + expected["builds"]
        and player.moves_left == expected["moves"]
    )
    return {
        "card": card_name,
        "ok": ok,
        "initial_result": initial_result,
        "prompts": prompts,
        "resolved": resolved,
        "before_orgs": before_orgs,
        "after_orgs": after_orgs,
        "expected_after_orgs": before_orgs + expected["builds"],
        "moves_left": player.moves_left,
        "expected_moves": expected["moves"],
        "organizations": player.organizations,
        "action_log_tail": game.action_log[-8:],
    }


def main():
    reports = [validate_card(name, expected) for name, expected in BUILD_CARDS.items()]
    summary = {
        "total": len(reports),
        "passed": sum(1 for item in reports if item["ok"]),
        "failed": sum(1 for item in reports if not item["ok"]),
    }
    output = {"summary": summary, "reports": reports}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
