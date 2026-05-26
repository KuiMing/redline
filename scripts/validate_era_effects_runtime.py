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

    # Uyghur play-card hook: armed card grants 2 propaganda when played.
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
