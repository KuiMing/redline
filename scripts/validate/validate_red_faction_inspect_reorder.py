import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'faction-ui'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card

ABILITY = '紅軍派系'


def _new_game(faction_id='reform_opening'):
    g = Game([('p1', 'player'), ('p2', 'other')])
    a, b = g.players
    a.id = 'p1'
    b.id = 'p2'
    a.faction_id = faction_id
    b.faction_id = 'liberals'
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    a.hand = []
    # draw_pile 末端是牌庫頂：頂 -> 牌A、牌B、牌C（由頂往下）
    a.deck.draw_pile = [Card('牌E', 'command', {}), Card('牌D', 'command', {}), Card('牌C', 'command', {}), Card('牌B', 'command', {}), Card('牌A', 'command', {})]
    a.deck.discard_pile = []
    return g, a, b


def test_reorder_and_draw():
    g, a, b = _new_game()
    result = g._activated_faction_action(a, ABILITY)
    pending = g.pending_choice or {}
    inspected_names = [getattr(c, 'name', str(c)) for c in (pending.get('cards') or [])]
    checks = {
        'action_pending': result.get('pending_choice') is True,
        'ability_used_flag': g.turn_log.get('faction_action_used') is True,
        'inspected_top_three': inspected_names == ['牌A', '牌B', '牌C'],
        'choice_key_reused': pending.get('choice_key') == 'era_inspect_deck_top_and_reorder',
    }
    # 依序選 牌C、牌A、牌B：牌C 成為新的牌庫頂（會被隨後的抽1張拿走），之後頂部依序為 牌A、牌B
    order = [inspected_names.index('牌C'), inspected_names.index('牌A'), inspected_names.index('牌B')]
    resolved = g.resolve_pending_choice(a.id, order)
    hand_names = [getattr(c, 'name', str(c)) for c in a.hand]
    top_after = [getattr(c, 'name', str(c)) for c in reversed(a.deck.draw_pile)][:2]
    checks.update({
        'resolve_success': resolved.get('success') is True,
        'drew_one_card': resolved.get('drawn_cards') == ['牌C'] and hand_names == ['牌C'],
        'deck_top_matches_chosen_order': top_after == ['牌A', '牌B'],
        'no_stray_era_log': not g.turn_log.get('era_effects_applied'),
    })
    return {'name': 'reorder_and_draw', 'resolved': resolved, 'hand': hand_names, 'top_after': top_after, 'checks': checks, 'ok': all(checks.values())}


def test_once_per_turn():
    g, a, b = _new_game()
    g._activated_faction_action(a, ABILITY)
    order = [0, 1, 2]
    g.resolve_pending_choice(a.id, order)
    second = g._activated_faction_action(a, ABILITY)
    checks = {'second_use_blocked': second.get('error') == 'Faction action already used this turn'}
    return {'name': 'once_per_turn', 'second': second, 'checks': checks, 'ok': all(checks.values())}


def test_ownership_gate():
    g, a, b = _new_game(faction_id='liberals')  # liberals 沒有紅軍派系
    result = g._activated_faction_action(a, ABILITY)
    g2, a2, b2 = _new_game(faction_id='reform_opening')
    ritual = g2._activated_faction_action(a2, '民族祭儀', guess='odd')  # reform_opening 沒有民族祭儀
    checks = {
        'wrong_faction_blocked': result.get('error') == "Player's faction does not have this ability",
        'ethnic_ritual_blocked_for_wrong_faction': ritual.get('error') == "Player's faction does not have this ability",
    }
    return {'name': 'ownership_gate', 'result': result, 'ritual': ritual, 'checks': checks, 'ok': all(checks.values())}


def test_short_deck():
    g, a, b = _new_game()
    a.deck.draw_pile = [Card('唯二B', 'command', {}), Card('唯二A', 'command', {})]
    result = g._activated_faction_action(a, ABILITY)
    pending = g.pending_choice or {}
    inspected = [getattr(c, 'name', str(c)) for c in (pending.get('cards') or [])]
    resolved = g.resolve_pending_choice(a.id, [1, 0])  # 唯二B 放頂（被抽走），唯二A 次之
    hand = [getattr(c, 'name', str(c)) for c in a.hand]
    checks = {
        'inspected_two_only': inspected == ['唯二A', '唯二B'],
        'resolved': resolved.get('success') is True,
        'drew_new_top': hand == ['唯二B'],
        'remaining_deck': [getattr(c, 'name', str(c)) for c in a.deck.draw_pile] == ['唯二A'],
    }
    return {'name': 'short_deck', 'checks': checks, 'ok': all(checks.values())}


def test_existing_abilities_still_pass_ownership_gate():
    # 回歸：既有 activated 能力（正確陣營）不被新的歸屬檢查誤擋
    g, a, b = _new_game(faction_id='liberals')
    a.deck.draw_pile = [Card('奇數牌', 'money', {'money': 1})]
    g._top_card_cost_total = lambda card: 1
    probe = g._activated_faction_action(a, '立場試探')
    g2, a2, b2 = _new_game(faction_id='zhuang')
    a2.hand = [Card('墊牌', 'money', {'money': 1})]
    a2.deck.draw_pile = [Card('奇數牌', 'money', {'money': 1})]
    g2._top_card_cost_total = lambda card: 1
    ritual = g2._activated_faction_action(a2, '民族祭儀', guess='odd')
    checks = {
        'liberals_probe_ok': probe.get('success') is True,
        'zhuang_ritual_ok': ritual.get('success') is True,
    }
    return {'name': 'existing_abilities_still_pass_ownership_gate', 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        test_reorder_and_draw(),
        test_once_per_turn(),
        test_ownership_gate(),
        test_short_deck(),
        test_existing_abilities_still_pass_ownership_gate(),
    ]
    summary = {
        'scope': [ABILITY, 'faction-action ownership gate'],
        'purpose': (
            'reform_opening\'s 【紅軍派系】 ("每回合可檢視1次牌庫頂3張牌，將其以任意順序放回牌庫頂，'
            '並抽1張牌") had no implementation: the ability name was missing from '
            '_resolve_ability_text and _activated_faction_action had no branch for it. '
            'Implemented by reusing the existing era_inspect_deck_top_and_reorder multi-card '
            'choice with a draw_after_reorder context flag. Also added a backend ability-'
            'ownership gate to _activated_faction_action (previously ANY faction could invoke '
            'any named non-red faction action via WebSocket; only the frontend filtered by '
            'faction), and added 民族祭儀 to the ability-name mapping so its existing runtime '
            'branch passes the new gate for its 12 factions.'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'RED_FACTION_INSPECT_REORDER_VALIDATION_20260711.json'
    md_path = RECORD_DIR / 'RED_FACTION_INSPECT_REORDER_VALIDATION_20260711.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 紅軍派系（改革開放派）實作驗證\n\n'
        '可重跑指令：`python3 scripts/validate/validate_red_faction_inspect_reorder.py`\n\n'
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
