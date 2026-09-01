import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'support-cards'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card


SUPPORT_CASES = [
    {
        'card': '英美奧援',
        'resource': 'money',
        'expected_by_tier': {1: 1, 2: 2, 3: 3},
        'tier_setups': {
            1: ['北京'],
            2: ['東京', '臺北'],
            3: ['紐約'],
        },
        # 英美奧援實體上印有兩種 II 級門檻組合（歐洲/天方、東洋/臺灣），一張牌只印一組；
        # 這裡的 tier2 城鎮（東京=東洋、臺北=臺灣）對應第二組，需指定 variant_index=1，
        # 否則預設的第一組（歐洲/天方）不會被這兩個城鎮觸發（2026-07-16 使用者裁決）。
        'variant_by_tier': {2: 1},
    },
    {
        'card': '歐洲奧援',
        'resource': 'propaganda',
        'expected_by_tier': {1: 2, 2: 3, 3: 4},
        'tier_setups': {
            1: ['北京'],
            2: ['伯力', '伊斯坦堡'],
            3: ['巴黎'],
        },
    },
    {
        'card': '南洋奧援',
        'draw_expected_by_tier': {1: 1, 2: 1, 3: 2},
        'discard_expected_by_tier': {1: 2, 2: 1, 3: 1},  # includes played support card discard
        'tier_setups': {
            1: ['北京'],
            2: ['臺北', '東京'],
            3: ['新加坡'],
        },
    },
    {
        'card': '印度奧援',
        'red_discard_expected_by_tier': {1: 1, 2: 2, 3: 3},
        'expected_red_discard_name': '分神',
        'tier_setups': {
            1: ['北京'],
            2: ['新加坡', '紐約'],
            3: ['德里'],
        },
    },
]


def _new_game(card_name, org_towns, tier, variant_index=0):
    g = Game([('p1', 'player'), ('p2', 'red')])
    player, red = g.players
    player.id = 'p1'
    red.id = 'p2'
    player.faction_id = 'support_validator'
    player.base = org_towns[0]
    player.organizations = {town: 1 for town in org_towns}
    red.faction_id = 'red_army'
    red.base = '北京'
    red.organizations = {'北京': 1}
    red.hand = []
    red.deck.discard_pile = []
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.pending_choice = None
    g._deferred_auto_event = False
    noop_event = g._event_by_name('歲月靜好')
    g.current_event = dict(noop_event or {})
    g.event_progress = {'count': 0, 'required': 0, 'succeeded': True, 'settled': True, 'status': 'idle'}
    g.event_modifiers = []
    support = g._make_support_card(card_name, variant_index=variant_index)
    if card_name == '南洋奧援' and tier == 1:
        player.hand = [support, Card('保留手牌', 'command', {})]
    else:
        player.hand = [support]
    player.deck.draw_pile = [Card(f'補牌{i}', 'command', {}) for i in range(1, 5)]
    player.deck.discard_pile = []
    player.resources = {'money': 0, 'propaganda': 0}
    return g, player, red


def _support_log_contains(g, card_name, expected_tier):
    expected = f'resolved {card_name} at tier {expected_tier}'
    return any(expected in str(line) for line in getattr(g, 'action_log', []))


