import json
import random
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from server.game import Game, TurnPhase
from server.victory import VictoryEngine


SEMANTIC_POOLS = {
    "任意牆內": "china",
    "任意牆內城鎮": "china",
    "任意英美城鎮": {"華盛頓", "紐約", "多倫多", "卡加利", "溫哥華", "舊金山", "洛杉磯", "倫敦"},
    "任意南洋": {"曼谷", "吉隆坡", "新加坡", "雅加達", "河內", "胡志明市", "仰光"},
    "任意南洋城鎮": {"曼谷", "吉隆坡", "新加坡", "雅加達", "河內", "胡志明市", "仰光"},
    "任意東洋": {"東京", "大阪", "福岡", "札幌", "仙臺", "沖繩", "首爾", "釜山"},
}

ALIAS_TOWNS = {
    '梅州': '梅州',
}

RECORD_DIR = BASE / 'docs' / 'records' / 'misc'


def china_towns(game):
    return list(game._towns_for_region_alias('china'))


def allowed_base_names(game, faction):
    names = []
    for b in faction.get("bases", []):
        if isinstance(b, dict) and b.get("name"):
            names.append(b.get("name"))
        elif isinstance(b, str) and b:
            names.append(b)
    china_town_set = set(china_towns(game))
    allowed = set()
    for name in names:
        if name in game.map.get("towns", {}):
            allowed.add(name)
            continue
        pool = SEMANTIC_POOLS.get(name)
        if pool == "china":
            allowed.update(china_town_set)
        elif isinstance(pool, set):
            allowed.update(pool)
    return allowed


def validate_bases(game):
    factions = {f["id"]: f for f in game.factions}
    base_rows = []
    base_names = []
    for p in game.players:
        faction = factions[p.faction_id]
        allowed = allowed_base_names(game, faction)
        base_rows.append({
            "player": p.name,
            "faction": p.faction_id,
            "base": p.base,
            "orgs": dict(p.organizations),
            "single_base_org": list(p.organizations.keys()) == [p.base] and p.organizations.get(p.base) == 1,
            "base_allowed": p.base in allowed,
            "allowed_sample": sorted(list(allowed))[:12],
        })
        base_names.append(p.base)
    return {
        "rows": base_rows,
        "unique_bases": len(base_names) == len(set(base_names)),
    }


