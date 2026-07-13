import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'action-cards'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card


def _new_game(n_players=2):
    names = [('p1', 'me'), ('p2', 'opp1'), ('p3', 'opp2')][:n_players]
    g = Game(names)
    for p in g.players:
        p.faction_id = 'liberals'
        p.hand = []
        p.deck.draw_pile = []
        p.deck.discard_pile = []
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    me = g.players[0]
    me.hand = [Card('模仿戰術', 'command', {'propaganda': 2})]
    return g, me


def case_single_opponent_prompts_choice():
    g, me = _new_game(2)
    g.players[1].deck.draw_pile = [Card('對手頂牌', 'command', {})]
    res = g.play_card(0, mode='action')
    pc = g.pending_choice or {}
    checks = {
        'pending_choice_opened': res.get('pending_choice') is True,
        'choice_key_is_imitate': pc.get('choice_key') == 'imitate_topdeck_target',
        'single_opponent_still_listed': [t['label'] for t in pc.get('targets', [])] == ['opp1'],
    }
    return {'name': 'single_opponent_still_prompts_a_choice', 'checks': checks, 'ok': all(checks.values())}


def case_multi_opponent_lists_all_with_cards():
    g, me = _new_game(3)
    g.players[1].deck.draw_pile = [Card('opp1頂牌', 'command', {})]
    g.players[2].deck.draw_pile = [Card('opp2頂牌', 'command', {})]
    g.play_card(0, mode='action')
    labels = sorted(t['label'] for t in (g.pending_choice or {}).get('targets', []))
    checks = {'both_opponents_listed': labels == ['opp1', 'opp2']}
    return {'name': 'multi_opponent_lists_every_player_with_a_card', 'checks': checks, 'ok': all(checks.values())}


def case_discard_only_opponent_is_valid_target():
    # draw() reshuffles the discard pile, so an opponent with cards only in discard is a target.
    g, me = _new_game(3)
    g.players[1].deck.draw_pile = []
    g.players[1].deck.discard_pile = [Card('opp1棄牌', 'command', {})]
    g.players[2].deck.draw_pile = []
    g.players[2].deck.discard_pile = []  # totally empty → excluded
    g.play_card(0, mode='action')
    labels = [t['label'] for t in (g.pending_choice or {}).get('targets', [])]
    checks = {
        'discard_only_opponent_included': 'opp1' in labels,
        'fully_empty_opponent_excluded': 'opp2' not in labels,
    }
    return {'name': 'discard_only_opponent_is_a_valid_target', 'checks': checks, 'ok': all(checks.values())}


def case_no_target_when_all_empty():
    g, me = _new_game(2)
    # opponent has no cards at all
    res = g.play_card(0, mode='action')
    checks = {
        'no_pending_choice': not res.get('pending_choice') and g.pending_choice is None,
        'nothing_imitated_to_hand': all(c.name != '模仿戰術' for c in me.hand) and len(me.hand) == 0,
    }
    return {'name': 'no_legal_target_does_not_get_stuck', 'checks': checks, 'ok': all(checks.values())}


def case_resolve_imitates_card_and_marks_return():
    g, me = _new_game(2)
    top = Card('對手頂牌', 'command', {})
    g.players[1].deck.draw_pile = [top]
    g.play_card(0, mode='action')
    resolved = g.resolve_pending_choice(me.id, 0)
    checks = {
        'resolve_ok': resolved.get('success') is True,
        'imitated_card_reported': resolved.get('imitated_card') == '對手頂牌',
        'card_in_my_hand': any(c.name == '對手頂牌' for c in me.hand),
        'marked_to_return_to_owner': getattr(top, '_return_to_owner_topdeck', None) == g.players[1].id,
        'removed_from_owner_deck': top not in g.players[1].deck.draw_pile,
        'pending_cleared': g.pending_choice is None,
    }
    return {'name': 'resolving_imitates_card_to_hand_and_marks_return', 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_single_opponent_prompts_choice(),
        case_multi_opponent_lists_all_with_cards(),
        case_discard_only_opponent_is_valid_target(),
        case_no_target_when_all_empty(),
        case_resolve_imitates_card_and_marks_return(),
    ]
    summary = {
        'scope': ['模仿戰術'],
        'purpose': (
            'P1 playtest item: playing 模仿戰術 showed no target-selection prompt. The frontend '
            'auto-picked the sole opponent (players.length === 1) and silently imitated with no '
            'modal; it also did not filter opponents with an empty deck. 模仿戰術 is now driven by '
            'a server-side imitate_topdeck_target choice that always opens (even against one '
            'opponent), lists only players who actually have a card to reveal (draw pile or, via '
            'reshuffle, discard pile), and returns nothing-happened (with a log) when there is no '
            'legal target. The card rule: 選擇1位玩家展示其牌庫頂牌，本回合您可以使用該牌，使用後放回擁有者牌庫頂.'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    (RECORD_DIR / 'IMITATE_TACTICS_VALIDATION.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    (RECORD_DIR / 'IMITATE_TACTICS_VALIDATION.md').write_text(
        '# 模仿戰術目標選擇驗證\n\n'
        '可重跑指令：`python3 scripts/validate_imitate_tactics.py`\n\n'
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
