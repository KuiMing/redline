import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'action-cards'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card


def pin_noop_event(g):
    # Game 初始化會隨機抽該輪事件；抽到互動型事件會插入自己的 pending choice，
    # 污染這裡只想驗證卡片行為的測試。固定換成無效果的歲月靜好，與事件運氣脫鉤。
    g.current_event = dict(g._event_by_name('歲月靜好'))
    g.event_progress = {'count': 0, 'required': 0, 'succeeded': True, 'settled': True, 'status': 'idle'}
    g.event_modifiers = []
    g.pending_choice = None
    return g


def _new_game(card_name, purchased_names):
    g = Game([('p1', 'A'), ('p2', 'B')])
    a, b = g.players
    a.faction_id = 'liberals'
    b.faction_id = 'red_army'
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    pin_noop_event(g)
    purchased = [Card(n, 'command', {}) for n in purchased_names]
    a.deck.discard_pile = list(purchased)
    g.turn_log['purchased_cards_this_turn'] = list(purchased)
    a.hand = [Card(card_name, 'propaganda_special' if card_name == '行動預告' else 'money', {})]
    a.resources = {'money': 0, 'propaganda': 0}
    return g, a, purchased


def case_playing_card_banks_right_and_grants_resource_immediately():
    g, a, purchased = _new_game('行動預告', ['先買的牌', '後買的牌'])
    result = g.play_card(0, mode='action')
    checks = {
        'no_pending_choice_at_play_time': result.get('success') is True and not g.pending_choice,
        'resource_granted_immediately': a.resources['propaganda'] == 1,
        'right_banked': g.turn_log.get('pending_topdeck_uses') == 1,
        'purchases_untouched': {'先買的牌', '後買的牌'} <= {getattr(c, 'name', str(c)) for c in a.deck.discard_pile},
    }
    return {'name': 'playing_card_banks_right_and_grants_resource_immediately', 'checks': checks, 'ok': all(checks.values())}


def case_two_purchases_offers_choice_on_manual_use():
    g, a, purchased = _new_game('行動預告', ['先買的牌', '後買的牌'])
    g.play_card(0, mode='action')
    result = g.use_pending_topdeck_right()
    pending = g.pending_choice or {}
    offered = [getattr(c, 'name', str(c)) for c in (pending.get('cards') or [])]
    checks = {
        'pending_choice_raised': result.get('pending_choice') is True,
        'choice_key': pending.get('choice_key') == 'topdeck_purchased_choice',
        'both_offered': sorted(offered) == ['先買的牌', '後買的牌'],
        'right_already_spent': g.turn_log.get('pending_topdeck_uses') == 0,
    }
    idx = offered.index('先買的牌')  # 選先買的證明是真選擇，不是自動選最近一張
    resolved = g.resolve_pending_choice(a.id, idx)
    deck_top = getattr(a.deck.draw_pile[-1], 'name', '') if a.deck.draw_pile else ''
    discard_names = [getattr(c, 'name', str(c)) for c in a.deck.discard_pile]
    checks.update({
        'resolved': resolved.get('success') is True,
        'chosen_first_purchase_on_top': deck_top == '先買的牌',
        'other_purchase_stays_in_discard': '後買的牌' in discard_names,
        'turn_not_ended_by_manual_use': g.current_player_index == 0,
    })
    return {'name': 'two_purchases_player_chooses_which_to_topdeck', 'checks': checks, 'ok': all(checks.values())}


def case_single_purchase_auto():
    g, a, purchased = _new_game('行動募資', ['唯一買的牌'])
    g.play_card(0, mode='action')
    result = g.use_pending_topdeck_right()
    deck_top = getattr(a.deck.draw_pile[-1], 'name', '') if a.deck.draw_pile else ''
    checks = {
        'no_pending_choice': result.get('success') is True and not result.get('pending_choice') and not g.pending_choice,
        'auto_topdecked': deck_top == '唯一買的牌',
        'money_plus_1_applied_at_play_time': a.resources['money'] == 1,
        'right_consumed': g.turn_log.get('pending_topdeck_uses') == 0,
    }
    return {'name': 'single_purchase_auto_topdeck_one_shot', 'checks': checks, 'ok': all(checks.values())}


def case_no_purchase_use_errors_without_consuming_right():
    g, a, purchased = _new_game('行動預告', [])
    play_result = g.play_card(0, mode='action')
    use_result = g.use_pending_topdeck_right()
    checks = {
        'play_success_without_choice': play_result.get('success') is True and not g.pending_choice,
        'resource_still_granted': a.resources['propaganda'] == 1,
        'manual_use_errors': bool(use_result.get('error')),
        'right_not_consumed': g.turn_log.get('pending_topdeck_uses') == 1,
    }
    return {'name': 'no_purchase_use_errors_right_still_banked', 'checks': checks, 'ok': all(checks.values())}


