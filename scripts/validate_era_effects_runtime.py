#!/usr/bin/env python3
import json
import random
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase

RECORD_DIR = BASE / 'docs' / 'records' / 'event-cards'
OUT_JSON = RECORD_DIR / 'ERA_EFFECTS_RUNTIME_VALIDATION.json'
OUT_MD = RECORD_DIR / 'ERA_EFFECTS_RUNTIME_VALIDATION.md'


def make_game(actor_faction='hong_kong'):
    random.seed(20260526)
    game = Game([('actor', 'actor'), ('red', 'red')], market_mode='all_cards')
    actor = game.players[0]
    red = game.players[1]
    actor.id = 'actor'
    actor.name = 'actor'
    actor.faction_id = actor_faction
    actor.resources = {'money': 0, 'propaganda': 0}
    actor.organizations = {}
    red.id = 'red'
    red.name = 'red'
    red.faction_id = 'red_army'
    red.organizations = {'北京': 1}
    game.current_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.winner = None
    return game, actor, red


def first_towns(game, region, count):
    towns = game._towns_for_region_alias(region)
    assert len(towns) >= count, f'{region} only has {len(towns)} towns'
    return towns[:count]


def first_developable_towns(game, player, region, count):
    towns = [town for town in game._towns_for_region_alias(region) if game.can_faction_develop_in_town(player.faction_id, town)]
    assert len(towns) >= count, f'{region} only has {len(towns)} developable towns for {player.faction_id}'
    return towns[:count]


def first_out_of_range_developable_pair(game, player, region):
    towns = first_developable_towns(game, player, region, 2)
    all_towns = [town for town in game._towns_for_region_alias(region) if game.can_faction_develop_in_town(player.faction_id, town)]
    for origin in towns:
        neighbors = set(game.map.get('towns', {}).get(origin, {}).get('road', []) or []) | set(game.map.get('towns', {}).get(origin, {}).get('rail', []) or [])
        for target in all_towns:
            if target != origin and target not in neighbors:
                return origin, target
    raise AssertionError(f'No out-of-range developable pair for {player.faction_id} in {region}')


def place_orgs(player, towns, count_each=1):
    player.organizations = {town: count_each for town in towns}


def check(name, passed, details):
    return {'name': name, 'passed': bool(passed), 'details': details}


def discard_count(player, name):
    return sum(1 for card in player.deck.discard_pile if getattr(card, 'name', str(card)) == name)


