import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'action-cards'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card


def _new_game():
    g = Game([('p1', 'A'), ('p2', 'B')])
    a, b = g.players
    a.faction_id = 'liberals'
    b.faction_id = 'red_army'
    b.hand = [Card('乙手牌', 'command', {})]
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    a.hand = [Card('誘導虛耗', 'command', {'propaganda': 1}), Card('天方奧援', 'support', {}), Card('追隨者', 'propaganda', {})]
    a.deck.draw_pile = [Card('抽到的', 'command', {})]
    a.deck.discard_pile = []
    return g, a, b


def case_only_self_offered():
    g, a, b = _new_game()
    g.play_card(0, mode='action')
    pending = g.pending_choice or {}
    entries = pending.get('cards') or []
    names = [(e.get('zone'), getattr(e.get('card'), 'name', None) or e.get('name')) for e in entries]
    checks = {
        'choice_opened': pending.get('choice_key') == 'optional_trash',
        'exactly_two_options': len(entries) == 2,
        'first_is_the_card_itself': names[0] == ('current_card', '誘導虛耗') if names else False,
        'second_is_skip': bool(entries) and entries[-1].get('skip') is True,
        'no_hand_cards_offered': not any(e.get('zone') == 'hand' for e in entries),
    }
    return {'name': 'only_the_played_card_offered', 'names': names, 'checks': checks, 'ok': all(checks.values())}


def case_remove_then_target_discard():
    g, a, b = _new_game()
    g.play_card(0, mode='action')
    removed = g.resolve_pending_choice(a.id, 0)  # 移除誘導虛耗本身
    pending = g.pending_choice or {}
    checks = {
        'remove_ok': removed.get('success') is True,
        'followup_target_choice': pending.get('choice_key') == 'bait_exhaustion_target',
    }
    targets = pending.get('targets') or []
    idx = next(i for i, t in enumerate(targets) if t.get('id') == b.id)
    g.resolve_pending_choice(a.id, idx)
    pending = g.pending_choice or {}
    checks['target_hand_discard_opened'] = pending.get('choice_key') == 'bait_exhaustion_target_discard' and pending.get('player_id') == b.id
    resolved = g.resolve_pending_choice(b.id, 0)
    checks['target_discarded'] = resolved.get('success') is True and not b.hand
    return {'name': 'remove_self_then_force_target_discard', 'checks': checks, 'ok': all(checks.values())}


def case_decline_skips_effect():
    g, a, b = _new_game()
    g.play_card(0, mode='action')
    pending = g.pending_choice or {}
    skip_index = next(i for i, e in enumerate(pending.get('cards') or []) if isinstance(e, dict) and e.get('skip'))
    declined = g.resolve_pending_choice(a.id, skip_index)
    discard_names = [c.name for c in a.deck.discard_pile]
    checks = {
        'declined_ok': declined.get('success') is True and declined.get('skipped') is True,
        'no_followup': not g.pending_choice,
        'card_goes_to_own_discard_not_removed': '誘導虛耗' in discard_names,
        'target_hand_untouched': len(b.hand) == 1,
    }
    return {'name': 'decline_keeps_card_in_discard_and_skips_forced_discard', 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_only_self_offered(),
        case_remove_then_target_discard(),
        case_decline_skips_effect(),
    ]
    summary = {
        'scope': ['誘導虛耗'],
        'purpose': (
            'P1 playtest item: 誘導虛耗\'s optional trash listed the whole hand ("或移除 1 '
            '張手牌") even though the card text only allows removing the just-played '
            '誘導虛耗 itself ("打出可移除本牌"). The choice now offers exactly the played '
            'card plus an explicit decline option; removing it proceeds to the '
            'choose-a-player forced-discard flow ("若移除本牌…"), while declining sends the '
            'card to the discard pile normally and skips the forced discard entirely.'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'BAIT_EXHAUSTION_SELF_ONLY_VALIDATION_20260711.json'
    md_path = RECORD_DIR / 'BAIT_EXHAUSTION_SELF_ONLY_VALIDATION_20260711.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 誘導虛耗僅可移除本牌驗證\n\n'
        '可重跑指令：`python3 scripts/validate/validate_bait_exhaustion_self_only.py`\n\n'
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
