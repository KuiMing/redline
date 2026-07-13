import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'playtest-flow'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase, CANCELLABLE_CHOICE_KEYS
from server.cards import Card


def _red_game(hand=2, opp_org='臺北'):
    g = Game([('p1', 'red'), ('p2', 'opp')])
    red, opp = g.players
    red.faction_id = 'red_army'
    opp.faction_id = 'liberals'
    red.base = '北京'
    red.organizations = {'北京': 1, '天津': 1}
    opp.base = opp_org
    opp.organizations = {opp_org: 1}
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    red.hand = [Card(f'手牌{i+1}', 'command', {}) for i in range(hand)]
    return g, red, opp


def case_ccdi_cancellable_and_cancel_does_not_consume():
    g, red, _ = _red_game()
    g._activated_faction_action(red, '中紀委')
    st = g.state(red.id)['pending_choice']
    cancel = g.cancel_pending_choice(red.id)
    checks = {
        'pending_is_ccdi': st['choice_key'] == 'red_army_ccdi_discard_draw',
        'state_flag_cancellable': st['cancellable'] is True,
        'cancel_succeeded': cancel.get('success') is True,
        'pending_cleared': g.pending_choice is None,
        'ability_not_consumed': g._red_army_action_count() == 0,
        'hand_untouched': [c.name for c in red.hand] == ['手牌1', '手牌2'],
    }
    return {'name': 'ccdi_cancel_reverts_cleanly_without_consuming', 'checks': checks, 'ok': all(checks.values())}


def case_propaganda_and_state_security_cancellable():
    g, red, opp = _red_game()
    g._activated_faction_action(red, '政工部')
    prop = g.state(red.id)['pending_choice']
    g.cancel_pending_choice(red.id)
    g2, red2, opp2 = _red_game()
    opp2.organizations = {'瀋陽': 1}
    g2._activated_faction_action(red2, '國安部')
    sec = g2.state(red2.id)['pending_choice']
    checks = {
        'propaganda_key': prop['choice_key'] == 'red_army_propaganda_department_target',
        'propaganda_cancellable': prop['cancellable'] is True,
        'state_security_key': sec['choice_key'] == 'red_army_state_security_target',
        'state_security_cancellable': sec['cancellable'] is True,
    }
    return {'name': 'propaganda_and_state_security_are_cancellable', 'checks': checks, 'ok': all(checks.values())}


def case_reactivate_after_cancel():
    g, red, _ = _red_game()
    g._activated_faction_action(red, '中紀委')
    g.cancel_pending_choice(red.id)
    # ability can be triggered again (not stuck / not marked used)
    again = g._activated_faction_action(red, '中紀委')
    checks = {
        're_triggers_pending': again.get('pending_choice') is True,
        'still_not_consumed_before_resolve': g._red_army_action_count() == 0,
    }
    return {'name': 'cancelled_ability_can_be_reactivated', 'checks': checks, 'ok': all(checks.values())}


def case_resolve_zero_still_consumes():
    # "confirm 0 cards" is distinct from cancel: it DOES consume the ability.
    g, red, _ = _red_game()
    g._activated_faction_action(red, '中紀委')
    resolved = g.resolve_pending_choice(red.id, [])
    checks = {
        'resolve_ok': resolved.get('success') is True,
        'ability_consumed': g._red_army_action_count() == 1,
    }
    return {'name': 'confirm_zero_cards_consumes_unlike_cancel', 'checks': checks, 'ok': all(checks.values())}


def case_mandatory_choice_not_cancellable():
    g, red, _ = _red_game()
    g.pending_choice = {'type': 'card_choice', 'choice_key': 'event_discard_self', 'player_id': red.id, 'cards': []}
    st = g.state(red.id)['pending_choice']
    cancel = g.cancel_pending_choice(red.id)
    checks = {
        'state_flag_not_cancellable': st['cancellable'] is False,
        'cancel_rejected': cancel.get('error') == 'This choice cannot be cancelled',
        'pending_still_present': g.pending_choice is not None,
    }
    return {'name': 'mandatory_choice_cannot_be_cancelled', 'checks': checks, 'ok': all(checks.values())}


def case_cancel_rejects_other_players_choice():
    g, red, opp = _red_game()
    g._activated_faction_action(red, '中紀委')
    cancel = g.cancel_pending_choice(opp.id)
    checks = {
        'rejected_not_your_choice': cancel.get('error') == 'Not your pending choice',
        'pending_still_present': g.pending_choice is not None,
    }
    return {'name': 'cannot_cancel_another_players_choice', 'checks': checks, 'ok': all(checks.values())}


def case_only_three_keys_are_cancellable():
    checks = {
        'exactly_the_three_red_army_abilities': set(CANCELLABLE_CHOICE_KEYS) == {
            'red_army_ccdi_discard_draw',
            'red_army_propaganda_department_target',
            'red_army_state_security_target',
        },
    }
    return {'name': 'cancellable_set_is_scoped_to_the_three_abilities', 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_ccdi_cancellable_and_cancel_does_not_consume(),
        case_propaganda_and_state_security_cancellable(),
        case_reactivate_after_cancel(),
        case_resolve_zero_still_consumes(),
        case_mandatory_choice_not_cancellable(),
        case_cancel_rejects_other_players_choice(),
        case_only_three_keys_are_cancellable(),
    ]
    summary = {
        'scope': ['可取消 pending choice'],
        'purpose': (
            'P1 playtest item (中紀委視窗關閉): closing a choice modal only hid it client-side '
            'and left a dangling server-side pending_choice that blocked everything and could '
            'not be re-entered — systemic to the shared closeChoiceModal. Fix: a scoped '
            'cancellable-choice mechanism. The three voluntary Red Army activated abilities '
            '(中紀委/政工部/國安部), whose use-count is only consumed on RESOLVE, are marked '
            'cancellable; the modal close button becomes 取消 and sends cancel_choice, which '
            'clears the pending choice without consuming the ability so it can be re-activated. '
            'Every other choice is not cancellable (state() reports cancellable=false) and its '
            'close button is hidden on the frontend (must resolve; map choices keep their own '
            'close-to-map behaviour). "Confirm 0 cards" stays distinct from cancel — it consumes.'
        ),
        'browser_proof': [
            'docs/records/playtest-flow/CANCELLABLE_CHOICE_CCDI_BROWSER.png',
            'docs/records/playtest-flow/CANCELLABLE_CHOICE_MANDATORY_NOCLOSE_BROWSER.png',
        ],
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    (RECORD_DIR / 'CANCELLABLE_CHOICE_VALIDATION.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    (RECORD_DIR / 'CANCELLABLE_CHOICE_VALIDATION.md').write_text(
        '# 可取消 pending choice 驗證\n\n'
        '可重跑指令：`python3 scripts/validate_cancellable_choice.py`\n\n'
        f"- total: {summary['total']} / passed: {summary['passed']} / failed: {summary['failed']}\n\n"
        '## Browser proof\n\n'
        '- `CANCELLABLE_CHOICE_CCDI_BROWSER.png`（中紀委：關閉鈕為「取消」）\n'
        '- `CANCELLABLE_CHOICE_MANDATORY_NOCLOSE_BROWSER.png`（強制型 topdeck：無關閉鈕）\n\n'
        '## Results\n\n'
        + '\n'.join(
            f"- {'PASS' if r['ok'] else 'FAIL'} {r['name']}: checks={json.dumps(r['checks'], ensure_ascii=False)}"
            for r in results
        )
        + '\n',
        encoding='utf-8',
    )
    print(json.dumps(summary, ensure_ascii=False, default=str))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