def forced_victory_orgs(game, player):
    faction = game.faction_by_id.get(player.faction_id, {})
    conditions = faction.get('win_conditions', []) or []
    all_towns = list(game.map.get('towns', {}).keys())
    china_town_list = china_towns(game)

    if not conditions:
        return {town: 1 for town in china_town_list[:14]}

    orgs = {}
    target_conditions = max(1, (len(conditions) * 2) // 3)
    satisfied_seeded = 0

    for cond in conditions:
        if satisfied_seeded >= target_conditions:
            break
        cond_type = cond.get('type')
        if cond_type == 'default_survival':
            continue
        if cond_type == 'taiwan_override' and player.faction_id != 'red_army':
            continue

        required = [town for town in cond.get('required_locations', []) if town in game.map.get('towns', {})]
        for town in required:
            orgs[town] = 1

        count = int(cond.get('count', 0) or 0)
        if cond.get('scope') == '牆內':
            pool = china_town_list
        else:
            pool = all_towns

        for town in pool:
            if town not in orgs:
                orgs[town] = 1
            in_scope_count = sum(1 for seeded in orgs if seeded in set(pool))
            if in_scope_count >= max(count, 0):
                break
        satisfied_seeded += 1

    if not orgs:
        orgs = {town: 1 for town in china_town_list[:14]}
    return orgs


def resolve_pending_choices(game, trace, label, max_steps=12):
    resolved = []
    for step in range(max_steps):
        choice = getattr(game, 'pending_choice', None)
        if not choice:
            break
        player_id = choice.get('player_id')
        choice_type = choice.get('type')
        choice_key = choice.get('choice_key')
        if not player_id:
            resolved.append({'error': 'pending choice without player_id', 'choice': dict(choice)})
            break
        index = [0] if choice_type == 'multi_card_choice' and int(choice.get('count', 1) or 1) == 1 else 0
        result = game.resolve_pending_choice(player_id, index)
        resolved.append({
            'player_id': player_id,
            'choice_type': choice_type,
            'choice_key': choice_key,
            'index': index,
            'result': result,
            'turn': game.turn,
            'turn_phase': game.turn_phase,
            'current_player': game.current_player().name,
        })
        if isinstance(result, dict) and result.get('error'):
            break
    if resolved:
        trace.append({'step': f'{label}_resolve_pending_choices', 'resolved': resolved})
    return resolved


def run_game(player_count):
    random.seed(20260510 + player_count)
    game = Game([(f"p{i}", f"player{i}") for i in range(1, player_count + 1)])
    trace = []

    if game.game_phase == game.game_phase.BASE_SELECTION:
        initial_pending = json.loads(json.dumps(game.pending_base_choices, ensure_ascii=False))
        for pid, choice_data in list(game.pending_base_choices.items()):
            labels = choice_data.get('labels', [])
            resolved = choice_data.get('resolved', {})
            chosen = None
            for label in labels:
                for town in resolved.get(label, []):
                    result = game.set_base_choice(pid, town, label=label)
                    if result.get('success'):
                        chosen = {'player_id': pid, 'label': label, 'town': town, 'result': result}
                        break
                if chosen:
                    break
            trace.append({"step": "base_selection_choice", "choice": chosen})
        trace.append({
            "step": "base_selection_resolution",
            "initial_pending": initial_pending,
            "remaining_pending": dict(game.pending_base_choices),
            "game_phase_after_selection": game.game_phase,
        })

    base_validation = validate_bases(game)
    trace.append({
        "step": "init",
        "turn": game.turn,
        "turn_phase": game.turn_phase,
        "current_player": game.current_player().name,
        "base_validation": base_validation,
    })

    cycles = player_count * 2
    for cycle in range(1, cycles + 1):
        trace.append({
            "step": f"cycle_{cycle}_advance_to_action_before",
            "turn": game.turn,
            "turn_phase": game.turn_phase,
            "current_player": game.current_player().name,
        })
        game.advance_turn_phase()
        trace.append({
            "step": f"cycle_{cycle}_advance_to_action_after",
            "turn": game.turn,
            "turn_phase": game.turn_phase,
            "current_player": game.current_player().name,
        })
        resolve_pending_choices(game, trace, f"cycle_{cycle}_after_advance_to_action")
        if game.turn_phase == TurnPhase.EVENT and not game.pending_choice:
            game.advance_turn_phase()
            trace.append({
                "step": f"cycle_{cycle}_advance_to_action_after_pending_resolution",
                "turn": game.turn,
                "turn_phase": game.turn_phase,
                "current_player": game.current_player().name,
            })

        player = game.current_player()
        hand_before = [c.name for c in player.hand]
        play_result = game.play_card(0, mode='action') if player.hand else {"skipped": True}
        hand_after = [c.name for c in player.hand]
        trace.append({
            "step": f"cycle_{cycle}_play_card",
            "player": player.name,
            "faction": player.faction_id,
            "hand_before": hand_before,
            "hand_after": hand_after,
            "result": play_result,
            "resources": dict(player.resources),
            "moves_left": player.moves_left,
        })

        move_result = {"skipped": True, "reason": "no move points"}
        move_detail = None
        if player.moves_left > 0:
            for from_town in list(player.organizations.keys()):
                if from_town == player.base and player.organizations.get(from_town, 0) <= 1:
                    continue
                town = game.map["towns"].get(from_town, {})
                roads = list(town.get("road") or [])
                rails = list(town.get("rail") or [])
                if roads:
                    target = ALIAS_TOWNS.get(roads[0], roads[0])
                    move_result = game.move_organization(from_town, target, "road")
                    move_detail = {"from": from_town, "to": target, "mode": "road"}
                    break
                if rails:
                    target = ALIAS_TOWNS.get(rails[0], rails[0])
                    move_result = game.move_organization(from_town, target, "rail")
                    move_detail = {"from": from_town, "to": target, "mode": "rail"}
                    break
        trace.append({
            "step": f"cycle_{cycle}_move",
            "player": player.name,
            "move_detail": move_detail,
            "result": move_result,
            "orgs_after": dict(player.organizations),
            "moves_left_after": player.moves_left,
        })

        # 出牌與購買同屬一個行動階段：一次「結束行動階段」就結束回合並交棒。
        trace.append({
            "step": f"cycle_{cycle}_action_phase_done",
            "turn": game.turn,
            "turn_phase": game.turn_phase,
            "current_player": game.current_player().name,
        })

        game.advance_turn_phase()
        trace.append({
            "step": f"cycle_{cycle}_end_turn",
            "turn": game.turn,
            "turn_phase": game.turn_phase,
            "current_player": game.current_player().name,
        })

    winner_player = next(
        (p for p in game.players if p.faction_id != 'red_army' and game.faction_by_id.get(p.faction_id, {}).get('win_conditions')),
        None,
    )
    forced_red_survival = False
    if winner_player is None:
        winner_player = next((p for p in game.players if p.faction_id == 'red_army'), game.players[0])
        game.turn = 21
        forced_red_survival = True
    else:
        winner_player.organizations = forced_victory_orgs(game, winner_player)

    trace.append({
        "step": "before_forced_victory_check",
        "candidate": winner_player.name,
        "faction": winner_player.faction_id,
        "org_count": sum(winner_player.organizations.values()),
        "forced_red_survival": forced_red_survival,
        "turn": game.turn,
        "turn_phase": game.turn_phase,
    })

    did_win, winner_name = VictoryEngine(game.factions).evaluate(game)
    if did_win:
        game.game_phase = game.game_phase.FINISHED
        game.winner = winner_name

    trace.append({
        "step": "after_forced_victory_check",
        "did_win": did_win,
        "game_phase": game.game_phase,
        "winner": game.winner,
        "turn": game.turn,
        "turn_phase": game.turn_phase,
    })

    return {
        "player_count": player_count,
        "trace": trace,
        "final_state": game.state(),
    }


def write_outputs(result):
    count = result["player_count"]
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / f"FULL_GAMEPLAY_{count}P_VALIDATION.json"
    md_path = RECORD_DIR / f"FULL_GAMEPLAY_{count}P_VALIDATION.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [f"# FULL GAMEPLAY {count}P VALIDATION", "", "日期：2026-05-03", ""]
    for item in result["trace"]:
        lines.append(f"## {item['step']}")
        for k, v in item.items():
            if k == "step":
                continue
            lines.append(f"- {k}: {v}")
        lines.append("")
    lines.append("## final_state")
    lines.append(f"- turn: {result['final_state']['turn']}")
    lines.append(f"- turn_phase: {result['final_state']['turn_phase']}")
    lines.append(f"- game_phase: {result['final_state']['game_phase']}")
    lines.append(f"- current_player: {result['final_state']['current_player']}")
    lines.append(f"- winner: {result['final_state']['winner']}")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(json_path)
    print(md_path)


def main():
    summaries = []
    for count in (3, 4):
        result = run_game(count)
        write_outputs(result)
        errors = [item for item in result['trace'] if isinstance(item.get('result'), dict) and item['result'].get('error')]
        passed = result['final_state'].get('game_phase') == 'finished' and result['final_state'].get('winner') and not errors
        summaries.append({'player_count': count, 'passed': passed, 'error_count': len(errors), 'winner': result['final_state'].get('winner'), 'game_phase': result['final_state'].get('game_phase')})
    print(json.dumps({'summaries': summaries}, ensure_ascii=False))
    if not all(item['passed'] for item in summaries):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
