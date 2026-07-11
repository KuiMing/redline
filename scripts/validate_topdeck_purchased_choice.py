import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'action-cards'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card


def _new_game(card_name, purchased_names):
    g = Game([('p1', 'A'), ('p2', 'B')])
    a, b = g.players
    a.faction_id = 'liberals'
    b.faction_id = 'red_army'
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    purchased = [Card(n, 'command', {}) for n in purchased_names]
    a.deck.discard_pile = list(purchased)
    g.turn_log['purchased_cards_this_turn'] = list(purchased)
    a.hand = [Card(card_name, 'propaganda_special' if card_name == '行動預告' else 'money', {})]
    a.resources = {'money': 0, 'propaganda': 0}
    return g, a, purchased


def case_two_purchases_offers_choice():
    g, a, purchased = _new_game('行動預告', ['先買的牌', '後買的牌'])
    result = g.play_card(0, mode='action')
    pending = g.pending_choice or {}
    offered = [getattr(c, 'name', str(c)) for c in (pending.get('cards') or [])]
    checks = {
        'pending_choice_raised': result.get('pending_choice') is True,
        'choice_key': pending.get('choice_key') == 'topdeck_purchased_choice',
        'both_offered': sorted(offered) == ['先買的牌', '後買的牌'],
        'resource_not_granted_yet': a.resources['propaganda'] == 0,
    }
    idx = offered.index('先買的牌')  # 舊實作永遠自動選「後買的牌」；選先買的證明是真選擇
    resolved = g.resolve_pending_choice(a.id, idx)
    deck_top = getattr(a.deck.draw_pile[-1], 'name', '') if a.deck.draw_pile else ''
    discard_names = [getattr(c, 'name', str(c)) for c in a.deck.discard_pile]
    checks.update({
        'resolved': resolved.get('success') is True,
        'chosen_first_purchase_on_top': deck_top == '先買的牌',
        'other_purchase_stays_in_discard': '後買的牌' in discard_names,
        'remaining_effect_resumed_propaganda_plus_1': a.resources['propaganda'] == 1,
    })
    return {'name': 'two_purchases_player_chooses_which_to_topdeck', 'checks': checks, 'ok': all(checks.values())}


def case_single_purchase_auto():
    g, a, purchased = _new_game('行動募資', ['唯一買的牌'])
    result = g.play_card(0, mode='action')
    deck_top = getattr(a.deck.draw_pile[-1], 'name', '') if a.deck.draw_pile else ''
    checks = {
        'no_pending_choice': result.get('success') is True and not g.pending_choice,
        'auto_topdecked': deck_top == '唯一買的牌',
        'money_plus_1_applied': a.resources['money'] == 1,
    }
    return {'name': 'single_purchase_auto_topdeck_one_shot', 'checks': checks, 'ok': all(checks.values())}


def case_no_purchase_noop():
    g, a, purchased = _new_game('行動預告', [])
    result = g.play_card(0, mode='action')
    checks = {
        'success_without_choice': result.get('success') is True and not g.pending_choice,
        'resource_still_granted': a.resources['propaganda'] == 1,
        'noop_logged': any('no card bought this turn' in str(line) for line in g.action_log),
    }
    return {'name': 'no_purchase_noop_still_grants_resource', 'checks': checks, 'ok': all(checks.values())}


def case_end_turn_flow_with_two_purchases():
    # 回合結束提示流程（END phase 買完牌後系統詢問是否使用手上的行動預告）：
    # 買了 2 張時，選完要頂哪張才結束回合，且頂牌發生在補手牌之前
    from server.game import GamePhase
    g = Game([('p1', 'A'), ('p2', 'B')])
    a, b = g.players
    a.faction_id = 'liberals'
    b.faction_id = 'red_army'
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.END
    g.current_player_index = 0
    g.pending_base_choices = {}
    bought1, bought2 = Card('先買的牌', 'command', {}), Card('後買的牌', 'command', {})
    a.hand = [Card('行動預告', 'propaganda_special', {})]
    a.deck.draw_pile = [Card(f'補{i}', 'command', {}) for i in range(1, 8)]
    a.deck.discard_pile = [bought1, bought2]
    g.turn_log['purchased_cards_this_turn'] = [bought1, bought2]
    a.resources = {'money': 0, 'propaganda': 0}

    prompt = g.advance_turn_phase()
    use_index = next(i for i, o in enumerate((g.pending_choice or {}).get('options') or []) if o.get('action') != 'skip')
    used = g.resolve_pending_choice(a.id, use_index)
    pending = g.pending_choice or {}
    offered = [getattr(c, 'name', str(c)) for c in (pending.get('cards') or [])]
    checks = {
        'end_turn_prompted': prompt.get('pending_choice') is True,
        'use_returns_pending': used.get('pending_choice') is True,
        'turn_not_ended_yet': pending.get('choice_key') == 'topdeck_purchased_choice',
        'both_offered': sorted(offered) == ['先買的牌', '後買的牌'],
    }
    idx = offered.index('先買的牌')
    hand_before_refill = list(a.hand)
    resolved = g.resolve_pending_choice(a.id, idx)
    hand_names = [getattr(c, 'name', str(c)) for c in a.hand]
    checks.update({
        'resolved': resolved.get('success') is True,
        'no_dangling_choice': not g.pending_choice,
        'chosen_card_drawn_into_new_hand': '先買的牌' in hand_names,  # 頂牌後才補手牌
        # 回合結束流程：+1 資源在效果續跑時套用，隨後被 reset_turn() 正常歸零（與舊行為一致）
        'resources_reset_by_end_turn': a.resources['propaganda'] == 0,
    })
    return {'name': 'end_turn_flow_two_purchases_choice_then_end_turn', 'hand': hand_names, 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_two_purchases_offers_choice(),
        case_single_purchase_auto(),
        case_no_purchase_noop(),
        case_end_turn_flow_with_two_purchases(),
    ]
    summary = {
        'scope': ['行動預告', '行動募資'],
        'purpose': (
            'B3 remainder: topdeck_purchased_this_turn auto-picked the most recently bought '
            'card still in discard, with no player choice even though buy_card allows multiple '
            'purchases per turn and the card text says the player places "1張本回合購得的牌" '
            'on top. Now: 0 candidates = logged no-op; exactly 1 = auto (one-shot, unchanged '
            'UX); 2+ = pending card choice, and the card\'s remaining effects (the +1 '
            'resource) resume after the choice resolves via the stored remaining_effects '
            'context, matching the optional_trash resume pattern.'
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
