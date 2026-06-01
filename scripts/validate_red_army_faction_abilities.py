import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'event-cards'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card


def ok(name, condition, detail=''):
    return {'name': name, 'ok': bool(condition), 'detail': detail}


def make_red_game():
    game = Game([('red', 'Red'), ('a', 'A'), ('b', 'B')], market_mode='all_cards')
    red, a, b = game.players
    red.faction_id = 'red_army'
    red.base = '北京'
    red.organizations = {'北京': 1}
    a.faction_id = 'liberals'
    a.base = '香港城'
    a.organizations = {'天津': 1}
    b.faction_id = 'hong_kong'
    b.base = '香港城'
    b.organizations = {'上海': 1}
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.turn_log = game._new_turn_log()
    return game, red, a, b


def test_united_front_draws_once_per_use_until_non_red_limit():
    game, red, a, b = make_red_game()
    red.hand = []
    red.deck.draw_pile = [Card('補牌1', 'money', {'money': 1}), Card('補牌2', 'money', {'money': 1})]
    first = game._activated_faction_action(red, '統戰部')
    second = game._activated_faction_action(red, '統戰部')
    third = game._activated_faction_action(red, '統戰部')
    return ok(
        'red_army_united_front_draws_until_non_red_limit',
        first.get('success') and second.get('success') and third.get('error') and len(red.hand) == 2,
        f'first={first}, second={second}, third={third}, hand={[c.name for c in red.hand]}, turn_log={game.turn_log}',
    )


def test_propaganda_department_target_choice_and_per_target_limit():
    game, red, a, b = make_red_game()
    a.deck.draw_pile = []
    start = game._activated_faction_action(red, '政工部')
    choice = game.pending_choice or {}
    target_index = next((i for i, t in enumerate(choice.get('targets') or []) if t.get('id') == a.id), None)
    resolved = game.resolve_pending_choice(red.id, target_index)
    top_name = a.deck.draw_pile[-1].name if a.deck.draw_pile else None
    repeat = game._activated_faction_action(red, '政工部', target_player_id=a.id)
    top_type = a.deck.draw_pile[-1].card_type if a.deck.draw_pile else None
    supply_after = game.static_purchase_supply.get('內鬥')
    return ok(
        'red_army_propaganda_department_topdecks_internal_conflict_and_limits_same_target',
        start.get('pending_choice') and choice.get('choice_key') == 'red_army_propaganda_department_target' and resolved.get('success') and top_name == '內鬥' and top_type == 'disruption' and supply_after == 0 and repeat.get('error'),
        f'start={start}, choice={game.state().get("pending_choice")}, resolved={resolved}, top={top_name}, top_type={top_type}, supply_after={supply_after}, repeat={repeat}',
    )


def test_propaganda_department_respects_internal_conflict_static_supply_empty():
    game, red, a, b = make_red_game()
    game.static_purchase_supply['內鬥'] = 0
    a.deck.draw_pile = []
    result = game._activated_faction_action(red, '政工部', target_player_id=a.id)
    return ok(
        'red_army_propaganda_department_does_not_create_internal_conflict_when_supply_empty',
        result.get('success') and result.get('result', {}).get('static_supply_empty') and not a.deck.draw_pile and game.static_purchase_supply.get('內鬥') == 0,
        f'result={result}, draw_pile={[c.name for c in a.deck.draw_pile]}, supply={game.static_purchase_supply.get("內鬥")}',
    )


def test_state_security_dissolves_inner_org_within_one_step():
    game, red, a, b = make_red_game()
    a.organizations = {'天津': 1}
    b.organizations = {'上海': 1}
    start = game._activated_faction_action(red, '國安部')
    choice = game.pending_choice or {}
    target_index = next((i for i, t in enumerate(choice.get('targets') or []) if t.get('player_id') == a.id and t.get('town') == '天津'), None)
    resolved = game.resolve_pending_choice(red.id, target_index)
    return ok(
        'red_army_state_security_dissolves_one_inner_org_within_one_step',
        start.get('pending_choice') and choice.get('choice_key') == 'red_army_state_security_target' and resolved.get('success') and a.organizations.get('天津', 0) == 0,
        f'start={start}, targets={choice.get("targets")}, resolved={resolved}, a_orgs={a.organizations}',
    )


