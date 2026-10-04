"""Fixed, hand-written authoritative oracle for every mission event card.

This file is the independent source of truth the event audit checks the runtime against. It is
deliberately NOT derived from data/events_structured.v1.1.json: each of the 14 mission cards
(8 main cards + 6 副本 copies) is spelled out in full below, so a wrong number, scope or card name
in the loaded definition (main card, copy, or both together) cannot hide behind the data it is
being checked against. When a card's rules legitimately change, edit this file by hand together
with rules.md and the data file; never regenerate it from the data.

Per card:
  id / name          card identity (副本 copies carry the （副本） suffix)
  trigger            trigger type and EVERY parameter (count, scope, min_cost, card_names, ...)
  success / failure  effect type and EVERY parameter (count, card, scope, max_steps, ...)
  personal           True = tracked, judged and rewarded/penalised per non-Red player
                     (`each_non_red_player` on the trigger)
  timing             when the personal result is judged: always the end of the full round that follows the reveal
                     (every player, Red Army included, acted exactly once; Red's seat is irrelevant)
  special            scope / distance / timing notes that the effect parameters encode
"""

PERSONAL = True
FULL_ROUND_END = 'full_round_end'

# Shared card bodies. The 副本 entries below restate them in full (no references), so the oracle
# stays human-readable; tests assert main card and copy are identical apart from id/name.
MISSION_ORACLE = [
    # ----- 主卡 -----
    {
        'id': 'national_people_congress', 'name': '全國人大召開', 'type': 'mission',
        'trigger': {'type': 'use_faction_ability', 'count': 1, 'each_non_red_player': True},
        'success': {'type': 'draw', 'count': 1},
        'failure': {'type': 'red_dissolve', 'count': 1, 'scope': '牆內'},
        'personal': PERSONAL, 'timing': FULL_ROUND_END,
        'special': '成功者各抽1；失敗者被紅軍瓦解自己1個牆內非根據地組織（無合法目標略過）；盟旗學校只在瓦解實際執行時記給蒙古',
    },
    {
        'id': 'hong_kong_protest', 'name': '香港抗暴之戰', 'type': 'mission',
        'trigger': {'type': 'play_card_with_money', 'count': 1, 'each_non_red_player': True},
        'success': {'type': 'gain_card', 'card': '宣傳家', 'count': 2},
        'failure': {'type': 'discard_self', 'count': 1},
        'personal': PERSONAL, 'timing': FULL_ROUND_END,
        'special': '全部個人結果與棄牌完成後，香港才決定遷移或留在',
    },
    {
        'id': 'major_disaster', 'name': '重大災難', 'type': 'mission',
        'trigger': {'type': 'play_card_with_propaganda', 'count': 1, 'each_non_red_player': True},
        'success': {'type': 'gain_card', 'card': '宣傳家', 'count': 1},
        'failure': {'type': 'discard_self', 'count': 1},
        'personal': PERSONAL, 'timing': FULL_ROUND_END,
        'special': '',
    },
    {
        'id': 'tibet_border_conflict', 'name': '藏印邊境軍事對峙', 'type': 'mission',
        'trigger': {'type': 'build_organization', 'count': 1, 'scope': '牆內', 'each_non_red_player': True},
        'success': {'type': 'move', 'count': 2},
        'failure': {'type': 'none'},
        'personal': PERSONAL, 'timing': FULL_ROUND_END,
        'special': '只計牆內建立組織',
    },
    {
        'id': 'trade_war', 'name': '貿易戰加劇', 'type': 'mission',
        'trigger': {'type': 'buy_card', 'count': 1, 'min_cost': 4, 'card_names': ['英美奧援'],
                    'each_non_red_player': True},
        'success': {'type': 'topdeck_from_discard', 'count': 1},
        'failure': {'type': 'none'},
        'personal': PERSONAL, 'timing': FULL_ROUND_END,
        'special': '購買費用至少4的英美奧援',
    },
    {
        'id': 'east_turkestan_camp', 'name': '東突厥集中營', 'type': 'mission',
        'trigger': {'type': 'play_card_with_propaganda', 'count': 1, 'each_non_red_player': True},
        'success': {'type': 'gain_card', 'card': '宣傳家', 'count': 1},
        'failure': {'type': 'discard_random', 'count': 1},
        'personal': PERSONAL, 'timing': FULL_ROUND_END,
        'special': '失敗者各自被隨機棄1張手牌，紅軍不受影響',
    },
    {
        'id': 'beijing_power_struggle', 'name': '北京政爭', 'type': 'mission',
        'trigger': {'type': 'draw', 'count': 1, 'each_non_red_player': True},
        'success': {'type': 'draw', 'count': 1},
        'failure': {'type': 'none'},
        'personal': PERSONAL, 'timing': FULL_ROUND_END,
        'special': '',
    },
    {
        'id': 'elite_defection', 'name': '紅軍權貴出逃', 'type': 'mission',
        'trigger': {'type': 'move_organization', 'count': 3, 'each_non_red_player': True},
        'success': {'type': 'trash_from_hand_or_discard', 'count': 1},
        'failure': {'type': 'discard_self', 'count': 1},
        'personal': PERSONAL, 'timing': FULL_ROUND_END,
        'special': '累計移動組織3次',
    },
    {
        'id': 'urumqi_incident', 'name': '烏魯木齊七五事件', 'type': 'mission',
        'trigger': {'type': 'end_turn_state', 'count': 1, 'condition': 'own_organization_in_scope',
                    'scope': '牆內', 'each_non_red_player': True},
        'success': {'type': 'build_organization_near_own', 'count': 1, 'max_steps': 1},
        'failure': {'type': 'discard_random', 'count': 1},
        'personal': PERSONAL, 'timing': FULL_ROUND_END,
        'special': '狀態型：整輪結束時才檢查是否仍有牆內組織；成功者在己方組織1格內免費建立（無合法城鎮略過）',
    },
    # ----- 副本 -----
    {
        'id': 'second_major_disaster', 'name': '重大災難（副本）', 'type': 'mission',
        'trigger': {'type': 'play_card_with_propaganda', 'count': 1, 'each_non_red_player': True},
        'success': {'type': 'gain_card', 'card': '宣傳家', 'count': 1},
        'failure': {'type': 'discard_self', 'count': 1},
        'personal': PERSONAL, 'timing': FULL_ROUND_END,
        'special': '',
    },
    {
        'id': 'second_npc', 'name': '全國人大召開（副本）', 'type': 'mission',
        'trigger': {'type': 'use_faction_ability', 'count': 1, 'each_non_red_player': True},
        'success': {'type': 'draw', 'count': 1},
        'failure': {'type': 'red_dissolve', 'count': 1, 'scope': '牆內'},
        'personal': PERSONAL, 'timing': FULL_ROUND_END,
        'special': '與主卡相同',
    },
    {
        'id': 'second_trade_war', 'name': '貿易戰加劇（副本）', 'type': 'mission',
        'trigger': {'type': 'buy_card', 'count': 1, 'min_cost': 4, 'card_names': ['英美奧援'],
                    'each_non_red_player': True},
        'success': {'type': 'topdeck_from_discard', 'count': 1},
        'failure': {'type': 'none'},
        'personal': PERSONAL, 'timing': FULL_ROUND_END,
        'special': '與主卡相同',
    },
    {
        'id': 'second_border_conflict', 'name': '藏印邊境軍事對峙（副本）', 'type': 'mission',
        'trigger': {'type': 'build_organization', 'count': 1, 'scope': '牆內', 'each_non_red_player': True},
        'success': {'type': 'move', 'count': 2},
        'failure': {'type': 'none'},
        'personal': PERSONAL, 'timing': FULL_ROUND_END,
        'special': '與主卡相同',
    },
    {
        'id': 'second_elite_defection', 'name': '紅軍權貴出逃（副本）', 'type': 'mission',
        'trigger': {'type': 'move_organization', 'count': 3, 'each_non_red_player': True},
        'success': {'type': 'trash_from_hand_or_discard', 'count': 1},
        'failure': {'type': 'discard_self', 'count': 1},
        'personal': PERSONAL, 'timing': FULL_ROUND_END,
        'special': '與主卡相同',
    },
]

