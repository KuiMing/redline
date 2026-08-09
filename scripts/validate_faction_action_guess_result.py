import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'faction-ui'
sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game


def _structured_card(game, name):
    entry = next(c for c in game.structured_cards if c['name'] == name)
    return Card(entry['name'], entry['type'], dict(entry.get('resources', {})))


def run_guess_case(action_name, faction_id, revealed_card, expected_cost_total, guess,
                   expected_hit, expected_reward, miss_reward_index=None,
                   extra_hand=None, bottom_card_name=None):
    # 2026-08-09 使用者 playtest 回報並更正：這三個能力猜的是牌庫頂牌的「購買費用」
    # （購買區標價），不是打出後拿到的印刷資源；改用真實購買區卡牌（購買費用與印刷
    # 資源刻意不同奇偶，見下方 main() 的選牌註解）驅動，不再用亂編卡名＋任意資源
    # 字典湊出奇偶——那樣寫法即使 `_top_card_cost_total` 曾經誤看資源而非購買費用，
    # 也會因為亂編卡名查無購買費用（fallback 為 0）而巧合通過，測不出真正的回歸。
    game = Game([('p1', 'P1'), ('p2', 'P2')])
    player = game.players[0]
    player.faction_id = faction_id
    player.hand = [Card('墊牌', 'money', {'money': 1})] + [Card(n, 'command', {}) for n in (extra_hand or [])]
    player.deck.draw_pile = [Card('Bottom', 'command', {}), _structured_card(game, revealed_card)]
    player.deck.discard_pile = []
    expected_bottom = bottom_card_name or '墊牌'
    before_hand_count = len(player.hand)
    before_discard_count = len(player.deck.discard_pile)
    result = game._activated_faction_action(player, action_name, guess=guess)

    # 多張手牌時，能力文字「將1張手牌放進牌庫底」由玩家選擇要墊哪一張
    bottom_choice_offered = False
    if result.get('pending_choice') and (game.pending_choice or {}).get('choice_key') == 'guess_ability_bottom_card':
        bottom_choice_offered = True
        cards = game.pending_choice.get('cards') or []
        idx = next(i for i, c in enumerate(cards) if getattr(c, 'name', str(c)) == expected_bottom)
        result = game.resolve_pending_choice(player.id, idx)

    # 民族祭儀沒猜中：「獲得2點宣傳或2點資金」二選一
    miss_choice_offered = False
    if result.get('pending_choice') and (game.pending_choice or {}).get('choice_key') == 'ethnic_ritual_miss_reward':
        miss_choice_offered = True
        result = game.resolve_pending_choice(player.id, miss_reward_index or 0)

    payload = result.get('result') or {}
    checks = {
        'success': result.get('success') is True,
        'result_name': payload.get('name') == action_name,
        'revealed_card': payload.get('revealed_card') == revealed_card,
        'cost_total': payload.get('cost_total') == expected_cost_total,
        'guess': payload.get('guess') == guess,
        'hit': payload.get('hit') is expected_hit,
        'reward': payload.get('reward') == expected_reward,
        # 能力文字只說「展示」牌庫頂牌：看完放回牌庫頂
        'destination': payload.get('destination') == 'deck_top',
        'state_flag': game.state().get('faction_action_used') is True,
        'hand_bottomed': len(player.hand) == before_hand_count - 1,
        'revealed_topdecked': bool(player.deck.draw_pile) and player.deck.draw_pile[-1].name == revealed_card
                              and len(player.deck.discard_pile) == before_discard_count,
        'bottom_card_at_deck_bottom': bool(player.deck.draw_pile) and player.deck.draw_pile[0].name == expected_bottom,
        'resource_money': player.resources.get('money') == expected_reward.get('money', 0),
        'resource_propaganda': player.resources.get('propaganda') == expected_reward.get('propaganda', 0),
    }
    if extra_hand:
        checks['bottom_choice_offered'] = bottom_choice_offered
        checks['unchosen_card_kept_in_hand'] = '墊牌' in [c.name for c in player.hand]
    if action_name == '民族祭儀' and not expected_hit:
        checks['miss_reward_choice_offered'] = miss_choice_offered
    return {
        'name': f'{action_name}_{guess}_{revealed_card}'
                + (f'_bottom-{expected_bottom}' if extra_hand else '')
                + (f'_missidx{miss_reward_index}' if miss_reward_index is not None else ''),
        'passed': all(checks.values()),
        'checks': checks,
        'result': result,
        'resources': dict(player.resources),
        'deck_pile': [card.name for card in player.deck.draw_pile],
        'discard_pile': [card.name for card in player.deck.discard_pile],
    }


def check_static_result_text():
    app_js = (ROOT / 'static' / 'app.js').read_text(encoding='utf-8')
    checks = {
        'gambler_result_branch': "result.name === '賭徒耳語'" in app_js,
        'ethnic_result_branch': "result.name === '民族祭儀'" in app_js,
        'guess_text': '猜${guessText}' in app_js,
        'reward_text': "獲得 ${rewardParts.join('、')}" in app_js,
        'result_actions_include_guess_cards': "'立場試探', '賭徒耳語', '民族祭儀'" in app_js,
        'aomen_modal_receives_result_html': "'將 1 張手牌放進牌庫底，猜牌庫頂牌購買費用奇偶；若猜中獲得 3 點宣傳與 3 點資金。',\n      factionResult.html" in app_js,
        'ethnic_modal_receives_result_html': "'猜中可獲得 2 點宣傳與 2 點資金；沒猜中則獲得 2 點宣傳或 2 點資金（二選一）。',\n      factionResult.html" in app_js,
        'placeholder_mentions_guess_result': '發動後會在此直接顯示猜測、翻牌與資源結果。' in app_js,
    }
    return {
        'name': 'static_modal_formats_guess_results',
        'passed': all(checks.values()),
        'checks': checks,
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    # 宣傳家：購買費用 0+3=3（奇數），印刷資源 2（偶數）——刻意選一張購買費用與印刷資源
    # 奇偶不同的牌，才能真正測出「猜的是購買費用」而不是不小心測到印刷資源。
    # 乘勝追擊：購買費用 2+0=2（偶數），印刷資源 1（奇數），同理。
    tests = [
        run_guess_case('賭徒耳語', 'aomen', '宣傳家', 3, 'odd', True, {'money': 3, 'propaganda': 3}),
        run_guess_case('賭徒耳語', 'aomen', '乘勝追擊', 2, 'odd', False, {'money': 0, 'propaganda': 0}),
        run_guess_case('民族祭儀', 'zhuang', '乘勝追擊', 2, 'even', True, {'money': 2, 'propaganda': 2}),
        run_guess_case('民族祭儀', 'zhuang', '宣傳家', 3, 'even', False, {'money': 0, 'propaganda': 2}, miss_reward_index=0),
        run_guess_case('民族祭儀', 'zhuang', '宣傳家', 3, 'even', False, {'money': 2, 'propaganda': 0}, miss_reward_index=1),
        run_guess_case('賭徒耳語', 'aomen', '宣傳家', 3, 'odd', True, {'money': 3, 'propaganda': 3},
                       extra_hand=['要墊底的牌'], bottom_card_name='要墊底的牌'),
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
        '驗證賭徒耳語與民族祭儀：猜的是牌庫頂牌的購買費用（不是印刷資源）、墊底手牌由玩家選擇、'
        '展示的頂牌放回牌庫頂、民族祭儀沒猜中提供「2宣傳或2資金」二選一，並回傳可供 UI 顯示的結果。',
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