def run_checks():
    checks = []

    # Mongolia red_suppression adds 內鬥 to discard through static supply.
    game, actor, _red = make_game('mongol')
    before_supply = game.static_purchase_supply.get('內鬥')
    game.era_engine.activate_era('mongolia')
    runtime_effects = game._apply_era_activation_effects(game.era_engine.get_definition('mongolia'))
    after_supply = game.static_purchase_supply.get('內鬥')
    checks.append(check(
        'mongolia_adds_internal_conflict_with_static_supply_cap',
        'mongolia' in game.era_engine.get_active_eras()
        and discard_count(actor, '內鬥') == 1
        and before_supply == 1
        and after_supply == 0,
        {
            'rule': '蒙古時代關卡 activation effect 將內鬥加入蒙古棄牌堆，但最多消耗既有 static supply。',
            'active_eras': game.era_engine.get_active_eras(),
            'discard_internal_conflict': discard_count(actor, '內鬥'),
            'supply_before': before_supply,
            'supply_after': after_supply,
            'runtime_effects': runtime_effects,
        }
    ))

    # Taiwan uses the same static-supply path for 內鬥.
    game, actor, _red = make_game('taiwan_green')
    place_orgs(actor, first_towns(game, 'taiwan', 1), count_each=7)
    game._check_era_trigger()
    checks.append(check(
        'taiwan_adds_internal_conflict_to_discard',
        'taiwan' in game.era_engine.get_active_eras()
        and discard_count(actor, '內鬥') == 1
        and game.static_purchase_supply.get('內鬥') == 0,
        {
            'rule': '臺灣時代關卡觸發時，將內鬥加入臺灣棄牌堆並消耗 static supply。',
            'active_eras': game.era_engine.get_active_eras(),
            'discard_internal_conflict': discard_count(actor, '內鬥'),
            'supply_after': game.static_purchase_supply.get('內鬥'),
            'runtime_effects': game.era_notification.get('runtime_effects') if game.era_notification else None,
        }
    ))

    # Manchuria uses the same static-supply path for 分神.
    game, actor, _red = make_game('manchuria')
    game.era_engine.activate_era('manchuria')
    runtime_effects = game._apply_era_activation_effects(game.era_engine.get_definition('manchuria'))
    checks.append(check(
        'manchuria_adds_distraction_to_discard',
        'manchuria' in game.era_engine.get_active_eras()
        and discard_count(actor, '分神') == 1
        and game.static_purchase_supply.get('分神') == 0,
        {
            'rule': '滿洲時代關卡 activation effect 將分神加入滿洲棄牌堆並消耗 static supply。',
            'active_eras': game.era_engine.get_active_eras(),
            'discard_distraction': discard_count(actor, '分神'),
            'supply_after': game.static_purchase_supply.get('分神'),
            'runtime_effects': runtime_effects,
        }
    ))

    # Kazakh immediate draw is applied when the era activates.
    game, actor, _red = make_game('kazakh')
    north_towns = [
        town for town, info in game.map.get('towns', {}).items()
        if '北國' in (info.get('ruler') or [])
    ][:7]
    china_towns = first_towns(game, 'china', 3)
    actor.organizations = {town: 1 for town in north_towns + china_towns}
    hand_before = len(actor.hand)
    game._check_era_trigger()
    hand_after = len(actor.hand)
    checks.append(check(
        'kazakh_immediate_draw_two_on_activation',
        'kazakh' in game.era_engine.get_active_eras() and hand_after - hand_before == 2,
        {
            'rule': '哈薩克時代關卡觸發時，哈薩克立即抽 2 張牌。',
            'active_eras': game.era_engine.get_active_eras(),
            'hand_before': hand_before,
            'hand_after': hand_after,
            'runtime_effects': game.era_notification.get('runtime_effects') if game.era_notification else None,
        }
    ))

    # Hong Kong active era reduces armed purchase money cost by 2.
    game, actor, _red = make_game('hong_kong')
    game.era_engine.activate_era('hong_kong')
    armed = Card('武裝小隊', 'armed', {'money': 0, 'propaganda': 0})
    game.purchase_area = game._static_purchase_cards() + [armed]
    actor.resources = {'money': 1, 'propaganda': 0}
    result = game.buy_card(len(game._static_purchase_cards()))
    checks.append(check(
        'hong_kong_armed_purchase_cost_reduced_by_two_money',
        result.get('success') is True
        and actor.resources.get('money') == 0
        and discard_count(actor, '武裝小隊') == 1,
        {
            'rule': '香港時代關卡生效時，香港購買武裝類卡牌費用減 2 資金；武裝小隊原價 3 資金，1 資金可購買。',
            'buy_result': result,
            'remaining_money': actor.resources.get('money'),
            'discard_armed': discard_count(actor, '武裝小隊'),
            'active_era_effects': game.era_engine.get_active_era_details(),
        }
    ))

    # Hong Kong red suppression hook: Red Army spy card resolves, then target discards 1 card.
    game, actor, red = make_game('hong_kong')
    game.current_player_index = game.players.index(red)
    game.era_engine.activate_era('hong_kong')
    actor.organizations = {'天津': 1}
    actor.hand = [Card('香港目標手牌', 'money', {'money': 1})]
    actor.deck.discard_pile = []
    red.organizations = {'北京': 1}
    red.hand = [Card('內應間諜', 'spy', {'propaganda': 2})]
    red.resources = {'money': 0, 'propaganda': 0}
    play_result = game.play_card(0, mode='action', target_player_id=actor.id)
    spy_choice = dict(game.pending_choice or {})
    spy_index = next((i for i, entry in enumerate(spy_choice.get('targets') or []) if entry.get('player_id') == actor.id and entry.get('town') == '天津'), None)
    spy_result = game.resolve_pending_choice(red.id, spy_index) if spy_index is not None else {'error': 'spy target not found'}
    discard_choice = dict(game.pending_choice or {})
    discard_result = game.resolve_pending_choice(actor.id, 0)
    checks.append(check(
        'hong_kong_red_spy_play_forces_bonus_discard_after_spy_resolution',
        play_result.get('success') is True
        and spy_choice.get('choice_key') == 'card_dissolve_interaction'
        and spy_result.get('success') is True
        and spy_result.get('pending_choice') is True
        and discard_choice.get('choice_key') == 'era_bonus_discard_on_red_card'
        and discard_result.get('success') is True
        and actor.organizations.get('天津', 0) == 0
        and discard_count(actor, '香港目標手牌') == 1,
        {
            'rule': '香港紅軍壓制效果：紅軍打出間諜類卡牌並完成原本目標選擇後，香港玩家再以既有 card choice UI 棄 1 張手牌。',
            'play_result': play_result,
            'spy_choice_key': spy_choice.get('choice_key'),
            'spy_result': spy_result,
            'discard_choice_key': discard_choice.get('choice_key'),
            'discard_prompt': discard_choice.get('prompt'),
            'discard_result': discard_result,
            'actor_orgs_after': dict(actor.organizations),
            'actor_discard_count': discard_count(actor, '香港目標手牌'),
            'era_effects_applied': game.turn_log.get('era_effects_applied'),
        }
    ))


    # Era notification payloads must be complete enough for the achievement modal; no UI fallback 暫缺 text.
    game, _actor, _red = make_game('hong_kong')
    notification_details = {}
    missing_notifications = []
    for era in game.structured_eras:
        payload = game._era_notification_payload(era)
        fields = {
            'trigger_text': payload.get('trigger_text'),
            'success_text': payload.get('success_text'),
            'fail_text': payload.get('fail_text'),
            'duration_text': payload.get('duration_text'),
        }
        notification_details[era.get('id')] = fields
        if any(not value or '暫缺' in str(value) for value in fields.values()):
            missing_notifications.append({'id': era.get('id'), 'fields': fields})
    checks.append(check(
        'era_notification_payloads_have_complete_ui_text',
        not missing_notifications,
        {
            'rule': '時代關卡達成 modal 應顯示觸發條件、紅軍壓制、革命反撲與期限文字，不應出現暫缺 fallback。',
            'missing_notifications': missing_notifications,
            'notification_details': notification_details,
        }
    ))

    # Mongolia/Tibet-style resource-card bonus: propaganda card played as resource grants +1 propaganda.
    game, actor, _red = make_game('mongol')
    game.era_engine.activate_era('mongolia')
    actor.hand = [Card('宣傳家', 'propaganda', {'propaganda': 2})]
    actor.resources = {'money': 0, 'propaganda': 0}
    result = game.play_card(0, mode='resource')
    checks.append(check(
        'mongolia_propaganda_resource_card_bonus_adds_one_propaganda',
        result.get('success') is True and actor.resources.get('propaganda') == 3,
        {
            'rule': '蒙古反撲效果：宣傳類手牌用於購買/資源時額外提供 1 宣傳。',
            'play_result': result,
            'resources_after': dict(actor.resources),
            'era_effects_applied': game.turn_log.get('era_effects_applied'),
        }
    ))

    # Uyghur counterattack hook: Uyghur armed card grants 2 propaganda when played.
    game, actor, red = make_game('uyghur_istanbul')
    game.era_engine.activate_era('uyghur')
    actor.organizations = {'北京': 1}
    red.organizations = {'北京': 1}
    red.hand = [Card('目標手牌', 'money', {'money': 1})]
    actor.hand = [Card('武裝者', 'armed', {'propaganda': 1})]
    actor.resources = {'money': 0, 'propaganda': 0}
    result = game.play_card(0, mode='action', target_player_id='red')
    checks.append(check(
        'uyghur_armed_play_grants_two_propaganda',
        result.get('success') is True
        and result.get('pending_choice') is True
        and actor.resources.get('propaganda') == 2,
        {
            'rule': '維吾爾反撲效果：每打出 1 張武裝類卡牌，獲得 2 宣傳。',
            'play_result': result,
            'resources_after': dict(actor.resources),
            'pending_choice': game.pending_choice.get('choice_key') if game.pending_choice else None,
            'era_effects_applied': game.turn_log.get('era_effects_applied'),
        }
    ))

    # Uyghur red suppression hook: Red Army armed card asks target to discard, then dissolves 1 Uyghur org within 1 step.
    game, actor, red = make_game('uyghur_istanbul')
    game.current_player_index = game.players.index(red)
    game.era_engine.activate_era('uyghur')
    actor.organizations = {'天津': 1}
    actor.hand = [Card('維吾爾目標手牌', 'money', {'money': 1})]
    red.organizations = {'北京': 1}
    red.hand = [Card('武裝者', 'armed', {'propaganda': 1})]
    red.resources = {'money': 0, 'propaganda': 0}
    play_result = game.play_card(0, mode='action', target_player_id='actor')
    discard_choice = dict(game.pending_choice or {})
    discard_result = game.resolve_pending_choice(actor.id, 0)
    dissolve_choice = dict(game.pending_choice or {})
    dissolve_index = next((i for i, entry in enumerate(dissolve_choice.get('targets') or []) if entry.get('player_id') == actor.id and entry.get('town') == '天津'), None)
    dissolve_result = game.resolve_pending_choice(red.id, dissolve_index) if dissolve_index is not None else {'error': 'target not found'}
    checks.append(check(
        'uyghur_red_armed_play_dissolves_uyghur_org_after_discard_choice',
        play_result.get('success') is True
        and discard_choice.get('choice_key') == 'armed_target_discard'
        and discard_result.get('pending_choice') is True
        and dissolve_choice.get('choice_key') == 'era_red_bonus_dissolve_target'
        and dissolve_result.get('success') is True
        and actor.organizations.get('天津', 0) == 0
        and discard_count(actor, '維吾爾目標手牌') == 1,
        {
            'rule': '維吾爾紅軍壓制效果：紅軍打出武裝類卡牌後，在既有武裝棄牌 pending choice 完成後，選擇 1 個紅軍組織 1 格內的維吾爾組織瓦解。',
            'play_result': play_result,
            'discard_choice_key': discard_choice.get('choice_key'),
            'discard_result': discard_result,
            'dissolve_choice_key': dissolve_choice.get('choice_key'),
            'dissolve_targets': dissolve_choice.get('targets'),
            'dissolve_result': dissolve_result,
            'actor_orgs_after': dict(actor.organizations),
            'actor_discard_count': discard_count(actor, '維吾爾目標手牌'),
            'era_effects_applied': game.turn_log.get('era_effects_applied'),
        }
    ))


    # Manchuria counterattack: inspect top 7, select 2 in order, and place them back on deck top.
    game, actor, _red = make_game('manchuria')
    actor.deck.draw_pile = [Card(f'底牌{i}', 'command', {}) for i in range(3)] + [
        Card('第七張', 'command', {}),
        Card('第六張', 'command', {}),
        Card('第五張', 'command', {}),
        Card('第四張', 'command', {}),
        Card('第三張', 'command', {}),
        Card('第二張', 'command', {}),
        Card('第一張', 'command', {}),
    ]
    game.era_engine.activate_era('manchuria')
    runtime_effects = game._apply_era_activation_effects(game.era_engine.get_definition('manchuria'))
    reorder_choice = dict(game.pending_choice or {})
    resolve_result = game.resolve_pending_choice(actor.id, [2, 0])
    draw_result = [getattr(card, 'name', str(card)) for card in actor.deck.draw(2)]
    checks.append(check(
        'manchuria_inspects_top_seven_and_reorders_two_to_top',
        runtime_effects.get('revolution_counterattack', {}).get('status') == 'pending_reorder_choice'
        and reorder_choice.get('choice_key') == 'era_inspect_deck_top_and_reorder'
        and [getattr(card, 'name', str(card)) for card in (reorder_choice.get('cards') or [])] == ['第一張', '第二張', '第三張', '第四張', '第五張', '第六張', '第七張']
        and resolve_result.get('success') is True
        and resolve_result.get('chosen_cards') == ['第三張', '第一張']
        and draw_result == ['第三張', '第一張'],
        {
            'rule': '滿洲革命反撲效果：檢視牌庫頂 7 張，依玩家點選順序選 2 張放回牌庫頂。',
            'runtime_effects': runtime_effects,
            'choice_key': reorder_choice.get('choice_key'),
            'choice_count': reorder_choice.get('count'),
            'inspected_cards': [getattr(card, 'name', str(card)) for card in (reorder_choice.get('cards') or [])],
            'resolve_result': resolve_result,
            'first_two_drawn_after_reorder': draw_result,
            'era_effects_applied': game.turn_log.get('era_effects_applied'),
        }
    ))

    # Taiwan build hook: building in Taiwan region grants 1 propaganda.
    game, actor, _red = make_game('taiwan_green')
    game.era_engine.activate_era('taiwan')
    taiwan_town = first_towns(game, 'taiwan', 1)[0]
    actor.organizations = {taiwan_town: 1}
    actor.resources = {'money': 0, 'propaganda': 0}
    result = game.build_organization(taiwan_town)
    checks.append(check(
        'taiwan_build_in_taiwan_grants_one_propaganda',
        result.get('success') is True and actor.resources.get('propaganda') == 1,
        {
            'rule': '臺灣反撲效果：在臺灣城鎮建立至少 1 個組織時，獲得 1 宣傳。',
            'town': taiwan_town,
            'build_result': result,
            'resources_after': dict(actor.resources),
            'era_effects_applied': game.turn_log.get('era_effects_applied'),
        }
    ))

    # Rebel build-count hook: third build in the turn draws once, then only once.
    game, actor, _red = make_game('liberals')
    game.era_engine.activate_era('rebels')
    china_towns = first_developable_towns(game, actor, 'china', 3)
    actor.organizations = {town: 1 for town in china_towns}
    hand_before = len(actor.hand)
    results = [game.build_organization(town) for town in china_towns]
    hand_after = len(actor.hand)
    checks.append(check(
        'rebels_third_build_draws_one_card_once',
        all(r.get('success') is True for r in results)
        and hand_after - hand_before == 1
        and game.turn_log.get('era_build_count_draw_bonus:rebels') is True,
        {
            'rule': '反賊反撲效果：回合中建立至少 3 個組織時，當回合抽 1 張；同一回合只觸發一次。',
            'towns': china_towns,
            'build_results': results,
            'hand_before': hand_before,
            'hand_after': hand_after,
            'era_effects_applied': game.turn_log.get('era_effects_applied'),
        }
    ))

    # Kazakh/Rebel suppression hook: active restriction blocks ignore-distance builds in China.
    game, actor, _red = make_game('kazakh')
    game.era_engine.activate_era('kazakh')
    origin, target = first_out_of_range_developable_pair(game, actor, 'china')
    actor.organizations = {origin: 1}
    game.event_modifiers.append({'type': 'ignore_distance', 'remaining_turns': 1, 'duration': 1})
    result = game.build_organization_with_support(origin, target)
    checks.append(check(
        'kazakh_restricts_ignore_distance_build_in_china',
        result.get('error') == 'Target out of build range',
        {
            'rule': '哈薩克紅軍壓制效果：此後無法再無視距離建立牆內組織。',
            'origin': origin,
            'target': target,
            'build_result': result,
            'active_eras': game.era_engine.get_active_eras(),
        }
    ))

    # Tibet red suppression: Red Army discards a hand card, then builds near a Tibet organization.
    game, actor, red = make_game('tibet')
    tibet_town = next(town for town in game._towns_for_region_alias('tibet_region') if game.can_faction_develop_in_town('red_army', town))
    actor.organizations = {tibet_town: 1}
    red.hand = [Card('紅軍棄牌測試', 'money', {'money': 1})]
    red.organizations = {'北京': 1}
    game.era_engine.activate_era('tibet')
    runtime_effects = game._apply_era_activation_effects(game.era_engine.get_definition('tibet'))
    first_choice = dict(game.pending_choice or {})
    discard_result = game.resolve_pending_choice(red.id, 0)
    build_choice = dict(game.pending_choice or {})
    build_index = next(i for i, entry in enumerate(build_choice.get('towns') or []) if entry.get('town') == tibet_town)
    build_result = game.resolve_pending_choice(red.id, build_index)
    checks.append(check(
        'tibet_red_discards_then_builds_near_tibet_org',
        runtime_effects.get('red_suppression', {}).get('status') == 'pending_discard_choice'
        and first_choice.get('choice_key') == 'era_red_discard_to_build_near_target'
        and discard_result.get('pending_choice') is True
        and build_choice.get('choice_key') == 'era_red_build_near_target'
        and build_result.get('success') is True
        and discard_count(red, '紅軍棄牌測試') == 1
        and red.organizations.get(tibet_town) == 1,
        {
            'rule': '藏國紅軍壓制效果：紅軍棄 1 張手牌後，在藏國組織 1 格內免費建立 1 個紅軍組織。',
            'tibet_org_town': tibet_town,
            'runtime_effects': runtime_effects,
            'first_choice_key': first_choice.get('choice_key'),
            'discard_result': discard_result,
            'build_choice_key': build_choice.get('choice_key'),
            'build_town_count': len(build_choice.get('towns') or []),
            'build_result': build_result,
            'red_discard_count': discard_count(red, '紅軍棄牌測試'),
            'red_orgs': dict(red.organizations),
            'era_effects_applied': game.turn_log.get('era_effects_applied'),
        }
    ))

    return checks


def write_records(checks):
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        'total': len(checks),
        'passed': sum(1 for c in checks if c['passed']),
        'failed': sum(1 for c in checks if not c['passed']),
    }
    payload = {
        'date': date.today().isoformat(),
        'summary': summary,
        'checks': checks,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    lines = [
        '# Era Effects Runtime Validation',
        '',
        f'- Date: {payload["date"]}',
        f'- Summary: {summary["passed"]}/{summary["total"]} passed',
        '',
    ]
    for item in checks:
        mark = 'PASS' if item['passed'] else 'FAIL'
        lines.append(f'## {mark}: {item["name"]}')
        lines.append('')
        lines.append('```json')
        lines.append(json.dumps(item['details'], ensure_ascii=False, indent=2))
        lines.append('```')
        lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    return payload


def main():
    checks = run_checks()
    payload = write_records(checks)
    print(json.dumps(payload['summary'], ensure_ascii=False))
    if payload['summary']['failed']:
        for item in checks:
            if not item['passed']:
                print(json.dumps(item, ensure_ascii=False, indent=2))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
