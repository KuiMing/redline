import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'action-cards'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card

# 謀劃：種類=指揮（command），購買費用=資金1+宣傳1，效果=抽2張牌。
# 種類分類跟「非暴力」無關，是典型「種類不是資金/宣傳，但購買費用同時有資金與宣傳」的代表卡，
# 用來驗證 played_money_card / played_propaganda_card 與四個陣營能力現在是看購買費用，不是看種類。
MISMATCH_CARD = '謀劃'


def _new_game(hand_cards, resources=None, faction_id='liberals'):
    g = Game([('p1', 'player'), ('p2', 'player2')])
    a, b = g.players
    a.id = 'p1'
    b.id = 'p2'
    a.faction_id = faction_id
    b.faction_id = 'liberals'
    b.hand = []
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    a.hand = hand_cards
    a.resources = resources or {'money': 0, 'propaganda': 0}
    a.deck.draw_pile = [Card(f'補牌{i}', 'command', {}) for i in range(1, 6)]
    return g, a, b


def test_ignite_passion_bonus_after_mismatched_category_card():
    g, a, b = _new_game([Card(MISMATCH_CARD, 'command', {}), Card('點燃熱情', 'command', {'propaganda': 1})])
    g.play_card(0, mode='action')  # 謀劃：cost has both money+propaganda, category is 指揮
    before = len(a.hand)
    result = g.play_card(0, mode='action')  # now hand[0] is 點燃熱情
    drawn = len(a.hand) - before + 1  # +1 accounts for 點燃熱情 itself leaving hand
    return {
        'name': 'ignite_passion_bonus_after_mismatched_category_card',
        'checks': {
            'play_success': result.get('success') is True,
            'drew_2_cards': drawn == 2,
        },
        'ok': result.get('success') is True and drawn == 2,
        'detail': {'drawn': drawn},
    }


def test_build_confidence_bonus_after_mismatched_category_card():
    g, a, b = _new_game([Card(MISMATCH_CARD, 'command', {}), Card('樹立信心', 'command', {'money': 1})])
    g.play_card(0, mode='action')
    before = len(a.hand)
    result = g.play_card(0, mode='action')
    drawn = len(a.hand) - before + 1
    return {
        'name': 'build_confidence_bonus_after_mismatched_category_card',
        'checks': {
            'play_success': result.get('success') is True,
            'drew_2_cards': drawn == 2,
        },
        'ok': result.get('success') is True and drawn == 2,
        'detail': {'drawn': drawn},
    }


def test_ignite_passion_no_bonus_without_qualifying_play():
    g, a, b = _new_game([Card('點燃熱情', 'command', {'propaganda': 1})])
    before = len(a.hand)
    result = g.play_card(0, mode='action')
    drawn = len(a.hand) - before + 1
    return {
        'name': 'ignite_passion_no_bonus_without_qualifying_play',
        'checks': {
            'play_success': result.get('success') is True,
            'drew_only_1_card': drawn == 1,
        },
        'ok': result.get('success') is True and drawn == 1,
        'detail': {'drawn': drawn},
    }


def test_support_card_counts_by_printed_purchase_cost():
    # 普通奧援印刷購買費用為 1資金+2宣傳，因此必須同時登記兩種費用組成；
    # 後續點燃熱情看見先前已打出宣傳費用卡，應抽本身 1 張再加成 1 張。
    g, a, b = _new_game([Card('英美奧援', 'support', {}), Card('點燃熱情', 'command', {'propaganda': 1})])
    a.resources = {'money': 1, 'propaganda': 2}
    g.play_card(0, mode='action')
    before = len(a.hand)
    result = g.play_card(0, mode='action')
    drawn = len(a.hand) - before + 1
    return {
        'name': 'support_card_counts_for_printed_purchase_cost_triggers',
        'checks': {
            'play_success': result.get('success') is True,
            'drew_2_cards_with_bonus': drawn == 2,
        },
        'ok': result.get('success') is True and drawn == 2,
        'detail': {'drawn': drawn},
    }


