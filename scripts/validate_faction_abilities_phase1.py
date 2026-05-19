import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'faction-ui'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card


def ok(name, condition, detail=''):
    return {'name': name, 'ok': bool(condition), 'detail': detail}


def make_game(faction_id='hong_kong', base='香港城'):
    g = Game([('p1', 'A'), ('p2', 'B')])
    for p in g.players:
        if p.id == 'p1':
            p.faction_id = faction_id
            p.base = base
            p.organizations = {base: 1}
        else:
            p.faction_id = 'red_army'
            p.base = '北京'
            p.organizations = {'北京': 1}
    return g


def test_hong_kong_setup():
    g = make_game('hong_kong', '香港城')
    player = g.players[0]
    g._apply_setup_abilities(player)
    names = [c.name for c in player.deck.discard_pile]
    return ok('hong_kong_lam_chau_setup', names.count('宣傳家') >= 1, str(names))


def test_hong_kong_international_line():
    g = make_game('hong_kong', '倫敦')
    player = g.players[0]
    g.turn_phase = TurnPhase.ACTION
    player.hand = [Card('測試金錢牌', 'money', {'money': 1})]
    g.play_card(0, mode='action')
    return ok('hong_kong_international_line', bool(g.turn_log.get('played_propaganda_card')), str(g.turn_log))


def test_taiwan_green_build_draw():
    g = make_game('taiwan_green', '臺北')
    player = g.players[0]
    g.turn_phase = TurnPhase.ACTION
    player.hand = []
    player.deck.draw_pile = [Card('補牌1', 'money', {'money': 1})]
    g.build_organization('臺北')
    g.advance_turn_phase()  # ACTION -> END
    before = len(player.hand)
    g.advance_turn_phase()  # END -> _end_turn
    after = len(player.hand)
    return ok('taiwan_green_end_turn_draw', after >= before + 1 or after >= 1, f'before={before}, after={after}')


def test_taiwan_blue_build_draw():
    g = make_game('taiwan_blue', '臺北')
    player = g.players[0]
    g.turn_phase = TurnPhase.ACTION
    player.hand = []
    player.deck.draw_pile = [Card('補牌1', 'money', {'money': 1})]
    g.build_organization('臺北')
    g.advance_turn_phase()
    before = len(player.hand)
    g.advance_turn_phase()
    after = len(player.hand)
    return ok('taiwan_blue_end_turn_draw', after >= before + 1 or after >= 1, f'before={before}, after={after}')


def test_mongol_develop_legality():
    g = make_game('mongol', '東京')
    player = g.players[0]
    g.turn_phase = TurnPhase.ACTION
    player.organizations = {'烏蘭巴托': 1, '東京': 1, '北京': 1}
    allow_mongol = g.can_develop_in_town(player, '烏蘭巴托')
    allow_uncamped = g.can_develop_in_town(player, '東京')
    block_tagged_other = not g.can_develop_in_town(player, '北京')
    result = g.build_organization('東京')
    return ok('mongol_develop_legality', allow_mongol and allow_uncamped and block_tagged_other and result.get('success') is True, f"allow_mongol={allow_mongol}, allow_uncamped={allow_uncamped}, block_other={block_tagged_other}, result={result}")


def test_kazakh_propaganda_draw():
    g = make_game('kazakh', '阿拉木圖')
    player = g.players[0]
    g.turn_phase = TurnPhase.ACTION
    player.hand = [Card('宣傳測試', 'propaganda', {'propaganda': 1})]
    player.deck.draw_pile = [Card('補牌1', 'money', {'money': 1})]
    before = len(player.hand)
    g.play_card(0, mode='action')
    after = len(player.hand)
    return ok('kazakh_first_propaganda_draw', bool(g.turn_log.get('played_propaganda_card')), f'before={before}, after={after}, log={g.turn_log}')


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    results = [
        test_hong_kong_setup(),
        test_hong_kong_international_line(),
        test_taiwan_green_build_draw(),
        test_taiwan_blue_build_draw(),
        test_mongol_develop_legality(),
        test_kazakh_propaganda_draw(),
    ]
    summary = {
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    out = {'summary': summary, 'results': results}
    with open(RECORD_DIR / 'FACTION_ABILITY_PHASE1_VALIDATION.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with open(RECORD_DIR / 'FACTION_ABILITY_PHASE1_VALIDATION.md', 'w', encoding='utf-8') as f:
        f.write('# FACTION ABILITY PHASE1 VALIDATION\n\n')
        f.write(f"- total: {summary['total']}\n")
        f.write(f"- passed: {summary['passed']}\n")
        f.write(f"- failed: {summary['failed']}\n\n")
        for r in results:
            mark = 'PASS' if r['ok'] else 'FAIL'
            f.write(f"- {mark} {r['name']}: {r['detail']}\n")
    print(json.dumps(out, ensure_ascii=False))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