ORACLE_BY_NAME = {card['name']: card for card in MISSION_ORACLE}
DEFINITION_KEYS = ('id', 'name', 'type', 'trigger', 'success', 'failure')


def definition_mismatches(loaded_events):
    """Differences between the runtime-loaded mission definitions and this oracle ([] = identical).

    Compares the complete definitions (every key and parameter), the set of mission cards in
    both directions, and the personal-tracking flag (`each_non_red_player`)."""
    problems = []
    missions = [e for e in loaded_events if e.get('type') == 'mission']
    # Validate the raw list before it is keyed by name: a dict would silently swallow duplicates.
    if len(missions) != len(MISSION_ORACLE):
        problems.append(f'mission count runtime={len(missions)} oracle={len(MISSION_ORACLE)}')
    for field in ('id', 'name'):
        counts = {}
        for event in missions:
            counts[event.get(field)] = counts.get(event.get(field), 0) + 1
        for value, count in sorted(counts.items(), key=lambda item: str(item[0])):
            if count > 1:
                problems.append(f'{field} {value!r}: duplicated {count}x in runtime missions')
    loaded = {e.get('name'): e for e in missions}
    for name in sorted(set(ORACLE_BY_NAME) - set(loaded)):
        problems.append(f'{name}: in oracle but missing from runtime')
    for name in sorted(set(loaded) - set(ORACLE_BY_NAME)):
        problems.append(f'{name}: loaded at runtime but not in oracle')
    for name, expected in ORACLE_BY_NAME.items():
        actual = loaded.get(name)
        if actual is None:
            continue
        for key in DEFINITION_KEYS:
            if actual.get(key) != expected.get(key):
                problems.append(f'{name}: {key} runtime={actual.get(key)!r} oracle={expected.get(key)!r}')
        extra = sorted(set(actual) - set(DEFINITION_KEYS))
        if extra:
            problems.append(f'{name}: unexpected extra keys {extra}')
        personal = bool((actual.get('trigger') or {}).get('each_non_red_player'))
        if personal != expected['personal']:
            problems.append(f'{name}: personal flag runtime={personal} oracle={expected["personal"]}')
    return problems