def _with_ability(g, ability_dict):
    g._player_effective_abilities = lambda player: [ability_dict]


def test_faction_ability_money_draw_triggers_on_mismatched_card():
    g, a, b = _new_game([Card(MISMATCH_CARD, 'command', {})])
    _with_ability(g, {'name': '商貿組織', 'type': 'triggered'})
    before = len(a.hand)
    result = g.play_card(0, mode='action')
    drawn = len(a.hand) - before + 1  # 謀劃 itself draws 2; ability adds +1 more = 3
    return {
        'name': 'faction_ability_商貿組織_triggers_on_mismatched_category_card',
        'checks': {
            'play_success': result.get('success') is True,
            'triggered_flag_set': g.turn_log.get('faction_first_money_triggered') is True,
            'drew_3_cards_total': drawn == 3,
        },
        'ok': (
            result.get('success') is True
            and g.turn_log.get('faction_first_money_triggered') is True
            and drawn == 3
        ),
        'detail': {'drawn': drawn},
    }


def test_faction_ability_money_gain_triggers_on_mismatched_card():
    g, a, b = _new_game([Card(MISMATCH_CARD, 'command', {})])
    _with_ability(g, {'name': '基金會', 'type': 'triggered'})
    before_money = a.resources['money']
    result = g.play_card(0, mode='action')
    return {
        'name': 'faction_ability_基金會_triggers_on_mismatched_category_card',
        'checks': {
            'play_success': result.get('success') is True,
            'triggered_flag_set': g.turn_log.get('faction_first_money_gain_triggered') is True,
            'gained_2_money': a.resources['money'] - before_money == 2,
        },
        'ok': (
            result.get('success') is True
            and g.turn_log.get('faction_first_money_gain_triggered') is True
            and a.resources['money'] - before_money == 2
        ),
    }


def test_faction_ability_propaganda_draw_triggers_on_mismatched_card():
    g, a, b = _new_game([Card(MISMATCH_CARD, 'command', {})])
    _with_ability(g, {'name': '民族調和', 'type': 'triggered'})
    before = len(a.hand)
    result = g.play_card(0, mode='action')
    drawn = len(a.hand) - before + 1
    return {
        'name': 'faction_ability_民族調和_triggers_on_mismatched_category_card',
        'checks': {
            'play_success': result.get('success') is True,
            'triggered_flag_set': g.turn_log.get('faction_first_propaganda_triggered') is True,
            'drew_3_cards_total': drawn == 3,
        },
        'ok': (
            result.get('success') is True
            and g.turn_log.get('faction_first_propaganda_triggered') is True
            and drawn == 3
        ),
        'detail': {'drawn': drawn},
    }


def test_faction_ability_propaganda_gain_triggers_on_mismatched_card():
    g, a, b = _new_game([Card(MISMATCH_CARD, 'command', {})])
    _with_ability(g, {'name': '人同此心', 'type': 'triggered'})
    before_prop = a.resources['propaganda']
    result = g.play_card(0, mode='action')
    return {
        'name': 'faction_ability_人同此心_triggers_on_mismatched_category_card',
        'checks': {
            'play_success': result.get('success') is True,
            'triggered_flag_set': g.turn_log.get('faction_first_prop_gain_triggered') is True,
            'gained_2_propaganda': a.resources['propaganda'] - before_prop == 2,
        },
        'ok': (
            result.get('success') is True
            and g.turn_log.get('faction_first_prop_gain_triggered') is True
            and a.resources['propaganda'] - before_prop == 2
        ),
    }