def test_ccdi_discards_any_number_then_draws_equal():
    game, red, a, b = make_red_game()
    red.hand = [Card('手牌1', 'money', {'money': 1}), Card('手牌2', 'propaganda', {'propaganda': 1})]
    red.deck.draw_pile = [Card('補牌1', 'money', {'money': 1}), Card('補牌2', 'money', {'money': 1})]
    start = game._activated_faction_action(red, '中紀委')
    choice = game.pending_choice or {}
    serialized = game.state().get('pending_choice') or {}
    resolved = game.resolve_pending_choice(red.id, [0, 1])
    names = [c.name for c in red.hand]
    discard_names = [c.name for c in red.deck.discard_pile]
    return ok(
        'red_army_ccdi_discards_any_number_and_draws_equal',
        start.get('pending_choice') and choice.get('choice_key') == 'red_army_ccdi_discard_draw' and serialized.get('min_count') == 0 and resolved.get('success') and names == ['補牌2', '補牌1'] and {'手牌1', '手牌2'} <= set(discard_names),
        f'start={start}, serialized={serialized}, resolved={resolved}, hand={names}, discard={discard_names}',
    )


def test_non_red_cannot_use_red_army_abilities():
    game, red, a, b = make_red_game()
    result = game._activated_faction_action(a, '統戰部')
    return ok('non_red_cannot_use_red_army_abilities', result.get('error'), str(result))


def test_frontend_exposes_red_army_buttons_and_choice_helpers():
    app_js = (ROOT / 'static' / 'app.js').read_text(encoding='utf-8')
    required = [
        "id=\"redArmyAbilityBtn\"",
        "openRedArmyAbilityModal",
        "紅軍能力不再自動彈出",
        "faction === 'red_army' && isMine && (phase === 'event' || phase === 'action')",
        "rawPhase === 'event' || rawPhase === 'action'",
        "'統戰部'",
        "'政工部'",
        "'國安部'",
        "'中紀委'",
        "red_army_state_security_target",
        "red_army_ccdi_discard_draw",
        "<strong>統戰部：</strong>抽 1 張牌。",
        "<strong>政工部：</strong>選擇 1 名非紅軍玩家，將 1 張內鬥放到其牌庫頂；同一目標每回合限 1 次。",
        "<strong>國安部：</strong>選擇其他玩家在紅軍組織 1 格內的 1 個牆內組織瓦解；同一目標每回合限 1 次。",
        "<strong>中紀委：</strong>可棄掉任意張手牌，然後抽等量的牌。",
        'minChoiceCount',
        'maxChoiceCount',
    ]
    html = (ROOT / 'static' / 'index.html').read_text(encoding='utf-8')
    missing = [item for item in required if item not in app_js and item not in html]
    return ok(
        'frontend_exposes_red_army_buttons_and_choice_helpers',
        not missing,
        f'missing={missing}',
    )


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    results = [
        test_united_front_draws_once_per_use_until_non_red_limit(),
        test_propaganda_department_target_choice_and_per_target_limit(),
        test_propaganda_department_respects_internal_conflict_static_supply_empty(),
        test_state_security_dissolves_inner_org_within_one_step(),
        test_ccdi_discards_any_number_then_draws_equal(),
        test_non_red_cannot_use_red_army_abilities(),
        test_frontend_exposes_red_army_buttons_and_choice_helpers(),
    ]
    summary = {
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    out = {'summary': summary, 'results': results}
    with open(RECORD_DIR / 'RED_ARMY_FACTION_ABILITIES_RUNTIME_VALIDATION.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with open(RECORD_DIR / 'RED_ARMY_FACTION_ABILITIES_RUNTIME_VALIDATION.md', 'w', encoding='utf-8') as f:
        f.write('# RED ARMY FACTION ABILITIES RUNTIME VALIDATION\n\n')
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
