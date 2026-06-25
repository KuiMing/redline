import csv
import json
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from server import main
from server.game import STATIC_PURCHASE_CARD_SUPPLY

OUT_JSON = BASE / 'docs' / 'records' / 'purchase' / 'STATIC_PURCHASE_INITIAL_SUPPLY_VALIDATION.json'
OUT_MD = BASE / 'docs' / 'records' / 'purchase' / 'STATIC_PURCHASE_INITIAL_SUPPLY_VALIDATION.md'
RAW_ACTION_CSV = BASE / 'data' / 'raw' / 'action_cards.csv'


def raw_static_counts():
    with RAW_ACTION_CSV.open(encoding='utf-8') as f:
        rows = csv.DictReader(f)
        return {
            row['行動卡名稱']: int(row['卡牌張數'])
            for row in rows
            if row.get('行動卡名稱') in STATIC_PURCHASE_CARD_SUPPLY
        }


def reset_lobby_state():
    main.lobby.clear()
    main.lobby_hosts.clear()
    main.lobby_factions.clear()
    main.lobby_bases.clear()
    main.lobby_ready.clear()
    main.lobby_market_mode.clear()
    main.manager.games.clear()
    main.manager.connections.clear()


def create_formal_game(selections):
    reset_lobby_state()
    room = main.create_room()
    game_id = room['game_id']
    host_id = room['host_id']
    player_ids = [host_id]
    for idx in range(1, len(selections)):
        res = main.join_game({'game_id': game_id, 'name': f'P{idx + 1}'})
        assert 'error' not in res, res
        player_ids.append(res['player_id'])

    for pid, selection in zip(player_ids, selections):
        payload = {
            'game_id': game_id,
            'player_id': pid,
            'faction_id': selection['faction_id'],
        }
        if selection.get('base_name'):
            payload['base_name'] = selection['base_name']
        chosen = main.choose_faction(payload)
        assert 'error' not in chosen, {'payload': payload, 'result': chosen}
        ready = main.set_ready({'game_id': game_id, 'player_id': pid, 'ready': True})
        assert 'error' not in ready, ready

    started = main.start_game({'game_id': game_id, 'player_id': host_id})
    assert 'error' not in started, started
    return main.manager.games[game_id]


def names(cards):
    return [getattr(card, 'name', str(card)) for card in cards]


def check(name, passed, details):
    return {'name': name, 'passed': bool(passed), 'details': details}


def run_checks():
    raw_counts = raw_static_counts()
    checks = []

    checks.append(check(
        'static_supply_constants_match_raw_card_counts',
        raw_counts == STATIC_PURCHASE_CARD_SUPPLY,
        {
            'rule': '常設購買區總張數以 data/raw/action_cards.csv「卡牌張數」為準。',
            'raw_counts': raw_counts,
            'runtime_constants': STATIC_PURCHASE_CARD_SUPPLY,
        },
    ))

    game = create_formal_game([
        {'faction_id': 'red_army', 'base_name': '北京'},
        {'faction_id': 'taiwan_green', 'base_name': '臺北'},
    ])
    checks.append(check(
        'formal_start_without_setup_static_cards_uses_full_initial_supply',
        game.static_purchase_supply == STATIC_PURCHASE_CARD_SUPPLY,
        {
            'rule': '沒有起始額外常設牌的正式開局，常設供應應等於原始總張數。',
            'purchase_area_static_slots': game.state()['purchase_area'][:6],
            'static_purchase_supply': game.static_purchase_supply,
            'expected': STATIC_PURCHASE_CARD_SUPPLY,
        },
    ))

    game = create_formal_game([
        {'faction_id': 'red_army', 'base_name': '北京'},
        {'faction_id': 'hong_kong', 'base_name': '香港城'},
        {'faction_id': 'tibet_family', 'base_name': '達蘭薩拉'},
        {'faction_id': 'uyghur_family', 'base_name': '慕尼黑'},
    ])
    expected = dict(STATIC_PURCHASE_CARD_SUPPLY)
    expected['宣傳家'] -= 5  # 香港 1 + 達蘭薩拉 2 + 慕尼黑 2
    discards = {p.faction_id: names(p.deck.discard_pile) for p in game.players}
    checks.append(check(
        'formal_start_setup_propagandists_decrement_static_supply_once_after_lobby_override',
        game.static_purchase_supply == expected
        and discards.get('hong_kong', []).count('宣傳家') == 1
        and discards.get('tibet_dharamsala', []).count('宣傳家') == 2
        and discards.get('uyghur_munich', []).count('宣傳家') == 2,
        {
            'rule': '正式 lobby 開局套用陣營/根據地後，起始額外宣傳家要從常設供應扣除，且不可受 Game() 隨機初始陣營二次影響。',
            'static_purchase_supply': game.static_purchase_supply,
            'expected': expected,
            'player_discards': discards,
        },
    ))

    game = create_formal_game([
        {'faction_id': 'red_army', 'base_name': '北京'},
        {'faction_id': 'minyun', 'base_name': '巴黎'},
    ])
    expected = dict(STATIC_PURCHASE_CARD_SUPPLY)
    expected['資助者'] -= 1
    discards = {p.faction_id: names(p.deck.discard_pile) for p in game.players}
    checks.append(check(
        'formal_start_setup_patron_decrements_static_supply',
        game.static_purchase_supply == expected
        and discards.get('minyun', []).count('資助者') == 1,
        {
            'rule': '各界資助起始額外資助者也消耗常設供應。',
            'static_purchase_supply': game.static_purchase_supply,
            'expected': expected,
            'player_discards': discards,
        },
    ))

    return checks


def write_reports(checks):
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        'total': len(checks),
        'passed': sum(1 for c in checks if c['passed']),
        'failed': sum(1 for c in checks if not c['passed']),
    }
    payload = {
        'generated_at': date.today().isoformat(),
        'rule_area': 'static_purchase_initial_supply',
        'summary': summary,
        'checks': checks,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    lines = [
        '# Static Purchase Initial Supply Validation',
        '',
        f"Generated: {payload['generated_at']}",
        '',
        f"Summary: {summary['passed']}/{summary['total']} passed",
        '',
    ]
    for c in checks:
        lines.append(f"## {'PASS' if c['passed'] else 'FAIL'} — {c['name']}")
        lines.append('')
        lines.append('```json')
        lines.append(json.dumps(c['details'], ensure_ascii=False, indent=2))
        lines.append('```')
        lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    return summary


def main_cli():
    checks = run_checks()
    summary = write_reports(checks)
    print(json.dumps({'summary': summary, 'reports': [str(OUT_JSON), str(OUT_MD)]}, ensure_ascii=False))
    return 0 if summary['failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main_cli())
