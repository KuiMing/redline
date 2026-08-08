import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'support-cards'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase


def _new_game(caster_faction):
    g = Game([('p1', 'CASTER'), ('p2', 'RED' if caster_faction != 'red_army' else 'OTHER')])
    a, b = g.players
    a.faction_id = caster_faction
    b.faction_id = 'red_army' if caster_faction != 'red_army' else 'liberals'
    for p in g.players:
        p.deck.discard_pile = []
        p.hand = []
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    a.hand = [g._make_support_card('紅軍奧援')]
    a.deck.draw_pile = [g._starter_card('追隨者') for _ in range(3)]
    return g, a, b


def _names(cards):
    return [getattr(c, 'name', str(c)) for c in cards]


def case_non_red_action_returns_to_red():
    g, a, red = _new_game('liberals')
    result = g.play_card(0, mode='action')
    checks = {
        'play_ok': result.get('success') is True,
        'returned_flag': result.get('card_returned_to') == red.name,
        'card_in_red_discard': '紅軍奧援' in _names(red.deck.discard_pile),
        'not_in_caster_discard': '紅軍奧援' not in _names(a.deck.discard_pile),
        'caster_drew_one': len(a.hand) == 1,
    }
    return {'name': 'non_red_action_play_returns_to_red_discard', 'checks': checks, 'ok': all(checks.values())}


def case_non_red_resource_returns_to_red():
    g, a, red = _new_game('liberals')
    result = g.play_card(0, mode='resource')
    checks = {
        'play_ok': result.get('success') is True,
        'card_in_red_discard': '紅軍奧援' in _names(red.deck.discard_pile),
        'not_in_caster_discard': '紅軍奧援' not in _names(a.deck.discard_pile),
    }
    return {'name': 'non_red_resource_play_returns_to_red_discard', 'checks': checks, 'ok': all(checks.values())}


def case_red_resource_play_stays_in_own_discard_no_target_choice():
    # 2026-08-08 使用者更正：紅軍自己用紅軍奧援當資源時，直接取得資源、卡片進自己棄牌堆，
    # 不問要放進哪位反共玩家的棄牌堆（那是行動模式才有的效果）。
    g, red, other = _new_game('red_army')
    result = g.play_card(0, mode='resource')
    checks = {
        'play_ok': result.get('success') is True,
        'no_pending_choice': not result.get('pending_choice') and g.pending_choice is None,
        'resources_granted': red.resources.get('money') == 1 and red.resources.get('propaganda') == 1,
        'card_in_own_discard': '紅軍奧援' in _names(red.deck.discard_pile),
        'not_in_opponent_discard': '紅軍奧援' not in _names(other.deck.discard_pile),
    }
    return {'name': 'red_resource_play_stays_in_own_discard_no_target_choice', 'checks': checks, 'ok': all(checks.values())}


def case_red_play_passes_to_opponent_unchanged():
    # 紅軍自己打出：既有「選一位反共玩家、放入其棄牌堆」流程不受影響
    g, red, other = _new_game('red_army')
    result = g.play_card(0, mode='action')
    pending = g.pending_choice or {}
    checks = {
        'target_choice_opened': result.get('pending_choice') is True and pending.get('choice_key') == 'red_support_target_player',
    }
    targets = pending.get('targets') or []
    idx = next(i for i, t in enumerate(targets) if t.get('id') == other.id)
    resolved = g.resolve_pending_choice(red.id, idx)
    checks.update({
        'resolved': resolved.get('success') is True,
        'card_in_opponent_discard': '紅軍奧援' in _names(other.deck.discard_pile),
        'not_in_red_discard': '紅軍奧援' not in _names(red.deck.discard_pile),
    })
    return {'name': 'red_play_pass_flow_unchanged', 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_non_red_action_returns_to_red(),
        case_non_red_resource_returns_to_red(),
        case_red_resource_play_stays_in_own_discard_no_target_choice(),
        case_red_play_passes_to_opponent_unchanged(),
    ]
    summary = {
        'scope': ['紅軍奧援 ownership'],
        'purpose': (
            'P1 playtest item: when a non-red player played 紅軍奧援 (acquired via the pass '
            'mechanic), play_card\'s special branch discarded it into the CASTER\'s own pile '
            'instead of returning the red-army-exclusive card to the red player\'s discard. '
            'Both action mode and resource mode now return it to the red player. 2026-08-08 '
            'update: red player\'s own RESOURCE-mode play no longer opens the anti-communist '
            'target-choice prompt (that only applies to action mode) — resource mode now '
            'grants resources immediately and discards to red\'s own pile, matching a normal '
            'resource card.'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'RED_SUPPORT_OWNERSHIP_VALIDATION_20260712.json'
    md_path = RECORD_DIR / 'RED_SUPPORT_OWNERSHIP_VALIDATION_20260712.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 紅軍奧援歸屬驗證（非紅軍打出後回紅軍棄牌堆）\n\n'
        '可重跑指令：`python3 scripts/validate_red_support_ownership.py`\n\n'
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
