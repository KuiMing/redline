import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'action-cards'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card

CARD = '情報網'


def _new_game():
    g = Game([('p1', 'player'), ('p2', 'player2')])
    a, b = g.players
    a.id = 'p1'
    b.id = 'p2'
    a.faction_id = 'liberals'
    b.faction_id = 'liberals'
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    return g, a, b


def check_own_turn_play_offers_only_two_options():
    g, a, b = _new_game()
    a.hand = [Card(CARD, 'spy', {'money': 1, 'propaganda': 1})]
    a.resources = {'money': 3, 'propaganda': 3}
    b.hand = []  # nobody can react, isolates the own-turn choose_one behavior

    result = g.play_card(0, mode='action')
    choice = getattr(g, 'pending_choice', None) or {}
    options = choice.get('options') or []
    labels = [o.get('label') for o in options]

    checks = {
        'play_card_success': result.get('success') is True,
        'choose_one_offered': choice.get('choice_key') == 'choose_one',
        'exactly_two_options': len(options) == 2,
        'no_cancel_option_label': not any('取消' in (label or '') for label in labels),
    }
    return {
        'name': 'own_turn_play_offers_only_two_options',
        'play_card_result': result,
        'option_labels': labels,
        'checks': checks,
        'ok': all(checks.values()),
    }


def check_reaction_path_still_cancels_correctly():
    g, a, b = _new_game()
    a.hand = [Card('領導', 'command', {})]
    b.hand = [Card(CARD, 'spy', {'money': 1, 'propaganda': 1})]
    a_hand_before = len(a.hand)

    play_result = g.play_card(0, mode='action')
    reaction_choice = dict(getattr(g, 'pending_choice', None) or {})
    resolved = g.resolve_pending_choice(b.id, 1)

    checks = {
        'reaction_prompt_raised': play_result.get('pending_choice') is True,
        'reaction_choice_type_correct': reaction_choice.get('type') == 'reaction_choice',
        'reaction_offered_to_holder': reaction_choice.get('player_id') == b.id,
        'reaction_candidate_is_intel_network': (
            (reaction_choice.get('cards') or [{}])[0].get('name') == CARD
        ),
        'resolved_success': resolved.get('success') is True,
        'used_intel_network_as_reaction': resolved.get('reaction_card') == CARD,
        'canceled_correct_card': resolved.get('canceled_card') == '領導',
        # 領導's own effect (draw 1) must NOT have run once canceled.
        'acting_player_did_not_draw': len(a.hand) == a_hand_before - 1,
    }
    return {
        'name': 'reaction_path_still_cancels_correctly',
        'play_result': play_result,
        'reaction_choice': {k: v for k, v in reaction_choice.items() if k not in {'acting_player', 'played_card'}},
        'resolved': resolved,
        'checks': checks,
        'ok': all(checks.values()),
    }


def main():
    results = [
        check_own_turn_play_offers_only_two_options(),
        check_reaction_path_still_cancels_correctly(),
    ]
    summary = {
        'scope': [CARD],
        'purpose': (
            '情報網 choose_one previously always offered a 3rd option ("取消1張對方所打出行動卡'
            '之能力") even when played normally on the owner\'s own turn, where cancel_card has '
            'no real reaction context and silently no-ops (wastes the whole card for nothing). '
            'The genuine reaction-cancel use of 情報網 is handled entirely by a separate code '
            'path (_reaction_prompt_candidates / _build_reaction_context / '
            '_resolve_reaction_context) that never goes through choose_one at all, so the 3rd '
            'option was unreachable-but-broken. Fix: removed it from '
            'data/action_cards_structured.v1.1.json, leaving only the 2 real own-turn options; '
            'the reaction path is untouched and still works.'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'INTEL_NETWORK_NO_REACTION_OPTION_OWN_TURN_VALIDATION_20260710.json'
    md_path = RECORD_DIR / 'INTEL_NETWORK_NO_REACTION_OPTION_OWN_TURN_VALIDATION_20260710.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 情報網 own-turn choose_one fix validation\n\n'
        '可重跑指令：`python3 scripts/validate_intel_network_no_reaction_option_own_turn.py`\n\n'
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