def test_faction_ability_still_triggers_after_reaction_skip():
    # Player A plays 謀劃 while holding 商貿組織; player B holds 情報網 and can react.
    # B skips the reaction (index 0) -> 謀劃 should resolve normally afterward, and
    # 商貿組織 should still trigger via the resumed (deferred) code path, which reads
    # cost_has_money/cost_has_propaganda from action_context rather than effective_type.
    g, a, b = _new_game([Card(MISMATCH_CARD, 'command', {})])
    b.hand = [Card('情報網', 'spy', {'money': 1, 'propaganda': 1})]
    _with_ability(g, {'name': '商貿組織', 'type': 'triggered'})
    before = len(a.hand)
    play_result = g.play_card(0, mode='action')
    reaction_choice = getattr(g, 'pending_choice', None) or {}
    resolved = g.resolve_pending_choice(b.id, 0)  # 0 = skip reaction
    drawn = len(a.hand) - before + 1
    return {
        'name': 'faction_ability_still_triggers_after_reaction_skip',
        'checks': {
            'reaction_prompt_raised': play_result.get('pending_choice') is True,
            'reaction_choice_type_correct': reaction_choice.get('type') == 'reaction_choice',
            'skip_resolved_success': resolved.get('success') is True,
            'skipped_reaction_flag': resolved.get('skipped_reaction') is True,
            'triggered_flag_set': g.turn_log.get('faction_first_money_triggered') is True,
            'drew_3_cards_total': drawn == 3,
        },
        'ok': (
            play_result.get('pending_choice') is True
            and reaction_choice.get('type') == 'reaction_choice'
            and resolved.get('success') is True
            and resolved.get('skipped_reaction') is True
            and g.turn_log.get('faction_first_money_triggered') is True
            and drawn == 3
        ),
        'detail': {'drawn': drawn, 'resolved': resolved},
    }


def main():
    tests = [
        test_ignite_passion_bonus_after_mismatched_category_card,
        test_build_confidence_bonus_after_mismatched_category_card,
        test_ignite_passion_no_bonus_without_qualifying_play,
        test_support_card_counts_by_printed_purchase_cost,
        test_faction_ability_money_draw_triggers_on_mismatched_card,
        test_faction_ability_money_gain_triggers_on_mismatched_card,
        test_faction_ability_propaganda_draw_triggers_on_mismatched_card,
        test_faction_ability_propaganda_gain_triggers_on_mismatched_card,
        test_faction_ability_still_triggers_after_reaction_skip,
    ]
    results = [t() for t in tests]

    summary = {
        'scope': ['點燃熱情', '樹立信心', '商貿組織', '基金會/共合會', '民族調和/星星之火', '人同此心'],
        'purpose': (
            'These 2 cards and 4 faction abilities all key off whether the played card\'s '
            'purchase cost includes a money/propaganda component ("購買費用有資金/宣傳的牌"), '
            'but server/game.py used to check the card\'s own category (card_type / '
            'effective_type) instead — a poor proxy, since many command/spy/organization/'
            'armed/transport-category cards have mixed money+propaganda costs (e.g. 謀劃: '
            'category=指揮, cost=資金1+宣傳1). Fixed by deriving cost_has_money/'
            'cost_has_propaganda from actual purchase cost via _card_purchase_cost, threaded '
            'through both the immediate play_card path and the deferred reaction-resume path '
            '(action_context); ordinary support cards count by their printed purchase cost, '
            'while starter 紅軍奧援 has zero purchase cost.'
        ),
        'mismatch_card_used': MISMATCH_CARD,
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'COST_COMPOSITION_TRIGGERS_FIX_VALIDATION_20260710.json'
    md_path = RECORD_DIR / 'COST_COMPOSITION_TRIGGERS_FIX_VALIDATION_20260710.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 點燃熱情/樹立信心/陣營能力購買費用觸發修正驗證\n\n'
        '可重跑指令：`python3 scripts/validate/validate_cost_composition_triggers.py`\n\n'
        f"- total: {summary['total']}\n"
        f"- passed: {summary['passed']}\n"
        f"- failed: {summary['failed']}\n\n"
        '## Results\n\n'
        + '\n'.join(
            f"- {'PASS' if r['ok'] else 'FAIL'} {r['name']}: checks={json.dumps(r['checks'], ensure_ascii=False)}"
            for r in results
        )
        + '\n',
        encoding='utf-8',
    )
    print(json.dumps(payload, ensure_ascii=False, default=str))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
