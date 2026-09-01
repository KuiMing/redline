import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'support-cards'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card

CARD = '南洋奧援'


def _new_game():
    g = Game([('p1', 'player'), ('p2', 'red')])
    player, red = g.players
    player.id = 'p1'
    red.id = 'p2'
    player.faction_id = 'support_validator'
    player.base = '北京'  # no ruler presence -> tier 1 fallback
    player.organizations = {'北京': 1}
    red.faction_id = 'red_army'
    red.base = '北京'
    red.organizations = {'北京': 1}
    red.hand = []
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    support = g._make_support_card(CARD)
    player.hand = [support, Card('保留手牌', 'command', {})]
    player.deck.draw_pile = [Card('抽到的牌', 'command', {})]
    player.deck.discard_pile = []
    player.resources = {'money': 0, 'propaganda': 0}
    return g, player, red


def test_choice_is_offered_not_auto_resolved():
    g, player, red = _new_game()
    result = g.play_card(0, mode='action')
    pending = g.pending_choice or {}
    offered_names = sorted(getattr(c, 'name', str(c)) for c in (pending.get('cards') or []))
    checks = {
        'play_success': result.get('success') is True,
        'pending_choice_raised': result.get('pending_choice') is True,
        'choice_key_correct': pending.get('choice_key') == 'draw_then_discard_choice',
        'both_hand_cards_offered': offered_names == sorted(['保留手牌', '抽到的牌']),
    }
    return {'name': 'choice_is_offered_not_auto_resolved', 'checks': checks, 'ok': all(checks.values())}


def test_player_can_keep_the_drawn_card_and_discard_the_other():
    g, player, red = _new_game()
    g.play_card(0, mode='action')
    pending = g.pending_choice or {}
    cards = pending.get('cards') or []
    discard_index = next(i for i, c in enumerate(cards) if getattr(c, 'name', str(c)) == '保留手牌')
    resolved = g.resolve_pending_choice(player.id, discard_index)
    hand_names = [getattr(c, 'name', str(c)) for c in player.hand]
    discard_names = [getattr(c, 'name', str(c)) for c in player.deck.discard_pile]
    checks = {
        'resolved_success': resolved.get('success') is True,
        'discarded_the_other_card': resolved.get('discarded_card') == '保留手牌',
        'drawn_card_kept_in_hand': hand_names == ['抽到的牌'],
        'other_card_actually_discarded': '保留手牌' in discard_names,
    }
    return {
        'name': 'player_can_keep_the_drawn_card_and_discard_the_other',
        'checks': checks,
        'ok': all(checks.values()),
        'detail': {'hand_names': hand_names, 'discard_names': discard_names},
    }


def main():
    results = [
        test_choice_is_offered_not_auto_resolved(),
        test_player_can_keep_the_drawn_card_and_discard_the_other(),
    ]
    summary = {
        'scope': [CARD],
        'purpose': (
            '南洋奧援 tier 1 ("抽1張牌，再從所有手牌中棄掉1張牌") used to hard-pop the last '
            'hand card, which was always the just-drawn card (drawn cards are appended to '
            'the end of hand) — a net no-op with no real player choice. Fixed by offering a '
            'genuine pending choice over the whole hand. This proves the choice is real: the '
            'player can choose to discard a DIFFERENT card and keep the just-drawn one, not '
            'just reproduce the old fixed outcome.'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'SOUTH_SEAS_SUPPORT_TIER1_DISCARD_CHOICE_VALIDATION_20260711.json'
    md_path = RECORD_DIR / 'SOUTH_SEAS_SUPPORT_TIER1_DISCARD_CHOICE_VALIDATION_20260711.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 南洋奧援 tier1 discard choice validation\n\n'
        '可重跑指令：`python3 scripts/validate/validate_south_seas_support_tier1_discard_choice.py`\n\n'
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
