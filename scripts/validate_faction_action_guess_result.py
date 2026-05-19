import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'faction-ui'
sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game


def run_guess_case(action_name, faction_id, revealed_card, revealed_resources, guess, expected_hit, expected_reward):
    game = Game([('p1', 'P1'), ('p2', 'P2')])
    player = game.players[0]
    player.faction_id = faction_id
    player.hand = [Card('墊牌', 'money', {'money': 1})]
    player.deck.draw_pile = [Card(revealed_card, 'money', revealed_resources)]
    before_hand_count = len(player.hand)
    before_discard_count = len(player.deck.discard_pile)
    result = game._activated_faction_action(player, action_name, guess=guess)
    payload = result.get('result') or {}
    checks = {
        'success': result.get('success') is True,
        'result_name': payload.get('name') == action_name,
        'revealed_card': payload.get('revealed_card') == revealed_card,
        'cost_total': payload.get('cost_total') == sum(revealed_resources.values()),
        'guess': payload.get('guess') == guess,
        'hit': payload.get('hit') is expected_hit,
        'reward': payload.get('reward') == expected_reward,
        'destination': payload.get('destination') == 'discard',
        'state_flag': game.state().get('faction_action_used') is True,
        'hand_bottomed': len(player.hand) == before_hand_count - 1,
        'revealed_discarded': len(player.deck.discard_pile) == before_discard_count + 1 and player.deck.discard_pile[-1].name == revealed_card,
        'resource_money': player.resources.get('money') == expected_reward.get('money', 0),
        'resource_propaganda': player.resources.get('propaganda') == expected_reward.get('propaganda', 0),
    }
    return {
        'name': f'{action_name}_{guess}_{revealed_card}',
        'passed': all(checks.values()),
        'checks': checks,
        'result': result,
        'resources': dict(player.resources),
        'discard_pile': [card.name for card in player.deck.discard_pile],
    }


def check_static_result_text():
    app_js = (ROOT / 'static' / 'app.js').read_text(encoding='utf-8')
    checks = {
        'gambler_result_branch': "result.name === '賭徒耳語'" in app_js,
        'ethnic_result_branch': "result.name === '民族祭儀'" in app_js,
        'guess_text': '猜${guessText}' in app_js,
        'reward_text': "獲得 ${rewardParts.join('、')}" in app_js,
        'result_actions_include_guess_cards': "new Set(['立場試探', '賭徒耳語', '民族祭儀'])" in app_js,
        'aomen_modal_receives_result_html': "'將 1 張手牌放進牌庫底，猜牌庫頂牌購買費用奇偶；若猜中獲得 3 點宣傳與 3 點資金。',\n      factionResult.html" in app_js,
        'ethnic_modal_receives_result_html': "'猜中可獲得 2 點宣傳與 2 點資金；沒猜中則獲得 2 點宣傳。',\n      factionResult.html" in app_js,
        'placeholder_mentions_guess_result': '發動後會在此直接顯示猜測、翻牌與資源結果。' in app_js,
    }
    return {
        'name': 'static_modal_formats_guess_results',
        'passed': all(checks.values()),
        'checks': checks,
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    tests = [
        run_guess_case('賭徒耳語', 'aomen', '奇數牌', {'money': 1}, 'odd', True, {'money': 3, 'propaganda': 3}),
        run_guess_case('賭徒耳語', 'aomen', '偶數牌', {'money': 2}, 'odd', False, {'money': 0, 'propaganda': 0}),
        run_guess_case('民族祭儀', 'zhuang', '偶數牌', {'money': 2}, 'even', True, {'money': 2, 'propaganda': 2}),
        run_guess_case('民族祭儀', 'zhuang', '奇數牌', {'money': 1}, 'even', False, {'money': 0, 'propaganda': 2}),
        check_static_result_text(),
    ]
    failed = [test for test in tests if not test.get('passed')]
    payload = {
        'summary': {
            'total': len(tests),
            'passed': len(tests) - len(failed),
            'failed': len(failed),
        },
        'tests': tests,
    }
    (RECORD_DIR / 'FACTION_ACTION_GUESS_RESULT_VALIDATION.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    lines = [
        '# FACTION ACTION GUESS RESULT VALIDATION',
        '',
        f"- total: {payload['summary']['total']}",
        f"- passed: {payload['summary']['passed']}",
        f"- failed: {payload['summary']['failed']}",
        '',
        '驗證賭徒耳語與民族祭儀會回傳可供 UI 顯示的猜測、翻牌、命中與資源結果。',
        '',
    ]
    for test in tests:
        mark = 'PASS' if test.get('passed') else 'FAIL'
        lines.append(f"- [{mark}] {test['name']}")
    (RECORD_DIR / 'FACTION_ACTION_GUESS_RESULT_VALIDATION.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False))
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