def case_two_cards_played_stack_independent_rights():
    g, a, purchased = _new_game('行動預告', [])
    a.hand = [Card('行動預告', 'propaganda_special', {}), Card('行動預告', 'propaganda_special', {})]
    g.play_card(0, mode='action')
    g.play_card(0, mode='action')
    bought1, bought2 = Card('先買的牌', 'command', {}), Card('後買的牌', 'command', {})
    a.deck.discard_pile = [bought1, bought2]
    g.turn_log['purchased_cards_this_turn'] = [bought1, bought2]

    checks = {
        'two_rights_banked': g.turn_log.get('pending_topdeck_uses') == 2,
        'two_propaganda_granted': a.resources['propaganda'] == 2,
    }
    first = g.use_pending_topdeck_right()
    offered = [getattr(c, 'name', str(c)) for c in (g.pending_choice or {}).get('cards') or []]
    g.resolve_pending_choice(a.id, offered.index('先買的牌'))
    checks['first_use_placed_chosen_card'] = getattr(a.deck.draw_pile[-1], 'name', '') == '先買的牌'
    checks['one_right_remaining'] = g.turn_log.get('pending_topdeck_uses') == 1

    second = g.use_pending_topdeck_right()
    checks['second_use_auto_placed_last_candidate'] = second.get('success') is True and not second.get('pending_choice')
    checks['second_use_placed_remaining_card'] = getattr(a.deck.draw_pile[-1], 'name', '') == '後買的牌'
    checks['no_rights_remaining'] = g.turn_log.get('pending_topdeck_uses') == 0
    return {'name': 'two_cards_played_stack_independent_topdeck_rights', 'checks': checks, 'ok': all(checks.values())}


def case_end_turn_auto_drains_unused_right_with_two_purchases():
    # 回合結束時（END phase 按下結束回合）：若還有沒手動用掉的頂牌權利，系統自動跳出選擇，
    # 選完才真正結束回合、進入下一位玩家；補手牌會抽到剛頂上去的牌。
    from server.game import GamePhase
    g = Game([('p1', 'A'), ('p2', 'B')])
    a, b = g.players
    a.faction_id = 'liberals'
    b.faction_id = 'red_army'
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.END
    g.current_player_index = 0
    g.pending_base_choices = {}
    pin_noop_event(g)
    bought1, bought2 = Card('先買的牌', 'command', {}), Card('後買的牌', 'command', {})
    a.hand = [Card('Filler', 'command', {})]
    a.deck.draw_pile = [Card(f'補{i}', 'command', {}) for i in range(1, 8)]
    a.deck.discard_pile = [bought1, bought2]
    g.turn_log['purchased_cards_this_turn'] = [bought1, bought2]
    g.turn_log['pending_topdeck_uses'] = 1
    a.resources = {'money': 0, 'propaganda': 0}

    prompt = g.advance_turn_phase()
    pending = g.pending_choice or {}
    offered = [getattr(c, 'name', str(c)) for c in (pending.get('cards') or [])]
    checks = {
        'end_turn_auto_prompted': prompt.get('pending_choice') is True,
        'choice_key': pending.get('choice_key') == 'topdeck_purchased_choice',
        'both_offered': sorted(offered) == ['先買的牌', '後買的牌'],
    }
    idx = offered.index('先買的牌')
    resolved = g.resolve_pending_choice(a.id, idx)
    hand_names = [getattr(c, 'name', str(c)) for c in a.hand]
    checks.update({
        'resolved': resolved.get('success') is True,
        'no_dangling_choice': not g.pending_choice,
        'chosen_card_drawn_into_new_hand': '先買的牌' in hand_names,  # 頂牌後才補手牌
        'turn_passed_to_next_player': g.current_player_index == 1,
    })
    return {'name': 'end_turn_auto_drains_unused_right_with_two_purchases', 'hand': hand_names, 'checks': checks, 'ok': all(checks.values())}


def case_end_turn_drops_right_with_no_candidates():
    from server.game import GamePhase
    g = Game([('p1', 'A'), ('p2', 'B')])
    a, b = g.players
    a.faction_id = 'liberals'
    b.faction_id = 'red_army'
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.END
    g.current_player_index = 0
    g.pending_base_choices = {}
    pin_noop_event(g)
    a.hand = [Card('Filler', 'command', {})]
    a.deck.draw_pile = [Card(f'補{i}', 'command', {}) for i in range(1, 8)]
    a.deck.discard_pile = []
    g.turn_log['purchased_cards_this_turn'] = []
    g.turn_log['pending_topdeck_uses'] = 1

    result = g.advance_turn_phase()
    checks = {
        'no_pending_choice': not result.get('pending_choice'),
        'turn_still_completes': g.current_player_index == 1,
        'dropped_right_logged': any('沒有可頂的牌，作廢' in line for line in g.action_log),
    }
    return {'name': 'end_turn_drops_right_with_no_candidates_without_blocking_turn', 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_playing_card_banks_right_and_grants_resource_immediately(),
        case_two_purchases_offers_choice_on_manual_use(),
        case_single_purchase_auto(),
        case_no_purchase_use_errors_without_consuming_right(),
        case_two_cards_played_stack_independent_rights(),
        case_end_turn_auto_drains_unused_right_with_two_purchases(),
        case_end_turn_drops_right_with_no_candidates(),
    ]
    summary = {
        'scope': ['行動預告', '行動募資'],
        'purpose': (
            '2026-08-07 使用者要求改版：打出行動預告/行動募資時立刻拿到宣傳/資金（本回合可花用），'
            '頂牌對象改為玩家主動觸發的獨立動作（use_pending_topdeck_right），可在購買後、回合結束前'
            '任何時間點使用；同回合打出多張各自累積成獨立的頂牌權利，可分次使用；沒手動用掉的權利在'
            '結束回合時自動逐一跳出選擇，沒有候選牌時則作廢、不卡住回合。'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'TOPDECK_PURCHASED_CHOICE_VALIDATION_20260711.json'
    md_path = RECORD_DIR / 'TOPDECK_PURCHASED_CHOICE_VALIDATION_20260711.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 行動預告/行動募資 頂牌選擇驗證\n\n'
        '可重跑指令：`python3 scripts/validate_topdeck_purchased_choice.py`\n\n'
        f"- total: {summary['total']} / passed: {summary['passed']} / failed: {summary['failed']}\n\n"
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
