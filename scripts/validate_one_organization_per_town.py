import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / "docs" / "records" / "rules-audit"
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase


def case(name, condition, **detail):
    return {"name": name, "ok": bool(condition), "detail": detail}


def shared_game():
    game = Game([("hk", "HK"), ("yue", "Yue"), ("other", "Other")])
    hk, yue, other = game.players
    hk.faction_id = "hong_kong"
    yue.faction_id = "yue"
    other.faction_id = "liberals"
    hk.base = "香港城"
    yue.base = "南寧"
    other.base = "北京"
    hk.organizations = {}
    yue.organizations = {"廣州": 1}
    other.organizations = {}
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.turn_log = game._new_turn_log()
    return game, hk, yue, other


def main():
    results = []

    game, hk, yue, other = shared_game()
    direct = game.build_organization("廣州")
    results.append(case(
        "shared_piece_is_access_not_stack_permission",
        direct.get("error") is not None
        and game._shared_org_count(hk, "廣州") == 1
        and game._shared_origin_owner(hk, "廣州") is yue
        and yue.organizations == {"廣州": 1}
        and hk.organizations == {},
        result=direct,
        shared_count=game._shared_org_count(hk, "廣州"),
        hk_orgs=hk.organizations,
        yue_orgs=yue.organizations,
    ))

    game, hk, yue, other = shared_game()
    own_build = game._place_organization(hk, "深圳")
    second_own = game._place_organization(hk, "深圳")
    second_shared = game._place_organization(yue, "深圳")
    results.append(case(
        "central_placement_rejects_own_and_shared_occupancy",
        own_build and not second_own and not second_shared
        and hk.organizations.get("深圳") == 1
        and yue.organizations.get("深圳", 0) == 0
        and not game._organization_occupancy_violations(),
        own_build=own_build,
        second_own=second_own,
        second_shared=second_shared,
        violations=game._organization_occupancy_violations(),
    ))

    for label, destination_owner in (("own", "hk"), ("shared", "yue"), ("enemy", "other")):
        game, hk, yue, other = shared_game()
        owner = {"hk": hk, "yue": yue, "other": other}[destination_owner]
        owner.organizations["深圳"] = 1
        hk.moves_left = 2
        before = {
            "hk": dict(hk.organizations),
            "yue": dict(yue.organizations),
            "other": dict(other.organizations),
            "moves": hk.moves_left,
        }
        moved = game.move_organization("廣州", "深圳", "rail")
        results.append(case(
            f"movement_rejects_{label}_occupied_destination_atomically",
            "occupied town" in str(moved.get("error"))
            and hk.organizations == before["hk"]
            and yue.organizations == before["yue"]
            and other.organizations == before["other"]
            and hk.moves_left == before["moves"],
            result=moved,
            before=before,
            after={"hk": hk.organizations, "yue": yue.organizations, "other": other.organizations, "moves": hk.moves_left},
        ))

    game, hk, yue, other = shared_game()
    hk.moves_left = 1
    moved = game.move_organization("廣州", "深圳", "rail")
    results.append(case(
        "shared_piece_moves_to_empty_town_as_single_transferred_piece",
        moved.get("success") is True
        and yue.organizations.get("廣州", 0) == 0
        and hk.organizations.get("深圳") == 1
        and game._shared_org_count(hk, "深圳") == 1
        and not game._organization_occupancy_violations(),
        result=moved,
        hk_orgs=hk.organizations,
        yue_orgs=yue.organizations,
        violations=game._organization_occupancy_violations(),
    ))

    game, hk, yue, other = shared_game()
    card_choices = {entry['town'] for entry in game._card_build_town_choices(hk, {'range': 1})}
    event_choices = {entry['town'] for entry in game._event_build_towns_near_own(hk, 1)}
    results.append(case(
        "shared_piece_is_origin_for_card_and_event_builds",
        {'深圳', '澳門'} <= card_choices and {'深圳', '澳門'} <= event_choices,
        card_choices=sorted(card_choices),
        event_choices=sorted(event_choices),
    ))

    game, hk, yue, other = shared_game()
    results.append(case(
        "shared_piece_counts_for_era_region_and_ruler_requirements",
        game._player_region_org_count(hk, 'china') == 1
        and game._player_requirement_org_count(hk, {'ruler': '紅軍'}) == 1,
        china_count=game._player_region_org_count(hk, 'china'),
        red_ruler_count=game._player_requirement_org_count(hk, {'ruler': '紅軍'}),
    ))

    game, hk, yue, other = shared_game()
    hk.organizations = {"香港城": 1}
    choices = game._card_build_town_choices(hk, {"range": "ignore_distance"})
    choice_names = {entry["town"] for entry in choices}
    results.append(case(
        "card_build_choices_exclude_every_occupied_town",
        "香港城" not in choice_names and "廣州" not in choice_names,
        occupied=["香港城", "廣州"],
        choice_count=len(choice_names),
    ))

    game, hk, yue, other = shared_game()
    hk.organizations = {"香港城": 2}
    yue.organizations["香港城"] = 1
    violations = game._organization_occupancy_violations()
    results.append(case(
        "diagnostic_detects_stacks_and_multiple_owners",
        any(entry["town"] == "香港城" for entry in violations),
        violations=violations,
    ))

    red_game = Game([("red", "Red"), ("attacker", "Attacker")])
    red, attacker = red_game.players
    red.faction_id = "red_army"
    attacker.faction_id = "liberals"
    red.base = "北京"
    red.organizations = {"北京": 1}
    attacker.organizations = {"天津": 1}
    red_game.turn_log = red_game._new_turn_log()
    first = red_game.dissolve_organization(attacker, red, "北京", source="card")
    first_preserved = red.organizations.get("北京") == 1 and red.base == "北京"
    second = red_game.dissolve_organization(attacker, red, "北京", source="card")
    results.append(case(
        "red_army_base_uses_two_hit_counter_not_stacked_pieces",
        first.get("success") and not first.get("red_base_destroyed")
        and first_preserved
        and second.get("success") and second.get("red_base_destroyed")
        and red.organizations.get("北京", 0) == 0
        and red.base == "北京"
        and "北京" in set(red_game.turn_log.get("red_army_base_build_blocks", []) or []),
        first=first,
        first_preserved=first_preserved,
        second=second,
        red_orgs=red.organizations,
    ))

    summary = {
        "scope": ["global one-organization-per-town invariant", "香港/粵/澳門 shared access", "movement", "card build choices", "Red Army base durability"],
        "total": len(results),
        "passed": sum(1 for item in results if item["ok"]),
        "failed": sum(1 for item in results if not item["ok"]),
    }
    payload = {"summary": summary, "results": results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    (RECORD_DIR / "ONE_ORGANIZATION_PER_TOWN_RUNTIME_VALIDATION.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# 一城一組織 Runtime Validation",
        "",
        "- 規則裁決：共用組織代表共同使用同一枚實體組織，不代表可在同城疊放第二枚。",
        f"- total: {summary['total']}",
        f"- passed: {summary['passed']}",
        f"- failed: {summary['failed']}",
        "",
    ]
    lines.extend(f"- {'PASS' if item['ok'] else 'FAIL'} {item['name']}" for item in results)
    (RECORD_DIR / "ONE_ORGANIZATION_PER_TOWN_RUNTIME_VALIDATION.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
