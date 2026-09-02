import json
import random
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase

RECORD_DIR = BASE / 'docs' / 'records' / 'leak-card'
OUT_JSON = RECORD_DIR / 'LEAK_CARD_VALIDATION.json'
OUT_MD = RECORD_DIR / 'LEAK_CARD_VALIDATION.md'


def record_path(path):
    return str(path.relative_to(BASE))


def names(cards):
    return [getattr(c, 'name', str(c)) for c in cards]


def make_game():
    random.seed(20260511)
    game = Game([('p1', 'actor'), ('p2', 'target-a'), ('p3', 'target-b')])
    game.current_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    for p in game.players:
        p.resources = {'money': 0, 'propaganda': 0}
        p.moves_left = 0
        p.hand = []
        p.deck.draw_pile = []
        p.deck.discard_pile = []
    actor, target_a, target_b = game.players
    actor.name = 'actor'
    target_a.name = 'target-a'
    target_b.name = 'target-b'
    actor.hand = [Card('走漏風聲', 'spy', {'propaganda': 1})]
    return game, actor, target_a, target_b


def check(name, passed, details):
    return {'name': name, 'passed': bool(passed), 'details': details}


def run_checks():
    checks = []

    # Rule source: data/cards/action_cards.v1.1.json says:
    # 「選擇1位玩家棄掉其牌庫頂牌，若該牌購買費用為1點以上，則將1張內鬥放進該玩家棄牌堆。」
    game, actor, target_a, target_b = make_game()
    target_a.deck.draw_pile = [Card('追隨者', 'propaganda', {'propaganda': 1})]
    target_b.deck.draw_pile = [Card('樂捐者', 'money', {'money': 1}), Card('資助者', 'money', {'money': 2, 'propaganda': 2})]
    internal_conflict_supply_before = game.static_purchase_supply.get('內鬥', 0)
    result = game.play_card(0, mode='action', target_player_id=target_b.id)
    internal_conflict_supply_after = game.static_purchase_supply.get('內鬥', 0)
    checks.append(check(
        '走漏風聲_explicit_target_discards_top_card_receives_internal_conflict_and_consumes_supply',
        result.get('success') is True
        and names(target_b.deck.discard_pile) == ['資助者', '內鬥']
        and names(target_b.deck.draw_pile) == ['樂捐者']
        and names(target_a.deck.discard_pile) == []
        and names(actor.deck.discard_pile) == ['走漏風聲']
        and actor.resources == {'money': 0, 'propaganda': 0}
        and internal_conflict_supply_after == internal_conflict_supply_before - 1,
        {
            'result': result,
            'actor_discard': names(actor.deck.discard_pile),
            'target_a_discard': names(target_a.deck.discard_pile),
            'target_b_draw': names(target_b.deck.draw_pile),
            'target_b_discard': names(target_b.deck.discard_pile),
            'actor_resources': dict(actor.resources),
            'internal_conflict_supply_before': internal_conflict_supply_before,
            'internal_conflict_supply_after': internal_conflict_supply_after,
            'expected_rule': 'action mode discards chosen target top deck card; if discarded card purchase cost >= 1, move 1 內鬥 from static purchase supply to that same target discard; printed 宣傳1 is resource-mode only.',
        },
    ))

    game, actor, target_a, target_b = make_game()
    target_a.deck.draw_pile = [Card('追隨者', 'propaganda', {'propaganda': 1})]
    target_b.deck.draw_pile = [Card('資助者', 'money', {'money': 2, 'propaganda': 2})]
    result = game.play_card(0, mode='action')
    checks.append(check(
        '走漏風聲_without_explicit_target_uses_first_other_player_fallback_not_actor_or_all_players',
        result.get('success') is True
        and names(target_a.deck.discard_pile) == ['追隨者']
        and names(target_b.deck.discard_pile) == []
        and names(actor.deck.discard_pile) == ['走漏風聲'],
        {
            'result': result,
            'actor_discard': names(actor.deck.discard_pile),
            'target_a_discard': names(target_a.deck.discard_pile),
            'target_b_discard': names(target_b.deck.discard_pile),
            'expected_rule': 'until UI supplies an explicit target, fallback should affect exactly the first other player; zero-cost/top starter does not add 內鬥.',
        },
    ))

    game, actor, target_a, target_b = make_game()
    target_b.deck.draw_pile = [Card('資助者', 'money', {'money': 2, 'propaganda': 2})]
    result = game.play_card(0, mode='resource', target_player_id=target_b.id)
    checks.append(check(
        '走漏風聲_resource_mode_grants_only_printed_resource_without_deck_attack',
        result.get('success') is True
        and actor.resources == {'money': 0, 'propaganda': 1}
        and names(actor.deck.discard_pile) == ['走漏風聲']
        and names(target_b.deck.draw_pile) == ['資助者']
        and names(target_b.deck.discard_pile) == [],
        {
            'result': result,
            'actor_resources': dict(actor.resources),
            'actor_discard': names(actor.deck.discard_pile),
            'target_b_draw': names(target_b.deck.draw_pile),
            'target_b_discard': names(target_b.deck.discard_pile),
            'expected_rule': 'resource mode is exclusive: printed 宣傳1 only, no action effect.',
        },
    ))

    game, actor, target_a, target_b = make_game()
    target_b.deck.draw_pile = [Card('資助者', 'money', {'money': 2, 'propaganda': 2})]
    result = game.play_card(0, mode='action', target_player_id=actor.id)
    checks.append(check(
        '走漏風聲_rejects_self_target_without_consuming_card_or_deck',
        result.get('error') == '走漏風聲必須指定其他玩家'
        and names(actor.hand) == ['走漏風聲']
        and names(actor.deck.discard_pile) == []
        and names(target_b.deck.draw_pile) == ['資助者']
        and names(target_b.deck.discard_pile) == [],
        {
            'result': result,
            'actor_hand': names(actor.hand),
            'actor_discard': names(actor.deck.discard_pile),
            'target_b_draw': names(target_b.deck.draw_pile),
            'target_b_discard': names(target_b.deck.discard_pile),
            'expected_rule': 'server-side validation must reject crafted self-target payloads before consuming the played card.',
        },
    ))

    game, actor, target_a, target_b = make_game()
    target_b.deck.draw_pile = [Card('資助者', 'money', {'money': 2, 'propaganda': 2})]
    result = game.play_card(0, mode='action', target_player_id='missing-player')
    checks.append(check(
        '走漏風聲_rejects_unknown_target_without_consuming_card_or_deck',
        result.get('error') == '走漏風聲必須指定其他玩家'
        and names(actor.hand) == ['走漏風聲']
        and names(actor.deck.discard_pile) == []
        and names(target_b.deck.draw_pile) == ['資助者']
        and names(target_b.deck.discard_pile) == [],
        {
            'result': result,
            'actor_hand': names(actor.hand),
            'actor_discard': names(actor.deck.discard_pile),
            'target_b_draw': names(target_b.deck.draw_pile),
            'target_b_discard': names(target_b.deck.discard_pile),
            'expected_rule': 'server-side validation must reject unknown explicit targets before consuming the played card.',
        },
    ))

    game, actor, target_a, target_b = make_game()
    target_b.deck.draw_pile = [Card('資助者', 'money', {'money': 2, 'propaganda': 2})]
    result = game.play_card(0, mode='action', target_player_id='')
    checks.append(check(
        '走漏風聲_rejects_empty_string_target_without_consuming_card_or_deck',
        result.get('error') == '走漏風聲必須指定其他玩家'
        and names(actor.hand) == ['走漏風聲']
        and names(actor.deck.discard_pile) == []
        and names(target_b.deck.draw_pile) == ['資助者']
        and names(target_b.deck.discard_pile) == [],
        {
            'result': result,
            'actor_hand': names(actor.hand),
            'actor_discard': names(actor.deck.discard_pile),
            'target_b_draw': names(target_b.deck.draw_pile),
            'target_b_discard': names(target_b.deck.discard_pile),
            'expected_rule': 'server-side validation must reject falsy explicit targets before consuming the played card.',
        },
    ))

    return checks


def write_outputs(checks):
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        'total': len(checks),
        'passed': sum(1 for c in checks if c['passed']),
        'failed': sum(1 for c in checks if not c['passed']),
    }
    out = {'date': date.today().isoformat(), 'summary': summary, 'checks': checks}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')

    lines = ['# LEAK CARD VALIDATION', '', f"日期：{out['date']}", '', f"summary: {summary}", '']
    for item in checks:
        status = 'PASS' if item['passed'] else 'FAIL'
        lines.append(f"## {item['name']} — {status}")
        for k, v in item['details'].items():
            lines.append(f"- {k}: {v}")
        lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    return out


def main():
    out = write_outputs(run_checks())
    print(json.dumps({'summary': out['summary'], 'json': record_path(OUT_JSON), 'md': record_path(OUT_MD)}, ensure_ascii=False))
    if out['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
