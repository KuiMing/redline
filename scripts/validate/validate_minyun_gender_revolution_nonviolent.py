import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'faction-ui'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card

ARMED_CARD = '武裝者'


def _new_game(faction_id):
    g = Game([('p1', 'player'), ('p2', 'red')])
    player, red = g.players
    player.id = 'p1'
    red.id = 'p2'
    player.faction_id = faction_id
    red.faction_id = 'red_army'
    # 臺北/基隆 are rail-adjacent (1 step), so a faction actually allowed to play
    # 武裝者 has a valid in-range target and can genuinely succeed (not blocked for
    # an unrelated reason like "no target in range").
    red.organizations = {'基隆': 1}
    player.organizations = {'臺北': 1}
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    player.hand = [Card(ARMED_CARD, 'armed', {})]
    player.resources = {'money': 5, 'propaganda': 5}
    return g, player, red


def test_faction_has_ability(faction_id):
    g, player, red = _new_game(faction_id)
    has_ability = g._player_has_ability(player, '非暴力')
    return {
        'name': f'{faction_id}_has_非暴力_ability',
        'checks': {'ability_resolved': has_ability},
        'ok': has_ability,
    }


def test_faction_blocked_from_playing_armed_card(faction_id):
    g, player, red = _new_game(faction_id)
    result = g.play_card(0, mode='action')
    checks = {
        'play_blocked': result.get('error') == '非暴力：不能打出武裝類卡牌',
        'card_still_in_hand': any(getattr(c, 'name', str(c)) == ARMED_CARD for c in player.hand),
    }
    return {
        'name': f'{faction_id}_blocked_from_playing_armed_card',
        'result': result,
        'checks': checks,
        'ok': all(checks.values()),
    }


def test_faction_blocked_from_buying_armed_card(faction_id):
    g, player, red = _new_game(faction_id)
    player.hand = []
    g.turn_phase = TurnPhase.END  # buy_card only works in this phase (this game's purchase step)
    g.purchase_area = [Card(ARMED_CARD, 'armed', {})]
    result = g.buy_card(0)
    checks = {
        'buy_blocked': result.get('error') == '非暴力：不能購買武裝類卡牌',
    }
    return {
        'name': f'{faction_id}_blocked_from_buying_armed_card',
        'result': result,
        'checks': checks,
        'ok': all(checks.values()),
    }


def test_unrelated_faction_not_blocked():
    # Sanity/regression: a faction WITHOUT 非暴力 must still be able to play armed cards.
    g, player, red = _new_game('liberals')
    result = g.play_card(0, mode='action', target_player_id=red.id)
    checks = {
        'play_succeeded': result.get('success') is True,
        'no_nonviolent_ability': not g._player_has_ability(player, '非暴力'),
    }
    return {
        'name': 'unrelated_faction_liberals_not_blocked',
        'result': result,
        'checks': checks,
        'ok': all(checks.values()),
    }


def main():
    results = []
    for faction_id in ('minyun', 'gender_revolution'):
        results.append(test_faction_has_ability(faction_id))
        results.append(test_faction_blocked_from_playing_armed_card(faction_id))
        results.append(test_faction_blocked_from_buying_armed_card(faction_id))
    results.append(test_unrelated_faction_not_blocked())

    summary = {
        'scope': ['minyun', 'gender_revolution'],
        'purpose': (
            '民運派 (minyun) and 性別革命 (gender_revolution) declare a 【非暴力】 ability via '
            'abilities_text ("禁止持有武裝類卡牌"), but _resolve_ability_text had no mapping '
            'for the name "非暴力", so the ability silently resolved to None and was dropped '
            '— these two factions were never actually blocked from playing/buying armed '
            'cards. Fixed by adding "非暴力" to the direct-mapping dict, reusing the same '
            'restriction already enforced for structured-schema factions (e.g. '
            'tibet_dharamsala, uyghur_munich). Confirmed no scope-widening risk: this '
            'repo\'s card data has no "equipment"-category cards at all, so blocking '
            '{armed, equipment} behaves identically to blocking just {armed} in practice.'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'MINYUN_GENDER_REVOLUTION_NONVIOLENT_FIX_VALIDATION_20260711.json'
    md_path = RECORD_DIR / 'MINYUN_GENDER_REVOLUTION_NONVIOLENT_FIX_VALIDATION_20260711.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 民運派／性別革命 非暴力 fix validation\n\n'
        '可重跑指令：`python3 scripts/validate/validate_minyun_gender_revolution_nonviolent.py`\n\n'
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