def _run_case(case, tier):
    card_name = case['card']
    variant_index = case.get('variant_by_tier', {}).get(tier, 0)
    g, player, red = _new_game(card_name, case['tier_setups'][tier], tier, variant_index=variant_index)
    detected_tier, region_index, matched = g._support_card_tier(player, player.hand[0])
    before = {
        'player_hand': len(player.hand),
        'player_discard': len(player.deck.discard_pile),
        'red_discard': len(red.deck.discard_pile),
        'money': player.resources['money'],
        'propaganda': player.resources['propaganda'],
        'draw_pile': len(player.deck.draw_pile),
    }
    result = g.play_card(0, mode='action')
    if card_name == '南洋奧援' and tier == 1 and result.get('pending_choice'):
        # I級「抽1張牌，再從所有手牌中棄掉1張牌」現在是玩家自選要棄哪張，不是寫死棄掉
        # 剛抽到的那張；這裡選擇棄掉剛抽到的補牌，驗證「保留手牌」不會被誤棄掉。
        pending = g.pending_choice or {}
        cards = pending.get('cards') or []
        discard_index = next(
            (i for i, c in enumerate(cards) if getattr(c, 'name', str(c)) != '保留手牌'),
            0,
        )
        result = g.resolve_pending_choice(player.id, discard_index)
    after = {
        'player_hand': len(player.hand),
        'player_discard': len(player.deck.discard_pile),
        'red_discard': len(red.deck.discard_pile),
        'money': player.resources['money'],
        'propaganda': player.resources['propaganda'],
        'draw_pile': len(player.deck.draw_pile),
        'red_discard_names': [getattr(c, 'name', str(c)) for c in red.deck.discard_pile],
        'player_hand_names': [getattr(c, 'name', str(c)) for c in player.hand],
        'player_discard_names': [getattr(c, 'name', str(c)) for c in player.deck.discard_pile],
    }

    if card_name == '南洋奧援' and tier == 1:
        # Tier 1 now resolves through an interactive discard choice, so it follows the
        # same logging convention as the other interactive support flows (a specific
        # completion message, not the generic "resolved X at tier Y" line — see
        # _resolve_support_flow_choice's build/dissolve branches for the same pattern).
        action_log_check = any('discarded' in str(line) and '南洋奧援' in str(line) for line in getattr(g, 'action_log', []))
    else:
        action_log_check = _support_log_contains(g, card_name, tier)

    checks = {
        'play_card_success': result.get('success') is True,
        'tier_detected': detected_tier == tier,
        'action_log_tier': action_log_check,
    }
    expected = {}

    if 'resource' in case:
        resource = case['resource']
        amount = case['expected_by_tier'][tier]
        expected[f'{resource}_delta'] = amount
        checks[f'{resource}_delta'] = after[resource] - before[resource] == amount
    elif card_name == '南洋奧援':
        draw_count = case['draw_expected_by_tier'][tier]
        discard_count = case['discard_expected_by_tier'][tier]
        expected['draw_count'] = draw_count
        expected['player_discard_delta'] = discard_count
        checks['draw_pile_delta'] = before['draw_pile'] - after['draw_pile'] == draw_count
        checks['player_discard_delta'] = after['player_discard'] - before['player_discard'] == discard_count
        if tier == 1:
            checks['draw_then_discard_net_hand'] = after['player_hand'] == 1
        else:
            checks['draw_hand_count'] = after['player_hand'] == draw_count
    elif card_name == '印度奧援':
        expected_count = case['red_discard_expected_by_tier'][tier]
        expected['red_discard_delta'] = expected_count
        checks['red_discard_delta'] = after['red_discard'] - before['red_discard'] == expected_count
        checks['red_discard_names'] = after['red_discard_names'] == [case['expected_red_discard_name']] * expected_count

    return {
        'name': f"{card_name}_tier{tier}",
        'card': card_name,
        'expected_tier': tier,
        'detected_tier': detected_tier,
        'region_index': region_index,
        'matched_rulers': matched,
        'org_towns': case['tier_setups'][tier],
        'expected': expected,
        'before': before,
        'after': after,
        'result': result,
        'action_log_tail': getattr(g, 'action_log', [])[-5:],
        'checks': checks,
        'ok': all(checks.values()),
    }


def main():
    results = []
    for case in SUPPORT_CASES:
        for tier in (1, 2, 3):
            results.append(_run_case(case, tier))

    summary = {
        'scope': ['英美奧援', '歐洲奧援', '南洋奧援', '印度奧援'],
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'SUPPORT_CARD_EFFECTS_RUNTIME_VALIDATION.json'
    md_path = RECORD_DIR / 'SUPPORT_CARD_EFFECTS_RUNTIME_VALIDATION.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    md_path.write_text(
        '# SUPPORT CARD EFFECTS RUNTIME VALIDATION\n\n'
        '可重跑指令：`python3 scripts/validate/validate_support_card_effects_runtime.py`\n\n'
        f"- scope: {', '.join(summary['scope'])}\n"
        f"- total: {summary['total']}\n"
        f"- passed: {summary['passed']}\n"
        f"- failed: {summary['failed']}\n\n"
        '## Results\n\n'
        + '\n'.join(
            f"- {'PASS' if r['ok'] else 'FAIL'} {r['name']}: "
            f"tier={r['detected_tier']} matched={json.dumps(r['matched_rulers'], ensure_ascii=False)} "
            f"checks={json.dumps(r['checks'], ensure_ascii=False)} "
            f"before={json.dumps(r['before'], ensure_ascii=False)} "
            f"after={json.dumps(r['after'], ensure_ascii=False)}"
            for r in results
        )
        + '\n',
        encoding='utf-8',
    )
    print(json.dumps(payload, ensure_ascii=False))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
