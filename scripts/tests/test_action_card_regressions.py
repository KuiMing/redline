from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.effect_engine import EffectEngine
from server.game import Game, GamePhase, TurnPhase


def pin_noop_event(g):
    # Game 初始化會隨機抽該輪事件；抽到互動型事件（如 一帶一路 的 auto build）會在打牌時
    # 插入事件自己的 pending choice，污染這裡的行動卡單元測試。固定換成無效果的歲月靜好，
    # 讓測試只驗卡片行為、與事件運氣脫鉤。
    g.current_event = dict(g._event_by_name('歲月靜好'))
    g.event_progress = {'count': 0, 'required': 0, 'succeeded': True, 'settled': True, 'status': 'idle'}
    g.event_modifiers = []
    g.pending_choice = None
    return g


def make_game():
    g = Game([('p1', 'P1'), ('p2', 'P2')])
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.pending_base_choices = {}
    g.players[0].faction_id = 'red_army'
    return pin_noop_event(g)


def card(g, name):
    c = next(c for c in g.structured_cards if c['name'] == name)
    return Card(c['name'], c['type'], c.get('resources', {}))


def names(cards):
    result = []
    for c in cards:
        if isinstance(c, dict) and 'card' in c:
            c = c['card']
        result.append(getattr(c, 'name', str(c)))
    return result


def play_only(g, name):
    p = g.current_player()
    p.hand = [card(g, name)]
    p.resources = {'money': 0, 'propaganda': 0}
    result = g.play_card(0, mode='action')
    assert result.get('success'), result
    return p


def resolve_build_town(g, player, town):
    # 建組織效果現在是互動式選城鎮（card_build_organization / town_choice），
    # 不再自動蓋在當前城鎮；測試用此 helper 選定城鎮完成建造。
    assert g.pending_choice and g.pending_choice['choice_key'] == 'card_build_organization', g.pending_choice
    towns = [entry['town'] for entry in g.pending_choice['towns']]
    assert town in towns, (town, towns)
    return g.resolve_pending_choice(player.id, towns.index(town))


def resolve_first_build_town(g, player):
    assert g.pending_choice and g.pending_choice['choice_key'] == 'card_build_organization', g.pending_choice
    town = g.pending_choice['towns'][0]['town']
    return town, g.resolve_pending_choice(player.id, 0)


def test_press_advantage_prompts_for_eligible_discard_card_and_leaves_high_cost_cards():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '乘勝追擊')]
    p.deck.discard_pile = [
        card(g, '宣傳家'),      # total cost 3: eligible
        card(g, '合作談判'),    # total cost 4: ineligible, should not be offered
        card(g, '走漏風聲'),    # total cost 2: eligible
    ]

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'gain_from_discard'
    assert g.pending_choice['source_name'] == '乘勝追擊'
    assert g.pending_choice['max_cost'] == 3
    assert names(g.pending_choice['cards']) == ['宣傳家', '走漏風聲']
    assert names(p.deck.discard_pile) == ['宣傳家', '合作談判', '走漏風聲', '乘勝追擊']

    resolved = g.resolve_pending_choice(p.id, 1)

    assert resolved.get('success'), resolved
    assert resolved.get('chosen_card') == '走漏風聲'
    assert names(p.hand) == ['走漏風聲']
    assert names(p.deck.discard_pile) == ['宣傳家', '合作談判', '乘勝追擊']
    assert g.pending_choice is None
    assert any('gained 走漏風聲 from discard via 乘勝追擊' in entry for entry in g.action_log)



def test_recruit_talent_selects_any_card_from_own_deck_not_topdeck_only():
    g = make_game()
    p = g.current_player()
    p.faction_id = 'tibet_dehradun'
    p.hand = [card(g, '網羅人才')]
    # Deck top is TopCard (last element). DesiredCard is deliberately not on top.
    p.deck.draw_pile = [Card('DesiredCard', 'command', {}), Card('MiddleCard', 'command', {}), Card('TopCard', 'command', {})]
    p.deck.discard_pile = [Card('DiscardOnly', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'recruit_talent'
    assert names(g.pending_choice['cards']) == ['DesiredCard', 'MiddleCard', 'TopCard']
    resolved = g.resolve_pending_choice(p.id, 0)
    assert resolved.get('success'), resolved
    assert 'DesiredCard' in names(p.hand)
    assert 'TopCard' not in names(p.hand)
    # 卡面規則是「任選 1 張加入手牌，而後將牌庫洗牌」——沒被選中的 MiddleCard／TopCard
    # 應該留在牌庫裡被洗牌，不能連同 DesiredCard 一起憑空消失（2026-08-03 稽核修正：
    # 舊版程式碼會把候選清單裡除了被選中那張以外的每一張都從牌庫／棄牌堆刪除）。
    assert sorted(names(p.deck.draw_pile)) == ['MiddleCard', 'TopCard']
    assert 'DiscardOnly' in names(p.deck.discard_pile)


def test_recruit_talent_does_not_destroy_the_rest_of_the_deck_it_only_moves_the_chosen_card():
    """2026-08-03 playtest 回報：紅軍使用網羅人才時有時只顯示棄牌堆，漏掉己方牌庫。
    根本原因不是候選投影或畫面顯示，而是 `_resolve_card_choice` 的 `recruit_talent`
    分支把候選清單裡「除了被選中那張以外」的每一張牌都從牌庫／棄牌堆刪除，等同銷毀
    玩家整副牌庫——上一次使用就已經把牌庫清空了，導致下一次自然只剩棄牌堆有候選。
    這裡直接對照修正前／修正後的牌庫總量，確認沒被選中的候選牌全部原地保留。"""
    g = make_game()
    p = g.current_player()
    p.faction_id = 'red_army'
    p.hand = [card(g, '網羅人才')]
    p.deck.draw_pile = [Card('DrawA', 'command', {}), Card('DrawB', 'command', {}), Card('DrawC', 'command', {})]
    p.deck.discard_pile = [Card('DiscardX', 'command', {}), Card('DiscardY', 'command', {})]

    g.play_card(0, mode='action')
    resolved = g.resolve_pending_choice(p.id, 0)  # choose DrawA (first candidate)

    assert resolved.get('success'), resolved
    assert names(p.hand) == ['DrawA']
    # 五張候選（DrawA/B/C + DiscardX/Y）除了被選走加入手牌的 DrawA，其餘四張都應該
    # 還在牌庫或棄牌堆裡，沒有一張憑空消失。（棄牌堆裡另外多一張是打出的網羅人才本身。）
    assert sorted(names(p.deck.draw_pile)) == ['DrawB', 'DrawC']
    assert sorted(names(p.deck.discard_pile)) == ['DiscardX', 'DiscardY', '網羅人才']


def test_red_army_recruit_talent_can_select_from_own_deck_or_discard():
    g = make_game()
    p = g.current_player()
    p.faction_id = 'red_army'
    p.hand = [card(g, '網羅人才')]
    p.deck.draw_pile = [Card('DeckChoiceA', 'command', {}), Card('DeckChoiceB', 'command', {})]
    p.deck.discard_pile = [Card('DiscardChoice', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'recruit_talent'
    assert names(g.pending_choice['cards']) == ['DeckChoiceA', 'DeckChoiceB', 'DiscardChoice']
    assert g.state()['pending_choice']['cards'] == [
        {'name': 'DeckChoiceA', 'zone': 'draw_pile', 'zone_label': '牌庫'},
        {'name': 'DeckChoiceB', 'zone': 'draw_pile', 'zone_label': '牌庫'},
        {'name': 'DiscardChoice', 'zone': 'discard_pile', 'zone_label': '棄牌堆'},
    ]

    resolved = g.resolve_pending_choice(p.id, 2)

    assert resolved.get('success'), resolved
    assert resolved.get('source_zone') == 'discard_pile'
    assert names(p.hand) == ['DiscardChoice']
    assert names(p.deck.discard_pile) == ['網羅人才']
    # 沒被選中的 DeckChoiceA／DeckChoiceB 是牌庫候選，選了棄牌堆裡的牌之後，這兩張
    # 應該留在牌庫裡（後面會被洗牌），不能被一併刪除（2026-08-03 稽核修正）。
    assert sorted(names(p.deck.draw_pile)) == ['DeckChoiceA', 'DeckChoiceB']
    assert g.pending_choice is None
    assert any('recruited DiscardChoice from discard via 網羅人才' in entry for entry in g.action_log)


def test_red_army_recruit_talent_still_shows_deck_candidates_on_a_second_use():
    """直接重現 2026-08-03 playtest 回報的症狀：紅軍第二次使用網羅人才時，候選清單裡
    只剩棄牌堆、漏掉了牌庫。用兩張網羅人才連續使用來重現——第一次選牌庫裡的牌，
    第二次應該同時看到「牌庫剩下的牌」與「棄牌堆的牌」，而不是只剩棄牌堆。"""
    g = make_game()
    p = g.current_player()
    p.faction_id = 'red_army'
    p.hand = [card(g, '網羅人才'), card(g, '網羅人才')]
    p.deck.draw_pile = [Card('DeckA', 'command', {}), Card('DeckB', 'command', {})]
    p.deck.discard_pile = [Card('DiscardA', 'command', {})]

    g.play_card(0, mode='action')
    first_candidates = names(g.pending_choice['cards'])
    assert first_candidates == ['DeckA', 'DeckB', 'DiscardA']
    resolved_first = g.resolve_pending_choice(p.id, 0)  # pick DeckA
    assert resolved_first.get('success'), resolved_first
    assert resolved_first.get('chosen_card') == 'DeckA'

    g.play_card(0, mode='action')
    second_candidates = sorted(names(g.pending_choice['cards']))
    # DeckB 是牌庫剩下唯一一張，一定要出現在候選裡；棄牌堆則有原本的 DiscardA 加上
    # 第一次打出的網羅人才本身。只要 DeckB 出現，就證明牌庫候選沒有被上一次使用清空。
    assert 'DeckB' in second_candidates, (
        'second use should still show DeckB from the deck, not just the discard pile'
    )
    assert second_candidates == ['DeckB', 'DiscardA', '網羅人才']


def test_red_support_resource_mode_is_a_plain_discard_with_no_resources_for_red_army():
    # 2026-06-07（457d3a2）起奧援卡的資源模式一律改為「不給資源、直接棄置」；紅軍奧援
    # 原本的資源模式（給 1/1 並選反共玩家放入其棄牌堆）已被此裁決取代——紅軍自己打
    # 資源模式就是把牌棄進自己的棄牌堆、不開任何選擇（2026-07-16 起 UI 上這就是「棄置」鈕）。
    g = make_game()
    red = g.current_player()
    rebel = g.players[1]
    rebel.faction_id = 'hong_kong'
    red.hand = [Card('紅軍奧援', 'support', {'money': 1, 'propaganda': 1})]
    red.resources = {'money': 0, 'propaganda': 0}
    rebel.deck.discard_pile = []

    result = g.play_card(0, mode='resource')

    assert result.get('success'), result
    assert result.get('pending_choice') is None
    assert g.pending_choice is None
    assert red.resources == {'money': 0, 'propaganda': 0}
    assert names(red.hand) == []
    assert names(red.deck.discard_pile) == ['紅軍奧援']
    assert names(rebel.deck.discard_pile) == []


def test_red_support_requires_red_army_to_choose_rebel_discard_target_before_resolving_action_mode():
    g = make_game()
    red = g.current_player()
    rebel = g.players[1]
    rebel.faction_id = 'hong_kong'
    red.hand = [Card('紅軍奧援', 'support', {'money': 1, 'propaganda': 1})]
    red.deck.draw_pile = [Card('DrawnCard', 'command', {})]
    rebel.deck.discard_pile = []

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True
    assert names(red.hand) == ['DrawnCard']
    assert names(red.deck.draw_pile) == []
    assert g.pending_choice and g.pending_choice['choice_key'] == 'red_support_target_player'
    assert g.pending_choice['mode'] == 'action'

    resolved = g.resolve_pending_choice(red.id, 0)

    assert resolved.get('success'), resolved
    assert resolved.get('target_player_name') == 'P2'
    assert names(red.hand) == ['DrawnCard']
    assert names(rebel.deck.discard_pile)[-1] == '紅軍奧援'
    assert g.pending_choice is None


def test_taiwan_support_tier1_gains_propaganda_without_opening_target_choice():
    g = make_game()
    actor = g.current_player()
    enemy = g.players[1]

    actor.faction_id = 'taiwan_green'
    actor.base = '東京'
    actor.organizations = {'東京': 1}
    # 東京主導東洋；II 級 OR 裁決（2026-07-11）下第一種變體（東洋/南洋）會達 II 級，
    # 要驗 I 級 fallback 需拿第二種印刷變體（英美/歐洲，2026-07-16 變體裁決）——東洋不在
    # 這張牌自己印的門檻地區裡，才會落在 I 級。
    actor.hand = [g._make_support_card('臺灣奧援', variant_index=1)]
    actor.resources = {'money': 0, 'propaganda': 0}

    enemy.faction_id = 'red_army'
    enemy.base = '北京'
    enemy.organizations = {'北京': 1}

    result = g.play_card(0, mode='action')

    assert result.get('success') is True, result
    assert actor.resources == {'money': 0, 'propaganda': 1}
    assert g.pending_choice is None


def test_north_support_tier_detection_follows_or_semantics_and_card_variant():
    # II 級門檻為 OR（2026-07-11 裁決：主導配對中任一地區即可），且一張牌只看自己
    # 印的那組地區（2026-07-16 變體裁決：變體 0＝歐洲/東洋、變體 1＝天方/印度）。
    g = make_game()
    actor = g.current_player()

    actor.faction_id = 'liberals'
    actor.base = '海參崴'

    variant0 = g._make_support_card('北國奧援', variant_index=0)
    variant1 = g._make_support_card('北國奧援', variant_index=1)

    actor.organizations = {'海參崴': 1}
    tier3 = g._support_card_tier(actor, variant0)
    assert tier3[0] == 3
    assert g._resolve_support_card_effect('北國奧援', tier3[0], tier3[1]) == ('interactive_dissolve_many_near', {'count': 2})

    # 巴黎主導歐洲：對變體 0（歐洲/東洋）單一地區即達 II 級（OR），對變體 1（天方/印度）不匹配、落 I 級。
    actor.organizations = {'巴黎': 1}
    tier2_single = g._support_card_tier(actor, variant0)
    assert tier2_single == (2, 0, ['歐洲'])
    tier1 = g._support_card_tier(actor, variant1)
    assert tier1[0] == 1
    assert g._resolve_support_card_effect('北國奧援', tier1[0], tier1[1]) == ('interactive_dissolve_self_and_enemy', {'count': 1})

    actor.organizations = {'巴黎': 1, '沖繩': 1}
    tier2 = g._support_card_tier(actor, variant0)
    assert tier2 == (2, 0, ['歐洲', '東洋'])
    assert g._resolve_support_card_effect('北國奧援', tier2[0], tier2[1]) == ('interactive_dissolve_many_near', {'count': 1})


def test_north_support_tier1_sacrifices_the_selected_own_org_before_dissolving_enemy():
    g = make_game()
    actor = g.current_player()
    enemy = g.players[1]

    actor.faction_id = 'liberals'
    actor.base = '巴黎'
    actor.organizations = {'巴黎': 1, '日內瓦': 1}
    # 巴黎/日內瓦主導歐洲：變體 0 會因 OR 裁決達 II 級，改拿變體 1（天方/印度）才落 I 級。
    actor.hand = [g._make_support_card('北國奧援', variant_index=1)]
    actor.resources = {'money': 0, 'propaganda': 0}

    enemy.faction_id = 'red_army'
    enemy.base = '北京'
    enemy.organizations = {'慕尼黑': 1}

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert result.get('tier') == 1
    assert result.get('effect_type') == 'interactive_dissolve_self_and_enemy'
    assert g.pending_choice['step'] == 'sacrifice_town'
    assert g.pending_choice['towns'] == [{
        'town': '日內瓦',
        'label': '日內瓦（可瓦解鄰近敵方組織）',
        'target_count': 1,
    }]

    sacrificed = g.resolve_pending_choice(actor.id, 0)

    assert sacrificed.get('success'), sacrificed
    assert sacrificed.get('pending_choice') is True, sacrificed
    assert actor.organizations == {'巴黎': 1}
    assert g.pending_choice['step'] == 'target'
    assert g.pending_choice['targets'] == [{
        'id': f'{enemy.id}::慕尼黑',
        'label': 'P2｜慕尼黑',
        'player_id': enemy.id,
        'town': '慕尼黑',
        'sacrifice_town': '日內瓦',
    }]

    resolved = g.resolve_pending_choice(actor.id, 0)

    assert resolved.get('success'), resolved
    assert actor.organizations == {'巴黎': 1}
    assert enemy.organizations.get('慕尼黑', 0) == 0


def test_taiwan_support_tier3_requires_target_choice_and_builds_in_same_town_after_resolution():
    g = make_game()
    actor = g.current_player()
    enemy = g.players[1]

    actor.faction_id = 'taiwan_green'
    actor.base = '佬沃'
    actor.organizations = {'屏東': 1, '佬沃': 1, '馬祖': 1}
    actor.hand = [g._make_support_card('臺灣奧援')]
    actor.resources = {'money': 0, 'propaganda': 0}
    actor.deck.draw_pile = []
    actor.deck.discard_pile = []

    enemy.faction_id = 'red_army'
    enemy.base = '北京'
    enemy.organizations = {'福州': 1}
    enemy.deck.discard_pile = []

    original_resolver = g._support_card_tier
    def forced_tier(player, card):
        card_name = getattr(card, 'name', str(card))
        if getattr(player, 'id', None) == actor.id and card_name == '臺灣奧援':
            return 3, 0, ['東洋', '南洋']
        return original_resolver(player, card)
    g._support_card_tier = forced_tier

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert result.get('tier') == 3
    assert result.get('effect_type') == 'interactive_dissolve_and_build'
    assert g.pending_choice and g.pending_choice['type'] == 'support_flow_choice'
    assert g.pending_choice['step'] == 'target'
    assert g.pending_choice['source_name'] == '臺灣奧援'
    assert g.pending_choice['context']['effect_type'] == 'interactive_dissolve_and_build'
    assert g.pending_choice['targets'] == [{
        'id': f'{enemy.id}::福州',
        'label': 'P2｜福州',
        'player_id': enemy.id,
        'town': '福州',
        'requires_self_sacrifice': False,
    }]

    state_choice = g.state()['pending_choice']
    assert state_choice['type'] == 'support_flow_choice'
    assert state_choice['step'] == 'target'
    assert state_choice['source_name'] == '臺灣奧援'
    assert state_choice['targets'] == [{
        'id': f'{enemy.id}::福州',
        'label': 'P2｜福州',
        'player_id': enemy.id,
        'town': '福州',
        'requires_self_sacrifice': False,
    }]

    resolved = g.resolve_pending_choice(actor.id, 0)

    assert resolved.get('success'), resolved
    assert enemy.organizations.get('福州', 0) == 0
    assert actor.organizations['福州'] == 1
    assert g.pending_choice is None


def test_taiwan_support_tier3_can_replace_red_army_base_after_second_dissolve_hit():
    """2026-08-04 使用者裁決：紅軍根據地被真正瓦解移除後，臺灣奧援等瓦解＋補位效果應該
    比照瓦解紅軍其他組織城鎮一樣可以直接補上自己的組織，不再永久排除根據地
    （`_can_replace_dissolved_org_with_own` 原本對紅軍根據地的排除已移除）。這裡沿用
    既有「同一攻擊者同一回合需 2 次命中才真正移除」的耐久規則——先預先記一次命中
    （模擬本回合稍早已經瓦解過一次根據地），讓這次透過臺灣奧援的瓦解成為第 2 次命中，
    正確移除根據地組織後才驗證補位成功。"""
    g = make_game()
    actor = g.current_player()
    enemy = g.players[1]

    actor.faction_id = 'taiwan_green'
    actor.base = '佬沃'
    actor.organizations = {'天津': 1, '佬沃': 1, '馬祖': 1}
    actor.hand = [g._make_support_card('臺灣奧援')]
    actor.resources = {'money': 0, 'propaganda': 0}
    actor.deck.draw_pile = []
    actor.deck.discard_pile = []

    enemy.faction_id = 'red_army'
    enemy.base = '北京'
    enemy.organizations = {'北京': 1}
    enemy.deck.discard_pile = []

    g.turn_log['red_army_base_dissolves'] = {f'{actor.id}:北京': 1}

    original_resolver = g._support_card_tier
    def forced_tier(player, card):
        card_name = getattr(card, 'name', str(card))
        if getattr(player, 'id', None) == actor.id and card_name == '臺灣奧援':
            return 3, 0, ['東洋', '南洋']
        return original_resolver(player, card)
    g._support_card_tier = forced_tier

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert result.get('effect_type') == 'interactive_dissolve_and_build'
    assert g.pending_choice['targets'] == [{
        'id': f'{enemy.id}::北京',
        'label': 'P2｜北京',
        'player_id': enemy.id,
        'town': '北京',
        'requires_self_sacrifice': False,
    }]

    resolved = g.resolve_pending_choice(actor.id, 0)

    assert resolved.get('success'), resolved
    assert enemy.organizations.get('北京', 0) == 0
    assert actor.organizations['北京'] == 1
    assert g.pending_choice is None
    assert '北京' in g.turn_log.get('red_army_base_build_blocks', [])


def test_taiwan_support_tier3_cannot_replace_red_army_base_on_first_dissolve_hit():
    """同上一項的另一半：如果這是本回合對紅軍根據地的第 1 次命中（尚未真正移除），
    即使 `_can_replace_dissolved_org_with_own` 的預先篩選把根據地當成候選目標放行，
    `_resolve_support_interaction_result()` 在真正呼叫 `dissolve_organization()` 之後
    對 `_can_player_build_in_town()` 的即時複查仍要正確擋下補位——耐久規則本身沒有被
    這次放寬影響。"""
    g = make_game()
    actor = g.current_player()
    enemy = g.players[1]

    actor.faction_id = 'taiwan_green'
    actor.base = '佬沃'
    actor.organizations = {'天津': 1, '佬沃': 1, '馬祖': 1}
    actor.hand = [g._make_support_card('臺灣奧援')]
    actor.resources = {'money': 0, 'propaganda': 0}
    actor.deck.draw_pile = []
    actor.deck.discard_pile = []

    enemy.faction_id = 'red_army'
    enemy.base = '北京'
    enemy.organizations = {'北京': 1}
    enemy.deck.discard_pile = []

    original_resolver = g._support_card_tier
    def forced_tier(player, card):
        card_name = getattr(card, 'name', str(card))
        if getattr(player, 'id', None) == actor.id and card_name == '臺灣奧援':
            return 3, 0, ['東洋', '南洋']
        return original_resolver(player, card)
    g._support_card_tier = forced_tier

    result = g.play_card(0, mode='action')
    assert result.get('pending_choice') is True, result

    resolved = g.resolve_pending_choice(actor.id, 0)

    assert resolved.get('error') == 'Target could not be replaced after dissolve', resolved
    assert enemy.organizations.get('北京', 0) == 1
    assert '北京' not in (actor.organizations or {})
    assert g.turn_log.get('red_army_base_dissolves', {}).get(f'{actor.id}:北京') == 1


def test_taiwan_support_tier2_requires_target_choice_without_auto_resolution():
    g = make_game()
    actor = g.current_player()
    enemy = g.players[1]

    actor.faction_id = 'taiwan_green'
    actor.base = '東京'
    actor.organizations = {'東京': 1, '佬沃': 1}
    actor.hand = [g._make_support_card('臺灣奧援')]

    enemy.faction_id = 'red_army'
    enemy.base = '北京'
    enemy.organizations = {'大阪': 1}

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert result.get('tier') == 2
    assert result.get('effect_type') == 'interactive_dissolve_many_near'
    assert g.pending_choice['type'] == 'support_flow_choice'
    assert g.pending_choice['step'] == 'target'
    assert g.pending_choice['context']['effect_type'] == 'interactive_dissolve_many_near'
    assert actor.organizations == {'東京': 1, '佬沃': 1}
    assert enemy.organizations == {'大阪': 1}

    resolved = g.resolve_pending_choice(actor.id, 0)

    assert resolved.get('success'), resolved
    assert enemy.organizations.get('大阪', 0) == 0
    assert actor.organizations == {'東京': 1, '佬沃': 1}



def test_lure_exhaustion_draws_then_prompts_target_choice_after_self_remove():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '誘導虛耗')]
    p2.hand = [Card('EnemyCard', 'command', {})]
    p1.deck.draw_pile = [Card('DrawnCard', 'command', {})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert result.get('pending_choice') is True
    assert names(p1.hand) == ['DrawnCard']
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'optional_trash'

    resolved = g.resolve_pending_choice(p1.id, 0)

    assert resolved.get('success'), resolved
    assert resolved.get('pending_choice') is True
    # optional_trash 第 0 項＝「移除剛打出的牌」：誘導虛耗被移出遊戲，不會留在棄牌堆。
    assert resolved.get('removed_current_card') is True
    assert names(p1.deck.discard_pile) == []
    assert g.pending_choice and g.pending_choice['type'] == 'target_choice'
    assert g.pending_choice['choice_key'] == 'bait_exhaustion_target'
    assert [entry['label'] for entry in g.pending_choice['targets']] == ['P2']

    state_choice = g.state()['pending_choice']
    assert state_choice['type'] == 'target_choice'
    assert state_choice['choice_key'] == 'bait_exhaustion_target'
    assert state_choice['source_name'] == '誘導虛耗'
    assert state_choice['step'] is None
    assert state_choice['options'] == []
    assert state_choice['towns'] == []
    assert state_choice['targets'] == [{'id': p2.id, 'label': 'P2'}]

    target_resolved = g.resolve_pending_choice(p1.id, 0)

    assert target_resolved.get('success'), target_resolved
    assert target_resolved.get('pending_choice') is True
    assert target_resolved.get('target_player_name') == 'P2'
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'bait_exhaustion_target_discard'
    assert g.pending_choice['player_id'] == p2.id
    assert names(g.pending_choice['cards']) == ['EnemyCard']

    target_state_choice = g.state()['pending_choice']
    assert target_state_choice['type'] == 'card_choice'
    assert target_state_choice['choice_key'] == 'bait_exhaustion_target_discard'
    assert target_state_choice['player_id'] == p2.id
    assert target_state_choice['cards'] == ['EnemyCard']
    assert target_state_choice['source_name'] == '誘導虛耗'

    discard_resolved = g.resolve_pending_choice(p2.id, 0)

    assert discard_resolved.get('success'), discard_resolved
    assert discard_resolved.get('discarded_card') == 'EnemyCard'
    assert discard_resolved.get('target_player_name') == 'P2'
    assert names(p2.hand) == []
    assert names(p2.deck.discard_pile) == ['EnemyCard']
    assert g.turn_log.get('successful_discard') is True


def test_lure_exhaustion_skips_optional_trash_when_no_other_player_has_cards():
    g = make_game()
    p1, p2 = g.players
    bait = card(g, '誘導虛耗')
    p1.hand = [bait]
    p1.deck.draw_pile = [Card('DrawnCard', 'command', {})]
    p2.hand = []

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert not result.get('pending_choice')
    assert g.pending_choice is None
    assert names(p1.hand) == ['DrawnCard']
    assert names(p1.deck.discard_pile) == ['誘導虛耗']
    assert p2.hand == []
    assert p2.deck.discard_pile == []
    assert any('optional trash was skipped' in line for line in g.action_log)


def test_imitate_tactics_uses_target_player_top_card_not_own_top_card():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '模仿戰術')]
    p1.deck.draw_pile = [Card('OwnTop', 'command', {})]
    p2.deck.draw_pile = [Card('TargetBottom', 'command', {}), Card('OpponentTop', 'command', {'money': 1})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert 'OpponentTop' in names(p1.hand)
    assert 'OwnTop' not in names(p1.hand)
    assert names(p2.deck.draw_pile) == ['TargetBottom']

    idx = names(p1.hand).index('OpponentTop')
    result = g.play_card(idx, mode='resource')
    assert result.get('success'), result
    assert names(p2.deck.draw_pile)[-1] == 'OpponentTop'
    assert 'OpponentTop' not in names(p1.deck.discard_pile)


def test_imitate_tactics_borrowed_card_returns_to_owner_topdeck_after_action_play():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '模仿戰術')]
    p2.deck.draw_pile = [Card('TargetBottom', 'command', {}), Card('點燃熱情', 'command', {'propaganda': 1})]
    p1.deck.draw_pile = [Card('Bottom', 'command', {}), Card('FirstDraw', 'command', {}), Card('SecondDraw', 'command', {})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    borrowed_index = names(p1.hand).index('點燃熱情')
    action_result = g.play_card(borrowed_index, mode='action')
    assert action_result.get('success'), action_result
    assert names(p2.deck.draw_pile)[-1] == '點燃熱情'
    assert '點燃熱情' not in names(p1.deck.discard_pile)
    # 模仿戰術購買費用含宣傳（宣傳3），構成點燃熱情「本回合曾打出其它購買費用有宣傳的牌」
    # 條件（2026-07 費用組成修正），借來的點燃熱情因此抽 2 張而非 1 張。
    assert names(p1.hand) == ['SecondDraw', 'FirstDraw']



def test_business_network_borrowed_transport_card_grants_its_action_effect_after_choice_resolution():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '企業人脈')]
    g.purchase_area = [
        card(g, '宣傳家'),
        card(g, '思想家'),
        card(g, '資助者'),
        card(g, '資本家'),
        card(g, '分神'),
        card(g, '內鬥'),
        card(g, '合作談判'),
        card(g, '交通經驗乙'),
        card(g, '模仿戰術'),
    ]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'use_purchase_area_card'
    # 2026-07-10（19fc9bd）起企業人脈可借整個購買區（含常設 6 張），選單不再只列隨機區。
    assert [entry['name'] for entry in g.pending_choice['cards']] == [
        '宣傳家', '思想家', '資助者', '資本家', '分神', '內鬥', '合作談判', '交通經驗乙', '模仿戰術',
    ]

    resolved = g.resolve_pending_choice(p.id, 7)
    assert resolved.get('success'), resolved
    assert resolved.get('chosen_card') == '交通經驗乙'
    assert resolved.get('purchase_index') == 7
    assert p.moves_left == 4
    assert '交通經驗乙' not in names(p.hand)
    assert '交通經驗乙' not in names(p.deck.discard_pile)
    assert names(g.purchase_area)[7] == '交通經驗乙'



def test_red_support_resource_mode_from_rebel_hand_returns_card_to_red_army_discard():
    # 資源模式對奧援卡是無效果棄置（2026-06-07 裁決）；紅軍奧援是紅軍專屬卡，非紅軍
    # 玩家以資源模式用掉時，牌應回到紅軍玩家的棄牌堆（2026-07-12 P1 修正），不給任何資源。
    g = make_game()
    red = g.current_player()
    rebel = g.players[1]
    rebel.faction_id = 'hong_kong'
    g.current_player_index = 1
    rebel.hand = [g._make_support_card('紅軍奧援')]
    rebel.resources = {'money': 0, 'propaganda': 0}
    red.deck.discard_pile = []
    rebel.deck.discard_pile = []

    result = g.play_card(0, mode='resource')

    assert result.get('success'), result
    assert g.pending_choice is None
    assert rebel.resources == {'money': 0, 'propaganda': 0}
    assert names(rebel.deck.discard_pile) == []
    assert names(red.deck.discard_pile) == ['紅軍奧援']



def test_red_support_action_draws_and_moves_to_red_army_discard_when_rebel_plays_it():
    g = make_game()
    p1, p2 = g.players
    p1.faction_id = 'liberals'
    p2.faction_id = 'red_army'
    p1.hand = []
    p2.hand = []
    g.current_player_index = 0
    support = g._make_support_card('紅軍奧援')
    p1.deck.draw_pile = []
    p1.deck.discard_pile = [Card('DrawnCard', 'command', {})]
    p2.deck.discard_pile = []

    resolution = g._execute_support_card(p1, support)

    assert names(p1.hand) == ['DrawnCard']
    assert names(p1.deck.discard_pile) == []
    assert names(p2.deck.discard_pile) == ['紅軍奧援']
    assert resolution['effect_type'] == 'red_support_draw_and_pass'
    assert resolution['moved_to_player_id'] == p2.id



def test_red_support_action_draws_and_moves_to_rebel_discard_when_red_army_plays_it():
    g = make_game()
    p1, p2 = g.players
    p1.faction_id = 'red_army'
    p2.faction_id = 'liberals'
    p1.hand = []
    p2.hand = []
    g.current_player_index = 0
    support = g._make_support_card('紅軍奧援')
    p1.deck.draw_pile = []
    p1.deck.discard_pile = [Card('DrawnCard', 'command', {})]
    p2.deck.discard_pile = []

    resolution = g._execute_support_card(p1, support)

    assert names(p1.hand) == ['DrawnCard']
    assert names(p1.deck.discard_pile) == []
    assert names(p2.deck.discard_pile) == []
    assert resolution['effect_type'] == 'red_support_draw_and_pass'
    assert resolution['effect_text'] is None
    assert resolution['pending_choice'] is True
    assert g.pending_choice and g.pending_choice['choice_key'] == 'red_support_target_player'

    resolved = g.resolve_pending_choice(p1.id, 0)

    assert resolved.get('success'), resolved
    assert names(p1.hand) == ['DrawnCard']
    assert names(p2.deck.discard_pile) == ['紅軍奧援']
    assert resolved['moved_to_player_id'] == p2.id



def test_intel_network_state_serializes_three_options_for_ui():
    g = Game([('p1', 'P1'), ('p2', 'P2'), ('p3', 'P3'), ('p4', 'P4')])
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.pending_base_choices = {}
    pin_noop_event(g)
    g.players[0].faction_id = 'red_army'
    p1, p2, p3, p4 = g.players
    p1.hand = [card(g, '情報網')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'天津': 1}
    p2.deck.discard_pile = [Card('棄牌A', 'command', {})]
    p3.deck.discard_pile = [Card('棄牌B', 'command', {})]
    p4.deck.discard_pile = [Card('棄牌C', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    state_choice = g.state()['pending_choice']
    assert state_choice['type'] == 'option_choice'
    assert state_choice['choice_key'] == 'choose_one'
    assert state_choice['source_name'] == '情報網'
    # 「取消對方行動卡」選項只在反應時機有意義，2026-07（5f50a20）已從自己回合的
    # choose_one 移除（該用法走獨立的 reaction 流程）；自回合選單只剩兩項。
    assert [opt['label'] for opt in state_choice['options']] == [
        '在至多3位玩家棄牌堆各放入1張內鬥',
        '瓦解己方組織1格內的1個對手組織',
    ]



def test_intel_network_first_branch_adds_internal_conflict_without_running_other_branches():
    g = Game([('p1', 'P1'), ('p2', 'P2'), ('p3', 'P3'), ('p4', 'P4')])
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.pending_base_choices = {}
    pin_noop_event(g)
    g.players[0].faction_id = 'red_army'
    p1, p2, p3, p4 = g.players
    p1.hand = [card(g, '情報網')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'天津': 1}
    p2.deck.discard_pile = [Card('棄牌A', 'command', {})]
    p3.deck.discard_pile = [Card('棄牌B', 'command', {})]
    p4.deck.discard_pile = [Card('棄牌C', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    resolved = g.resolve_pending_choice(p1.id, 0)
    assert resolved.get('success'), resolved
    assert names(p1.deck.discard_pile) == ['情報網']
    assert names(p2.deck.discard_pile) == ['棄牌A', '內鬥']
    assert names(p3.deck.discard_pile) == ['棄牌B', '內鬥']
    assert names(p4.deck.discard_pile) == ['棄牌C', '內鬥']
    state_players = {player['name']: player for player in g.state()['players']}
    assert state_players['P2']['discard_pile'] == ['棄牌A', '內鬥']
    assert state_players['P3']['discard_pile'] == ['棄牌B', '內鬥']
    assert state_players['P4']['discard_pile'] == ['棄牌C', '內鬥']
    assert p2.organizations.get('天津', 0) == 1


def test_intel_network_can_choose_dissolve_branch_instead_of_default_internal_conflict():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '情報網')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'天津': 1}

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'option_choice'
    assert g.pending_choice['choice_key'] == 'choose_one'
    resolved = g.resolve_pending_choice(p1.id, 1)
    assert resolved.get('success'), resolved
    assert resolved.get('pending_choice') is True
    assert g.pending_choice and g.pending_choice['choice_key'] == 'intel_network_dissolve_target'
    assert [entry['label'] for entry in g.pending_choice['targets']] == ['P2｜天津']
    target_resolved = g.resolve_pending_choice(p1.id, 0)
    assert target_resolved.get('success'), target_resolved
    assert p2.organizations.get('天津', 0) == 0
    assert names(p2.deck.discard_pile).count('內鬥') == 0



def test_intel_network_own_turn_choice_has_no_cancel_branch():
    # 舊第 3 選項「取消對方行動卡」在自己回合本來就永遠無效（context 沒有可取消的牌），
    # 2026-07（5f50a20）已移除；這裡鎖住「index 2 不再是合法選項」，取消用法由
    # reaction 流程覆蓋（見 test_intel_network_reaction_cancels_other_player_action...）。
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '情報網')]
    p2.hand = [Card('EnemyCard', 'command', {})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'option_choice'
    assert len(g.pending_choice['options']) == 2
    rejected = g.resolve_pending_choice(p1.id, 2)
    assert rejected.get('error') == 'Invalid choice index'
    assert names(p2.deck.discard_pile).count('內鬥') == 0



def test_intel_network_reaction_cancels_other_player_action_without_bonus_draw():
    g = make_game()
    actor, reactor = g.players
    actor.hand = [card(g, '領導')]
    actor.deck.draw_pile = [Card('ShouldNotDraw', 'command', {})]
    reactor.hand = [card(g, '情報網')]
    reactor.deck.draw_pile = [Card('IntelShouldNotDrawBonus', 'command', {})]
    reactor.deck.discard_pile = []

    result = g.play_card(0, mode='action', reaction={'player_id': reactor.id, 'card_index': 0})

    assert result.get('success'), result
    assert names(actor.hand) == []
    assert names(actor.deck.discard_pile) == ['領導']
    assert names(reactor.hand) == []
    assert names(reactor.deck.discard_pile)[-1] == '情報網'
    assert names(reactor.hand) == []
    assert g.turn_log.get('canceled_card') is True
    assert g.turn_log.get('canceled_propaganda_card') is None
    assert g.turn_log.get('canceled_money_cost_card') is None



def test_intel_network_reaction_does_not_trigger_on_resource_play():
    g = make_game()
    actor, reactor = g.players
    actor.hand = [card(g, '領導')]
    actor.resources = {'money': 0, 'propaganda': 0}
    reactor.hand = [card(g, '情報網')]

    result = g.play_card(0, mode='resource', reaction={'player_id': reactor.id, 'card_index': 0})

    assert result.get('success'), result
    assert actor.resources == {'money': 0, 'propaganda': 1}
    assert names(reactor.hand) == ['情報網']
    assert names(reactor.deck.discard_pile) == []
    assert g.turn_log.get('canceled_card') is None


def test_every_other_player_action_prompts_cancel_reaction_while_reactor_holds_eligible_cards():
    """2026-08-02 使用者更正：`情報網`／`爆料黑幕`／`產業滲透` 這三張牌只要還在手上，
    對手「每一次」符合取消條件的行動都要跳出取消詢問——不是這回合問過這個人一次、
    之後同一回合就不再問了。舊版此測試（`test_first_other_player_action_prompts_
    cancel_reaction_once_with_all_available_cards`）斷言「第二張牌不再跳出詢問」，
    那其實是把一次性的 per-turn 節流當成正確行為，是誤解卡面規則後刻意做出來的
    （2026-05-17 commit 2aa6b0d "prompt cancel reactions on first action"）。這裡改為
    斷言：reactor 選擇不取消第一張牌後，第二張牌一樣會再跳出詢問，而且這次選擇取消
    也能正常生效。"""
    g = make_game()
    actor, reactor = g.players
    actor.hand = [card(g, '點燃熱情')]
    actor.deck.draw_pile = [Card('ShouldNotDrawYet', 'command', {})]
    reactor.hand = [card(g, '情報網'), card(g, '爆料黑幕'), card(g, '產業滲透')]

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert g.pending_choice and g.pending_choice['type'] == 'reaction_choice'
    assert g.pending_choice['choice_key'] == 'cancel_other_player_action'
    assert g.pending_choice['player_id'] == reactor.id
    assert g.pending_choice['acting_player_id'] == actor.id
    assert g.pending_choice['played_card_name'] == '點燃熱情'
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['情報網', '爆料黑幕', '產業滲透']
    assert names(actor.hand) == []
    assert names(actor.deck.discard_pile) == []
    assert names(actor.deck.draw_pile) == ['ShouldNotDrawYet']

    state_choice = g.state()['pending_choice']
    assert state_choice['type'] == 'reaction_choice'
    assert [entry['name'] for entry in state_choice['cards']] == ['情報網', '爆料黑幕', '產業滲透']
    assert state_choice['prompt'] == 'P1 打出 點燃熱情。是否要取消對方的行動？'

    skipped = g.resolve_pending_choice(reactor.id, 0)
    assert skipped.get('success'), skipped
    assert skipped.get('skipped_reaction') is True
    assert names(actor.hand) == ['ShouldNotDrawYet']
    assert names(actor.deck.discard_pile) == ['點燃熱情']
    assert names(reactor.hand) == ['情報網', '爆料黑幕', '產業滲透']

    actor.hand = [card(g, '領導')]
    actor.deck.draw_pile = [Card('ShouldNotDrawEitherSincePendingCancel', 'command', {})]
    second = g.play_card(0, mode='action')

    assert second.get('pending_choice') is True, second
    assert g.pending_choice and g.pending_choice['type'] == 'reaction_choice'
    assert g.pending_choice['played_card_name'] == '領導'
    # 領導的購買費用是宣傳1、資金0，`產業滲透` 的取消條件要求被取消的牌有資金費用，
    # 因此這裡正確地不包含 產業滲透——候選名單仍是逐次出牌各自重算，不是沿用第一次的名單。
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['情報網', '爆料黑幕']

    canceled = g.resolve_pending_choice(reactor.id, 2)  # index 2 -> 爆料黑幕
    assert canceled.get('success'), canceled
    assert canceled.get('reaction_card') == '爆料黑幕'
    assert canceled.get('canceled_card') == '領導'
    assert g.pending_choice is None
    assert names(actor.hand) == []
    assert names(actor.deck.draw_pile) == ['ShouldNotDrawEitherSincePendingCancel']
    assert names(actor.deck.discard_pile) == ['點燃熱情', '領導']
    assert '爆料黑幕' not in names(reactor.hand)


def test_reaction_candidate_who_declines_lets_the_next_eligible_reactor_react_to_the_same_card():
    """三人局：actor 打出一張牌時，若有兩位對手都持有可取消的反應卡，第一位選擇不取消
    後，應該接著問第二位（而不是第一位一謝絕，這張牌就直接結算掉，讓第二位永遠沒機會
    對這一次出牌反應）。"""
    g = Game([('p1', 'P1'), ('p2', 'P2'), ('p3', 'P3')])
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.pending_base_choices = {}
    pin_noop_event(g)
    g.players[0].faction_id = 'red_army'
    actor, first_reactor, second_reactor = g.players
    actor.hand = [card(g, '點燃熱情')]
    first_reactor.hand = [card(g, '產業滲透')]
    second_reactor.hand = [card(g, '爆料黑幕')]

    result = g.play_card(0, mode='action')
    assert result.get('pending_choice') is True, result
    assert g.pending_choice['player_id'] == first_reactor.id
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['產業滲透']

    skipped = g.resolve_pending_choice(first_reactor.id, 0)
    assert skipped.get('success'), skipped
    assert skipped.get('skipped_reaction') is True
    assert g.pending_choice is not None, 'second eligible reactor must still get a turn'
    assert g.pending_choice['type'] == 'reaction_choice'
    assert g.pending_choice['player_id'] == second_reactor.id
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['爆料黑幕']

    canceled = g.resolve_pending_choice(second_reactor.id, 1)
    assert canceled.get('success'), canceled
    assert canceled.get('reaction_card') == '爆料黑幕'
    assert canceled.get('canceled_card') == '點燃熱情'
    assert g.pending_choice is None
    assert '爆料黑幕' not in names(second_reactor.hand)


def test_cancel_reaction_prompt_can_select_one_reaction_card_to_cancel_action():
    g = make_game()
    actor, reactor = g.players
    actor.hand = [card(g, '領導')]
    actor.deck.draw_pile = [Card('ShouldNotDraw', 'command', {})]
    reactor.hand = [card(g, '情報網'), card(g, '爆料黑幕')]
    reactor.deck.discard_pile = []

    prompted = g.play_card(0, mode='action')
    assert prompted.get('pending_choice') is True, prompted

    resolved = g.resolve_pending_choice(reactor.id, 1)

    assert resolved.get('success'), resolved
    assert resolved.get('canceled_card') == '領導'
    assert resolved.get('reaction_card') == '情報網'
    assert g.pending_choice is None
    assert names(actor.hand) == []
    assert names(actor.deck.draw_pile) == ['ShouldNotDraw']
    assert names(actor.deck.discard_pile) == ['領導']
    assert names(reactor.hand) == ['爆料黑幕']
    assert names(reactor.deck.discard_pile)[-1] == '情報網'
    assert g.turn_log.get('canceled_card') is True


def test_dissolve_without_explicit_target_does_not_fall_back_to_all_opponents():
    g = make_game()
    actor, target = g.players
    actor.organizations = {'北京': 1}
    target.organizations = {'天津': 1}
    before_actor_orgs = dict(actor.organizations)
    before_target_orgs = dict(target.organizations)

    result = EffectEngine().execute(
        {'type': 'dissolve', 'range': 1},
        actor,
        g,
        context={'card_name': '無目標瓦解探針'},
    )

    assert result == {'no_target': True}
    assert actor.organizations == before_actor_orgs
    assert target.organizations == before_target_orgs
    assert any('無目標瓦解探針 had no explicit dissolve target' in line for line in g.action_log)


def test_force_discard_without_explicit_target_does_not_fall_back_to_all_opponents():
    g = make_game()
    actor, target = g.players
    target.hand = [Card('不得被靜默棄掉', 'command', {})]
    before_hand = list(target.hand)
    before_discard = list(target.deck.discard_pile)

    result = EffectEngine().execute(
        {'type': 'force_discard', 'count': 1},
        actor,
        g,
        context={'card_name': '無目標效果探針'},
    )

    assert result == {'no_target': True}
    assert target.hand == before_hand
    assert target.deck.discard_pile == before_discard
    assert any('無目標效果探針 had no explicit discard target' in line for line in g.action_log)


def test_all_interactive_support_effects_stop_cleanly_when_no_legal_target():
    cases = [
        ('interactive_build_anywhere_inner', {'count': 1}),
        ('interactive_build_near_inner', {'count': 1}),
        ('interactive_dissolve_many_near', {'count': 2}),
        ('interactive_dissolve_self_and_enemy', {'count': 1}),
        ('interactive_dissolve_and_build', {'count': 1}),
        ('force_discard_near', {'count': 1, 'random': False}),
    ]
    for effect_type, payload in cases:
        g = make_game()
        actor, target = g.players
        actor.organizations = {'北京': 1}
        target.organizations = {'臺北': 1}
        target.hand = [Card('不得被移動', 'command', {})]
        target.deck.discard_pile = [Card('既有棄牌', 'command', {})]
        before_actor_orgs = dict(actor.organizations)
        before_target_orgs = dict(target.organizations)
        before_hand = list(target.hand)
        before_discard = list(target.deck.discard_pile)
        g._support_card_tier = lambda player, card: (1, 0, [])
        g._resolve_support_card_effect = lambda card_name, tier, region_index, et=effect_type, ep=payload: (et, dict(ep))
        g._start_support_interaction = lambda *args, **kwargs: None

        result = g._execute_support_card(actor, Card('互動效果探針', 'support', {}))

        assert result.get('no_legal_target') is True, (effect_type, result)
        assert g.pending_choice is None
        assert actor.organizations == before_actor_orgs
        assert target.organizations == before_target_orgs
        assert target.hand == before_hand
        assert target.deck.discard_pile == before_discard


def test_support_resolver_rejects_stale_out_of_range_targets_before_mutation():
    g = make_game()
    actor, target = g.players
    actor.faction_id = 'red_army'
    target.faction_id = 'taiwan_green'
    actor.organizations = {'臺北': 1}
    target.organizations = {'天津': 1}
    target_card = Card('不得被棄掉', 'command', {})
    target.hand = [target_card]

    build_result = g._resolve_support_interaction_result(
        actor,
        {'town': '天津'},
        {
            'choice_key': 'support_interaction',
            'context': {'card_name': '東洋奧援', 'effect_type': 'interactive_build_near_inner'},
        },
    )
    assert build_result.get('error') == 'Invalid build town'
    assert actor.organizations == {'臺北': 1}

    for effect_type, card_name in (
        ('interactive_dissolve_many_near', '北國奧援'),
        ('force_discard_near', '天方奧援'),
    ):
        result = g._resolve_support_interaction_result(
            actor,
            {'selected': {'player_id': target.id, 'town': '天津'}},
            {
                'choice_key': 'support_interaction',
                'context': {
                    'card_name': card_name,
                    'effect_type': effect_type,
                    'effect_payload': {'count': 1, 'random': True},
                },
            },
        )
        assert result.get('error'), (effect_type, result)
        assert target.organizations == {'天津': 1}
        assert target.hand == [target_card]
        assert target.deck.discard_pile == []


def test_taiwan_support_tier3_with_no_build_supply_does_not_partially_dissolve():
    g = make_game()
    actor, target = g.players
    actor.faction_id = 'taiwan_green'
    target.faction_id = 'red_army'
    actor.organizations = {'臺北': 1, '供應占用': 21}
    target.organizations = {'基隆': 1}
    support_card = g._make_support_card('臺灣奧援')
    actor.hand = [support_card]
    setattr(g, '_support_card_tier', lambda player, card: (3, 0, []))

    result = g.play_card(0, mode='action')

    assert result.get('error') == 'No legal target for interactive support card', result
    assert actor.hand == [support_card]
    assert actor.deck.discard_pile == []
    assert actor.organizations == {'臺北': 1, '供應占用': 21}
    assert target.organizations == {'基隆': 1}
    assert g.pending_choice is None


def test_play_card_rolls_back_interactive_support_when_no_legal_target():
    cases = [
        'interactive_build_anywhere_inner',
        'interactive_build_near_inner',
        'interactive_dissolve_many_near',
        'interactive_dissolve_self_and_enemy',
        'interactive_dissolve_and_build',
        'force_discard_near',
    ]
    for effect_type in cases:
        g = make_game()
        actor, target = g.players
        before_card = Card('前一張', 'command', {})
        support_card = Card('互動奧援探針', 'support', {})
        after_card = Card('後一張', 'command', {})
        actor.hand = [before_card, support_card, after_card]
        target.hand = [Card('不得被移動', 'command', {})]
        target.deck.discard_pile = [Card('既有棄牌', 'command', {})]
        g.turn_log['played_money_card'] = True
        g.turn_log['played_propaganda_card'] = False
        before_target_hand = list(target.hand)
        before_target_discard = list(target.deck.discard_pile)
        g._support_card_tier = lambda player, card: (1, 0, [])
        setattr(g, '_resolve_support_card_effect', lambda card_name, tier, region_index, et=effect_type: (et, {'count': 1}))
        g._start_support_interaction = lambda *args, **kwargs: None

        result = g.play_card(1, mode='action')

        assert result.get('error') == 'No legal target for interactive support card', (effect_type, result)
        assert result.get('no_legal_target') is True
        assert actor.hand == [before_card, support_card, after_card]
        assert actor.deck.discard_pile == []
        assert target.hand == before_target_hand
        assert target.deck.discard_pile == before_target_discard
        assert g.turn_log['played_money_card'] is True
        assert g.turn_log['played_propaganda_card'] is False
        assert g.pending_choice is None


def test_tianfang_support_with_no_in_range_target_does_not_silently_discard():
    g = make_game()
    actor, target = g.players
    support_card = g._make_support_card('天方奧援')
    actor.hand = [support_card]
    actor.organizations = {'北京': 1}
    target.organizations = {'臺北': 1}
    first_donor = Card('樂捐者', 'resource', {'money': 1})
    second_donor = Card('樂捐者', 'resource', {'money': 1})
    target.hand = [first_donor, Card('其他手牌', 'command', {})]
    target.deck.draw_pile = [Card(f'牌庫{i}', 'command', {}) for i in range(8)]
    target.deck.discard_pile = [second_donor]

    result = g.play_card(0, mode='action')

    assert result.get('error') == 'No legal target for interactive support card', result
    assert result.get('no_legal_target') is True
    assert actor.hand == [support_card]
    assert actor.deck.discard_pile == []
    assert not result.get('pending_choice')
    assert names(target.hand) == ['樂捐者', '其他手牌']
    assert len(target.deck.draw_pile) == 8
    assert names(target.deck.discard_pile) == ['樂捐者']
    assert any('天方奧援 had no legal target; no interactive effect was applied' in line for line in g.action_log)


def test_tianfang_support_tier1_prompts_actor_target_choice_then_target_discard_choice():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [g._make_support_card('天方奧援')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'天津': 1}
    p2.hand = [Card('EnemyCardA', 'command', {}), Card('EnemyCardB', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert result.get('pending_choice') is True
    assert g.pending_choice and g.pending_choice['type'] == 'support_flow_choice'
    assert g.pending_choice['step'] == 'target'
    assert g.pending_choice['context']['effect_type'] == 'force_discard_near'
    assert g.pending_choice['context']['effect_payload'] == {'count': 1, 'random': False}
    assert [entry['label'] for entry in g.pending_choice['targets']] == ['P2']

    state_choice = g.state()['pending_choice']
    assert state_choice['type'] == 'support_flow_choice'
    assert state_choice['targets'] == [{'id': p2.id, 'label': 'P2', 'player_id': p2.id}]
    assert state_choice['source_name'] == '天方奧援'

    target_resolved = g.resolve_pending_choice(p1.id, 0)

    assert target_resolved.get('success'), target_resolved
    assert target_resolved.get('pending_choice') is True
    assert target_resolved.get('target_player_id') == p2.id
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'tianfang_support_target_discard'
    assert g.pending_choice['player_id'] == p2.id
    assert names(g.pending_choice['cards']) == ['EnemyCardA', 'EnemyCardB']

    target_state_choice = g.state()['pending_choice']
    assert target_state_choice['type'] == 'card_choice'
    assert target_state_choice['choice_key'] == 'tianfang_support_target_discard'
    assert target_state_choice['player_id'] == p2.id
    assert target_state_choice['cards'] == ['EnemyCardA', 'EnemyCardB']
    assert target_state_choice['source_name'] == '天方奧援'

    discard_resolved = g.resolve_pending_choice(p2.id, 1)

    assert discard_resolved.get('success'), discard_resolved
    assert discard_resolved.get('discarded_card') == 'EnemyCardB'
    assert discard_resolved.get('target_player_name') == 'P2'
    assert names(p2.hand) == ['EnemyCardA']
    assert names(p2.deck.discard_pile) == ['EnemyCardB']



def test_tianfang_support_tier3_discards_two_random_cards_from_chosen_target_in_range():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [g._make_support_card('天方奧援')]
    p1.faction_id = 'india'
    p1.organizations = {'喀布爾': 1, '拉瓦爾品第': 1}
    p2.organizations = {'杜尚貝': 1}
    p2.hand = [Card('EnemyCardA', 'command', {}), Card('EnemyCardB', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert result.get('pending_choice') is True
    assert result.get('tier') == 3
    assert g.pending_choice and g.pending_choice['context']['effect_payload'] == {'count': 2, 'random': True}

    resolved = g.resolve_pending_choice(p1.id, 0)

    assert resolved.get('success'), resolved
    assert resolved.get('target_player_id') == p2.id
    assert sorted(resolved.get('discarded_cards')) == ['EnemyCardA', 'EnemyCardB']
    assert names(p2.hand) == []
    assert sorted(names(p2.deck.discard_pile)) == ['EnemyCardA', 'EnemyCardB']



def test_divide_adds_internal_conflict_to_other_players_not_self():
    # 卡面「在至多3位玩家棄牌堆各放入1張內鬥」＝每位其他玩家各 1 張、最多 3 位；
    # 舊斷言「單一目標塞 3 張」不符卡面文字（2026-07-10 7bc0d6b 修正後為現行為）。
    g = Game([('p1', 'P1'), ('p2', 'P2'), ('p3', 'P3'), ('p4', 'P4')])
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.pending_base_choices = {}
    pin_noop_event(g)
    p1, p2, p3, p4 = g.players
    p1.faction_id = 'red_army'
    p1.hand = [card(g, '離間')]
    for player in g.players:
        player.deck.discard_pile = []

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert names(p1.deck.discard_pile).count('內鬥') == 0
    assert names(p2.deck.discard_pile).count('內鬥') == 1
    assert names(p3.deck.discard_pile).count('內鬥') == 1
    assert names(p4.deck.discard_pile).count('內鬥') == 1


def test_announce_action_topdecks_latest_card_bought_this_turn_and_gains_propaganda():
    g = make_game()
    p = g.current_player()
    bought = Card('PurchasedCard', 'command', {})
    p.deck.discard_pile = [bought]
    g.turn_log['purchased_cards_this_turn'] = [bought]

    p = play_only(g, '行動預告')

    assert p.resources['propaganda'] == 1
    assert names(p.deck.draw_pile)[-1] == 'PurchasedCard'
    assert 'PurchasedCard' not in names(p.deck.discard_pile)


def test_action_fundraising_topdecks_latest_card_bought_this_turn_and_gains_money():
    g = make_game()
    p = g.current_player()
    bought = Card('PurchasedCard', 'command', {})
    p.deck.discard_pile = [bought]
    g.turn_log['purchased_cards_this_turn'] = [bought]

    p = play_only(g, '行動募資')

    assert p.resources['money'] == 1
    assert names(p.deck.draw_pile)[-1] == 'PurchasedCard'
    assert 'PurchasedCard' not in names(p.deck.discard_pile)



def test_end_turn_prompts_action_announcement_and_draws_purchased_card_after_resolution():
    g = make_game()
    p = g.current_player()
    bought = Card('PurchasedCard', 'command', {})
    p.hand = [card(g, '行動預告'), Card('Filler', 'command', {})]
    p.deck.draw_pile = [Card('Bottom1', 'command', {}), Card('Bottom2', 'command', {}), Card('Bottom3', 'command', {}), Card('Bottom4', 'command', {}), Card('Bottom5', 'command', {})]
    p.deck.discard_pile = [bought]
    g.turn_log['purchased_cards_this_turn'] = [bought]
    g.turn_phase = TurnPhase.END

    result = g.advance_turn_phase()

    assert result.get('pending_choice') is True
    assert g.pending_choice and g.pending_choice['type'] == 'option_choice'
    assert g.pending_choice['choice_key'] == 'end_turn_topdeck_action'
    assert [option['label'] for option in g.pending_choice['options']] == ['不使用', '使用 行動預告']
    assert names(p.hand) == ['行動預告', 'Filler']

    resolved = g.resolve_pending_choice(p.id, 1)

    assert resolved.get('success'), resolved
    # 現行回合模型（action-first）：回合結束後直接輪到下一位玩家的 ACTION，沒有 EVENT 階段。
    assert g.turn_phase == TurnPhase.ACTION
    assert g.current_player().name == 'P2'
    assert 'PurchasedCard' in names(p.hand)
    assert 'PurchasedCard' not in names(p.deck.discard_pile)
    assert '行動預告' in names(p.deck.discard_pile)
    assert any('used 行動預告 before drawing new hand' in line for line in g.action_log)



def test_end_turn_can_skip_action_fundraising_prompt_and_purchased_card_stays_discarded():
    g = make_game()
    p = g.current_player()
    bought = Card('PurchasedCard', 'command', {})
    p.hand = [card(g, '行動募資')]
    p.deck.draw_pile = [Card('Draw1', 'command', {}), Card('Draw2', 'command', {}), Card('Draw3', 'command', {}), Card('Draw4', 'command', {}), Card('Draw5', 'command', {})]
    p.deck.discard_pile = [bought]
    g.turn_log['purchased_cards_this_turn'] = [bought]
    g.turn_phase = TurnPhase.END

    result = g.advance_turn_phase()

    assert result.get('pending_choice') is True
    assert [option['label'] for option in g.pending_choice['options']] == ['不使用', '使用 行動募資']
    resolved = g.resolve_pending_choice(p.id, 0)

    assert resolved.get('success'), resolved
    # 現行回合模型（action-first）：回合結束後直接輪到下一位玩家的 ACTION，沒有 EVENT 階段。
    assert g.turn_phase == TurnPhase.ACTION
    assert g.current_player().name == 'P2'
    assert 'PurchasedCard' not in names(p.hand)
    assert 'PurchasedCard' in names(p.deck.discard_pile)
    assert any('skipped end-turn action topdeck prompt' in line for line in g.action_log)



def test_negotiation_draws_actor_and_chosen_other_player_only_and_gains_two_propaganda():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '合作談判')]
    p1.deck.draw_pile = [Card('ActorDraw', 'command', {})]
    p2.deck.draw_pile = [Card('TargetDraw', 'command', {})]
    p2.hand = []
    p1.resources = {'money': 0, 'propaganda': 0}

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert names(p1.hand) == ['ActorDraw']
    assert names(p2.hand) == ['TargetDraw']
    assert p1.resources['propaganda'] == 2


def test_liberals_stance_probe_adds_odd_cost_top_card_to_hand():
    g = make_game()
    p = g.current_player()
    # 立場試探現屬自由派（liberals）；舊測試用的 'fujian' 陣營 id 已不存在。
    p.faction_id = 'liberals'
    p.hand = []
    p.deck.draw_pile = [Card('Bottom', 'command', {}), card(g, '點燃熱情')]

    result = g._activated_faction_action(p, '立場試探')

    assert result.get('success'), result
    assert names(p.hand) == ['點燃熱情']
    assert names(p.deck.discard_pile) == []
    assert g.turn_log.get('faction_action_used') is True



def test_liberals_stance_probe_discards_even_cost_top_card():
    g = make_game()
    p = g.current_player()
    # 立場試探現屬自由派（liberals）；舊測試用的 'fujian' 陣營 id 已不存在。
    p.faction_id = 'liberals'
    p.hand = []
    p.deck.draw_pile = [Card('Bottom', 'command', {}), Card('EvenTop', 'command', {'money': 2})]

    result = g._activated_faction_action(p, '立場試探')

    assert result.get('success'), result
    assert names(p.hand) == []
    assert names(p.deck.discard_pile) == ['EvenTop']
    assert g.turn_log.get('faction_action_used') is True



def test_liberals_stance_probe_treats_starter_donor_as_odd_cost_and_adds_it_to_hand():
    g = make_game()
    p = g.current_player()
    # 立場試探現屬自由派（liberals）；舊測試用的 'fujian' 陣營 id 已不存在。
    p.faction_id = 'liberals'
    p.hand = [Card('Existing', 'command', {})]
    p.deck.draw_pile = [Card('Bottom', 'command', {}), Card('樂捐者', 'money', {'money': 1})]
    p.deck.discard_pile = []

    result = g._activated_faction_action(p, '立場試探')

    assert result.get('success'), result
    assert names(p.hand) == ['Existing', '樂捐者']
    assert names(p.deck.discard_pile) == []
    assert g.action_log[-1] == '[Turn 1] P1 triggered 立場試探 and added 樂捐者 to hand'



def test_underground_party_keeps_one_card_and_returns_the_rest_to_purchase_deck_system():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '地下黨')]
    starting_purchase_count = len(g.purchase_deck.draw_pile) + len(g.purchase_deck.discard_pile)

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'underground_party'
    revealed = list(g.pending_choice['cards'])
    chosen_name = names(revealed)[0]
    resolved = g.resolve_pending_choice(p.id, 0)
    assert resolved.get('success'), resolved
    assert chosen_name in names(p.hand)
    ending_purchase_count = len(g.purchase_deck.draw_pile) + len(g.purchase_deck.discard_pile)
    assert ending_purchase_count == starting_purchase_count - 1


def test_field_agent_requires_target_org_within_one_step_of_sacrificed_org():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '派遣間諜')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'香港城': 1}

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('error') == 'No target organization within range'
    assert p1.organizations == {'北京': 1}
    assert p2.organizations == {'香港城': 1}



def test_spy_cards_with_no_legal_target_are_rejected_before_leaving_hand():
    for card_name in ('派遣間諜', '內應間諜'):
        g = make_game()
        actor, target = g.players
        target.faction_id = 'taiwan_green'
        spy_card = card(g, card_name)
        actor.hand = [Card('前一張', 'command', {}), spy_card, Card('後一張', 'command', {})]
        actor.organizations = {'北京': 1}
        target.organizations = {'臺北': 1}
        before_actor_orgs = dict(actor.organizations)
        before_target_orgs = dict(target.organizations)

        result = g.play_card(1, mode='action')

        assert result.get('error') == 'No target organization within range', (card_name, result)
        assert actor.hand[1] is spy_card
        assert names(actor.hand) == ['前一張', card_name, '後一張']
        assert actor.deck.discard_pile == []
        assert actor.organizations == before_actor_orgs
        assert target.organizations == before_target_orgs
        assert g.pending_choice is None


def test_field_agent_prompts_sacrifice_then_target_org_like_north_support():
    g = make_game()
    p1, p2 = g.players
    p2.faction_id = 'taiwan_green'
    p1.hand = [card(g, '派遣間諜')]
    p1.base = '北京'
    p1.organizations = {'北京': 1, '上海': 1}
    p2.organizations = {'天津': 1, '杭州': 1, '香港城': 1}

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert g.pending_choice and g.pending_choice['type'] == 'support_flow_choice'
    assert g.pending_choice['choice_key'] == 'card_dissolve_interaction'
    assert g.pending_choice['step'] == 'sacrifice_town'
    assert g.pending_choice['source_name'] == '派遣間諜'
    assert p1.base == '北京'
    assert g.pending_choice['towns'] == [
        {'town': '上海', 'label': '上海（可瓦解鄰近敵方組織）', 'target_count': 1},
    ]

    sacrificed = g.resolve_pending_choice(p1.id, 0)

    assert sacrificed.get('success'), sacrificed
    assert sacrificed.get('pending_choice') is True
    assert p1.organizations == {'北京': 1}
    assert g.pending_choice['step'] == 'target'
    assert g.pending_choice['targets'] == [{
        'id': f'{p2.id}::杭州',
        'label': 'P2｜杭州',
        'player_id': p2.id,
        'town': '杭州',
        'sacrifice_town': '上海',
    }]

    resolved = g.resolve_pending_choice(p1.id, 0)

    assert resolved.get('success'), resolved
    assert p1.organizations == {'北京': 1}
    assert p2.organizations.get('杭州', 0) == 0
    assert p2.organizations.get('天津', 0) == 1
    assert p2.organizations.get('香港城', 0) == 1
    assert g.pending_choice is None



def test_embedded_agent_requires_target_org_within_one_step_of_own_org():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '內應間諜')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'香港城': 1}

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('error') == 'No target organization within range'
    assert p1.organizations == {'北京': 1}
    assert p2.organizations == {'香港城': 1}



def test_embedded_agent_prompts_exact_in_range_target_org_without_self_sacrifice():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '內應間諜')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'天津': 1, '香港城': 1}

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert g.pending_choice and g.pending_choice['type'] == 'support_flow_choice'
    assert g.pending_choice['choice_key'] == 'card_dissolve_interaction'
    assert g.pending_choice['step'] == 'target'
    assert g.pending_choice['source_name'] == '內應間諜'
    assert g.pending_choice['targets'] == [{
        'id': f'{p2.id}::天津',
        'label': 'P2｜天津',
        'player_id': p2.id,
        'town': '天津',
        'requires_self_sacrifice': False,
    }]

    resolved = g.resolve_pending_choice(p1.id, 0)

    assert resolved.get('success'), resolved
    assert p1.organizations == {'北京': 1}
    assert p2.organizations.get('天津', 0) == 0
    assert p2.organizations.get('香港城', 0) == 1
    assert g.pending_choice is None



def test_armed_c_requires_target_player_with_org_within_one_step_of_self_org():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '武裝者')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'香港城': 1}
    p2.hand = [Card('Enemy1', 'command', {})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('error') == 'Target player has no organization within range'
    assert names(p2.hand) == ['Enemy1']
    assert names(p2.deck.discard_pile) == []



def test_armed_card_rejects_in_range_player_with_empty_hand_before_consuming_card():
    g = make_game()
    p1, p2 = g.players
    armed = card(g, '武裝者')
    p1.hand = [armed]
    p1.organizations = {'北京': 1}
    p2.organizations = {'天津': 1}
    p2.hand = []

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('error') == 'Target player has no hand cards', result
    assert p1.hand == [armed]
    assert p1.deck.discard_pile == []
    assert g.pending_choice is None


def test_armed_c_target_player_chooses_one_discard_when_in_range():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '武裝者')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'天津': 1}
    p2.hand = [Card('Enemy1', 'command', {}), Card('Enemy2', 'command', {})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert result.get('pending_choice') is True
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'armed_target_discard'
    assert g.pending_choice['player_id'] == p2.id
    assert names(g.pending_choice['cards']) == ['Enemy1', 'Enemy2']
    assert names(p2.hand) == ['Enemy1', 'Enemy2']
    resolved = g.resolve_pending_choice(p2.id, 0)
    assert resolved.get('success'), resolved
    assert names(p2.hand) == ['Enemy2']
    assert names(p2.deck.discard_pile)[-1] == 'Enemy1'
    assert any('P1 used 武裝者 to force P2 to discard Enemy1' in line for line in g.action_log)



def test_armed_b_requires_target_player_with_org_within_one_step_of_self_org():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '武裝小隊')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'香港城': 1}
    p2.hand = [Card('Enemy1', 'command', {}), Card('Enemy2', 'command', {})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('error') == 'Target player has no organization within range'
    assert names(p2.hand) == ['Enemy1', 'Enemy2']
    assert names(p2.deck.discard_pile) == []



def test_armed_b_target_player_chooses_two_discards_when_in_range():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '武裝小隊')]
    p1.organizations = {'北京': 1}
    p2.organizations = {'天津': 1}
    p2.hand = [Card('Enemy1', 'command', {}), Card('Enemy2', 'command', {}), Card('Enemy3', 'command', {})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert result.get('pending_choice') is True
    assert g.pending_choice and g.pending_choice['type'] == 'multi_card_choice'
    assert g.pending_choice['choice_key'] == 'armed_target_discard'
    assert g.pending_choice['player_id'] == p2.id
    assert g.pending_choice['count'] == 2
    assert names(g.pending_choice['cards']) == ['Enemy1', 'Enemy2', 'Enemy3']
    resolved = g.resolve_pending_choice(p2.id, [0, 2])
    assert resolved.get('success'), resolved
    assert names(p2.hand) == ['Enemy2']
    assert names(p2.deck.discard_pile) == ['Enemy1', 'Enemy3']
    assert any('P1 used 武裝小隊 to force P2 to discard 2 card(s)' in line for line in g.action_log)



def test_armed_group_target_player_chooses_two_discards_then_actor_draws():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '武裝集團')]
    p1.organizations = {'北京': 1}
    p1.deck.draw_pile = [Card('RewardDraw', 'command', {})]
    p2.organizations = {'天津': 1}
    p2.hand = [Card('Enemy1', 'command', {}), Card('Enemy2', 'command', {})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert result.get('pending_choice') is True
    assert g.pending_choice and g.pending_choice['type'] == 'multi_card_choice'
    assert g.pending_choice['choice_key'] == 'armed_target_discard'
    assert g.pending_choice['player_id'] == p2.id
    assert g.pending_choice['count'] == 2
    assert names(g.pending_choice['cards']) == ['Enemy1', 'Enemy2']
    assert 'RewardDraw' not in names(p1.hand)
    resolved = g.resolve_pending_choice(p2.id, [0, 1])
    assert resolved.get('success'), resolved
    assert names(p2.hand) == []
    assert names(p2.deck.discard_pile) == ['Enemy1', 'Enemy2']
    assert 'RewardDraw' in names(p1.hand)
    assert g.turn_log.get('successful_discard') is True
    assert any('P1 used 武裝集團 to force P2 to discard 2 card(s)' in line for line in g.action_log)


def test_shift_public_opinion_refreshes_random_market_instead_of_using_player_deck_cards():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '輿論丕變')]
    p.deck.draw_pile = [Card('PlayerDeckTop', 'command', {})]
    before_random_market = names(g.purchase_area[6:])

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    after_random_market = names(g.purchase_area[6:])
    assert len(after_random_market) == 5
    assert after_random_market != before_random_market
    assert 'PlayerDeckTop' not in after_random_market
    assert p.resources['propaganda'] == 1


def test_purge_cards_return_removed_cards_to_purchase_deck_system():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '批判'), Card('TrashTarget', 'command', {})]
    starting_purchase_count = len(g.purchase_deck.draw_pile) + len(g.purchase_deck.discard_pile)

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['choice_key'] == 'trash_from_hand_or_discard'
    resolved = g.resolve_pending_choice(p.id, 0)
    assert resolved.get('success'), resolved
    ending_purchase_count = len(g.purchase_deck.draw_pile) + len(g.purchase_deck.discard_pile)
    assert ending_purchase_count == starting_purchase_count + 1



def test_major_purge_returns_two_removed_cards_to_purchase_deck_system():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '批鬥'), Card('TrashTarget1', 'command', {}), Card('TrashTarget2', 'command', {})]
    starting_purchase_count = len(g.purchase_deck.draw_pile) + len(g.purchase_deck.discard_pile)

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['choice_key'] == 'trash_from_hand_or_discard'
    assert g.pending_choice['type'] == 'multi_card_choice'
    resolved = g.resolve_pending_choice(p.id, [0, 1])
    assert resolved.get('success'), resolved
    ending_purchase_count = len(g.purchase_deck.draw_pile) + len(g.purchase_deck.discard_pile)
    assert ending_purchase_count == starting_purchase_count + 2


def test_ignite_passion_draws_two_after_other_propaganda_cost_card_played():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '點燃熱情')]
    p.deck.draw_pile = [Card('Bottom', 'command', {}), Card('FirstDraw', 'command', {}), Card('SecondDraw', 'command', {})]
    g.turn_log['played_propaganda_card'] = True

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert names(p.hand) == ['SecondDraw', 'FirstDraw']



def test_build_confidence_draws_two_after_other_money_cost_card_played():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '樹立信心')]
    p.deck.draw_pile = [Card('Bottom', 'command', {}), Card('FirstDraw', 'command', {}), Card('SecondDraw', 'command', {})]
    g.turn_log['played_money_card'] = True

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert names(p.hand) == ['SecondDraw', 'FirstDraw']



def test_forge_consensus_grants_propaganda_when_both_discards_are_non_starters():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '凝聚共識'), Card('KeepMe', 'command', {})]
    p.deck.draw_pile = [Card('Bottom', 'command', {}), Card('UsefulA', 'command', {}), Card('UsefulB', 'command', {})]
    p.deck.discard_pile = [Card('ExistingDiscard', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert result.get('pending_choice') is True
    assert p.resources['propaganda'] == 0
    assert g.pending_choice and g.pending_choice['type'] == 'multi_card_choice'
    assert g.pending_choice['choice_key'] == 'discard_self'
    assert names(g.pending_choice['cards']) == ['KeepMe', 'UsefulB', 'UsefulA', 'Bottom']
    resolved = g.resolve_pending_choice(p.id, [1, 2])
    assert resolved.get('success'), resolved
    assert p.resources['propaganda'] == 2
    assert g.turn_log.get('non_starter_discard') is True
    assert 'KeepMe' in names(p.hand)
    assert 'Bottom' in names(p.hand)
    assert names(p.deck.discard_pile) == ['ExistingDiscard', '凝聚共識', 'UsefulB', 'UsefulA']


def test_forge_consensus_does_not_grant_propaganda_before_pending_choice_or_when_discards_are_starters():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '凝聚共識'), Card('KeepMe', 'command', {})]
    p.deck.draw_pile = [Card('Bottom', 'command', {}), Card('追隨者', 'starter', {}), Card('樂捐者', 'starter', {})]
    p.deck.discard_pile = [Card('ExistingDiscard', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert result.get('pending_choice') is True
    assert p.resources['propaganda'] == 0
    assert g.pending_choice and g.pending_choice['type'] == 'multi_card_choice'
    resolved = g.resolve_pending_choice(p.id, [1, 2])
    assert resolved.get('success'), resolved
    assert p.resources['propaganda'] == 0
    assert names(p.deck.discard_pile) == ['ExistingDiscard', '凝聚共識', '樂捐者', '追隨者']



def test_expand_gains_can_choose_any_card_from_own_discard():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '擴大戰果')]
    p.deck.discard_pile = [Card('WantedCard', 'command', {}), Card('TopCard', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'gain_any_from_discard'
    assert names(g.pending_choice['cards']) == ['WantedCard', 'TopCard']
    resolved = g.resolve_pending_choice(p.id, 0)
    assert resolved.get('success'), resolved
    assert 'WantedCard' in names(p.hand)
    assert 'TopCard' not in names(p.hand)



def test_business_network_borrows_from_whole_purchase_area_and_keeps_cards_in_place():
    # 2026-07-10（19fc9bd）規則盤點修正：卡面「將購買區面朝上的任1張牌」不限隨機區，
    # 企業人脈的選單涵蓋常設＋隨機整個購買區；牌只是暫借，購買區內容不動。
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '企業人脈')]
    area_names = names(g.purchase_area)

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['choice_key'] == 'use_purchase_area_card'
    assert [entry['name'] for entry in g.pending_choice['cards']] == area_names
    assert names(g.purchase_area) == area_names



def test_business_network_choice_auto_plays_borrowed_card_and_returns_it_to_slot():
    # 企業人脈選定後「視同打出該牌」（行動），沒有再選資源/行動的步驟；打完後牌回到
    # 購買區原槽位、不留在玩家棄牌堆。購買區釘成固定內容，避免隨機區剛好出現需要
    # 指定目標的武裝/間諜卡導致自動打出失敗的隨機性。
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '企業人脈')]
    g.purchase_area = [
        card(g, '宣傳家'),
        card(g, '思想家'),
        card(g, '資助者'),
        card(g, '資本家'),
        card(g, '分神'),
        card(g, '內鬥'),
        card(g, '領導'),
    ]
    p.deck.draw_pile = [Card('DrawA', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['choice_key'] == 'use_purchase_area_card'
    resolved = g.resolve_pending_choice(p.id, 6)
    assert resolved.get('success'), resolved
    assert resolved.get('chosen_card') == '領導'
    # 領導效果（抽1張）由借來的牌發動
    assert 'DrawA' in names(p.hand)
    assert '領導' not in names(p.deck.discard_pile)
    assert names(g.purchase_area)[6] == '領導'



def test_business_network_borrowed_card_returns_to_purchase_area_after_action_play():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '企業人脈')]
    g.purchase_area = [
        card(g, '宣傳家'),
        card(g, '思想家'),
        card(g, '資助者'),
        card(g, '資本家'),
        card(g, '分神'),
        card(g, '內鬥'),
        card(g, '行動預告'),
    ]
    random_name = names(g.purchase_area[6:])[0]
    p.deck.discard_pile = [Card('PurchasedCard', 'command', {})]
    g.turn_log['purchased_cards_this_turn'] = [p.deck.discard_pile[0]]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['choice_key'] == 'use_purchase_area_card'
    # 選單涵蓋整個購買區，手動排的 行動預告 位於 index 6。
    resolved = g.resolve_pending_choice(p.id, 6)
    assert resolved.get('success'), resolved
    assert resolved.get('chosen_card') == random_name
    assert random_name not in names(p.deck.discard_pile)
    assert names(g.purchase_area[6:])[0] == random_name



def test_industry_infiltration_can_cancel_target_action_card_and_draw_when_canceled_card_has_money_cost():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '擴大戰果')]
    p1.deck.discard_pile = [Card('DiscardTarget', 'command', {})]
    p2.hand = [card(g, '產業滲透')]
    p2.deck.draw_pile = [Card('ReactionDraw', 'command', {})]

    result = g.play_card(0, mode='action', reaction={'player_id': p2.id, 'card_index': 0})

    assert result.get('success'), result
    assert names(p1.hand) == []
    assert names(p1.deck.discard_pile)[-1] == '擴大戰果'
    assert 'DiscardTarget' in names(p1.deck.discard_pile)
    assert 'ReactionDraw' in names(p2.hand)
    assert names(p2.deck.discard_pile)[-1] == '產業滲透'
    assert g.turn_log.get('canceled_money_cost_card') is True



def test_industry_infiltration_does_not_draw_when_canceled_card_has_no_money_only_cost():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '凝聚共識')]
    p1.deck.draw_pile = [Card('Bottom', 'command', {}), Card('WouldHaveDrawn', 'command', {})]
    p2.hand = [card(g, '產業滲透')]
    p2.deck.draw_pile = [Card('ReactionDraw', 'command', {})]

    result = g.play_card(0, mode='action', reaction={'player_id': p2.id, 'card_index': 0})

    assert result.get('success'), result
    assert 'ReactionDraw' not in names(p2.hand)
    assert g.turn_log.get('canceled_money_cost_card') is None
    assert 'WouldHaveDrawn' in names(p1.hand)



def test_industry_infiltration_requires_an_actual_action_card_target_to_cancel():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [Card('樂捐者', 'money', {'money': 1})]
    p2.hand = [card(g, '產業滲透')]

    result = g.play_card(0, mode='resource', reaction={'player_id': p2.id, 'card_index': 0})

    assert result.get('success'), result
    assert names(p2.hand) == ['產業滲透']
    assert names(p2.deck.discard_pile) == []
    assert g.turn_log.get('canceled_money_cost_card') is None



def test_expose_scandal_requires_an_actual_action_card_target_to_cancel():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [Card('追隨者', 'propaganda', {'propaganda': 1})]
    p2.hand = [card(g, '爆料黑幕')]

    result = g.play_card(0, mode='resource', reaction={'player_id': p2.id, 'card_index': 0})

    assert result.get('success'), result
    assert names(p1.hand) == []
    assert names(p2.hand) == ['爆料黑幕']
    assert names(p2.deck.discard_pile) == []
    assert g.turn_log.get('canceled_propaganda_card') is None



def test_expose_scandal_cannot_cancel_another_expose_scandal_reaction():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '點燃熱情')]
    p1.deck.draw_pile = [Card('Bottom', 'command', {}), Card('WouldHaveDrawn', 'command', {})]
    p2.hand = [card(g, '爆料黑幕'), card(g, '爆料黑幕')]
    p2.deck.draw_pile = [Card('ReactionDraw', 'command', {})]

    result = g.play_card(
        0,
        mode='action',
        reaction={'player_id': p2.id, 'card_index': 0, 'reaction': {'player_id': p1.id, 'card_index': 0}},
    )

    assert result.get('success'), result
    assert names(p1.hand) == []
    assert names(p1.deck.discard_pile)[-1] == '點燃熱情'
    assert names(p2.hand) == ['爆料黑幕', 'ReactionDraw']
    assert names(p2.deck.discard_pile) == ['爆料黑幕']



def test_expose_scandal_reaction_must_be_from_another_player_holding_expose_scandal():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '點燃熱情')]
    p1.deck.draw_pile = [Card('Bottom', 'command', {}), Card('WouldHaveDrawn', 'command', {})]
    p2.hand = [card(g, '高效行動')]

    result = g.play_card(0, mode='action', reaction={'player_id': p2.id, 'card_index': 0})

    assert result.get('success'), result
    assert 'WouldHaveDrawn' in names(p1.hand)
    assert names(p2.hand) == ['高效行動']
    assert names(p2.deck.discard_pile) == []



def test_expose_scandal_can_cancel_target_action_card_and_prevent_its_effect():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '點燃熱情')]
    p1.deck.draw_pile = [Card('Bottom', 'command', {}), Card('WouldHaveDrawn', 'command', {})]
    starting_discard = len(p1.deck.discard_pile)
    p2.hand = [card(g, '爆料黑幕')]
    p2.deck.draw_pile = []

    result = g.play_card(0, mode='action', reaction={'player_id': p2.id, 'card_index': 0})

    assert result.get('success'), result
    assert names(p1.hand) == []
    assert len(p1.deck.discard_pile) == starting_discard + 1
    assert names(p1.deck.discard_pile)[-1] == '點燃熱情'
    assert names(p2.hand) == []
    assert names(p2.deck.discard_pile) == ['爆料黑幕']
    assert g.turn_log.get('canceled_propaganda_card') is True



def test_expose_scandal_only_draws_when_canceled_card_has_propaganda_cost():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '擴大戰果')]
    p1.deck.discard_pile = [Card('DiscardTarget', 'command', {})]
    p2.hand = [card(g, '爆料黑幕')]
    p2.deck.draw_pile = [Card('ReactionDraw', 'command', {})]

    result = g.play_card(0, mode='action', reaction={'player_id': p2.id, 'card_index': 0})

    assert result.get('success'), result
    assert 'ReactionDraw' not in names(p2.hand)
    assert g.turn_log.get('canceled_propaganda_card') is False



def test_expose_scandal_draws_when_canceled_card_has_propaganda_cost():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '點燃熱情')]
    p1.deck.draw_pile = [Card('Bottom', 'command', {}), Card('WouldHaveDrawn', 'command', {})]
    p2.hand = [card(g, '爆料黑幕')]
    p2.deck.draw_pile = [Card('ReactionDraw', 'command', {})]

    result = g.play_card(0, mode='action', reaction={'player_id': p2.id, 'card_index': 0})

    assert result.get('success'), result
    assert 'ReactionDraw' in names(p2.hand)
    assert g.turn_log.get('canceled_propaganda_card') is True



def test_efficient_action_can_choose_any_two_cards_to_discard():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '高效行動'), Card('KeepMe', 'command', {})]
    p.deck.draw_pile = [Card('Bottom', 'command', {}), Card('DrawA', 'command', {}), Card('DrawB', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'multi_card_choice'
    assert g.pending_choice['choice_key'] == 'discard_self'
    assert names(g.pending_choice['cards']) == ['KeepMe', 'DrawB', 'DrawA', 'Bottom']
    resolved = g.resolve_pending_choice(p.id, [1, 2])
    assert resolved.get('success'), resolved
    assert names(p.hand) == ['KeepMe', 'Bottom']
    assert names(p.deck.discard_pile)[-3:] == ['高效行動', 'DrawB', 'DrawA']



def test_thought_building_draws_one_and_extends_build_range_this_turn():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '思想建設')]
    p.deck.draw_pile = [Card('DrawnCard', 'command', {})]
    p.build_range_bonus = 0

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert names(p.hand) == ['DrawnCard']
    assert p.build_range_bonus == 1



def test_strategic_thinker_trashes_self_then_grants_build_and_three_moves():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '思想家')]
    p.organizations = {'北京': 1}
    p.moves_left = 0
    starting_supply = g.static_purchase_supply.get('思想家', 0)

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    built_town, resolved = resolve_first_build_town(g, p)
    assert resolved.get('success'), resolved
    assert p.organizations == {'北京': 1, built_town: 1}
    assert p.moves_left == 3
    assert '思想家' not in names(p.deck.discard_pile)
    assert g.static_purchase_supply.get('思想家', 0) == starting_supply + 1



def test_propagandist_trashes_self_then_grants_build_and_one_move():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '宣傳家')]
    p.organizations = {'北京': 1}
    p.moves_left = 0
    starting_supply = g.static_purchase_supply.get('宣傳家', 0)

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    built_town, resolved = resolve_first_build_town(g, p)
    assert resolved.get('success'), resolved
    assert p.organizations == {'北京': 1, built_town: 1}
    assert p.moves_left == 1
    assert '宣傳家' not in names(p.deck.discard_pile)
    assert g.static_purchase_supply.get('宣傳家', 0) == starting_supply + 1



def test_capitalist_trashes_self_and_grants_three_money_and_three_propaganda():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '資本家')]
    p.resources = {'money': 0, 'propaganda': 0}
    starting_supply = g.static_purchase_supply.get('資本家', 0)

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert p.resources == {'money': 3, 'propaganda': 3}
    assert '資本家' not in names(p.deck.discard_pile)
    assert g.static_purchase_supply.get('資本家', 0) == starting_supply + 1



def test_funder_trashes_self_and_grants_two_money_and_two_propaganda():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '資助者')]
    p.resources = {'money': 0, 'propaganda': 0}
    starting_supply = g.static_purchase_supply.get('資助者', 0)

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert p.resources == {'money': 2, 'propaganda': 2}
    assert '資助者' not in names(p.deck.discard_pile)
    assert g.static_purchase_supply.get('資助者', 0) == starting_supply + 1



def test_distraction_trashes_self_and_returns_to_static_supply():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '分神')]
    starting_supply = g.static_purchase_supply.get('分神', 0)

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert '分神' not in names(p.deck.discard_pile)
    assert g.static_purchase_supply.get('分神', 0) == starting_supply + 1



def test_leadership_draws_one_card():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '領導')]
    p.deck.draw_pile = [Card('Draw1', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert names(p.hand) == ['Draw1']



def test_leadership_reshuffles_discard_to_draw_after_reaction_skip_and_can_advance():
    g = make_game()
    actor, reactor = g.players
    actor.hand = [card(g, '領導')]
    actor.deck.draw_pile = []
    actor.deck.discard_pile = [Card('DiscardDraw1', 'command', {})]
    reactor.hand = [card(g, '爆料黑幕')]

    prompted = g.play_card(0, mode='action')

    assert prompted.get('pending_choice') is True, prompted
    assert g.pending_choice and g.pending_choice['type'] == 'reaction_choice'
    assert g.pending_choice['player_name'] == reactor.name
    assert names(actor.hand) == []
    assert any('played 領導; waiting up to 10 seconds for P2 to choose cancel reaction' in entry for entry in g.action_log)

    skipped = g.resolve_pending_choice(reactor.id, 0)

    assert skipped.get('success'), skipped
    assert skipped.get('skipped_reaction') is True
    assert g.pending_choice is None
    assert names(actor.hand) == ['DiscardDraw1']
    assert names(actor.deck.discard_pile) == ['領導']
    advanced = g.advance_turn_phase()
    assert advanced.get('success'), advanced
    assert g.turn_phase == TurnPhase.END



def test_plotting_draws_two_cards():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '謀劃')]
    p.deck.draw_pile = [Card('Bottom', 'command', {}), Card('Draw1', 'command', {}), Card('Draw2', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert names(p.hand) == ['Draw2', 'Draw1']



def test_strategy_draws_three_cards():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '戰略')]
    p.deck.draw_pile = [Card('Bottom', 'command', {}), Card('Draw1', 'command', {}), Card('Draw2', 'command', {}), Card('Draw3', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert names(p.hand) == ['Draw3', 'Draw2', 'Draw1']



def test_transport_c_grants_two_moves():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '交通經驗丙')]
    p.moves_left = 0

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert p.moves_left == 2



def test_transport_b_grants_four_moves():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '交通經驗乙')]
    p.moves_left = 0

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert p.moves_left == 4



def test_transport_a_grants_six_moves():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '交通經驗甲')]
    p.moves_left = 0

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert p.moves_left == 6



def test_organization_c_builds_one_via_town_choice():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '組織經驗丙')]
    p.organizations = {'北京': 1}

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    built_town, resolved = resolve_first_build_town(g, p)
    assert resolved.get('success'), resolved
    assert p.organizations == {'北京': 1, built_town: 1}



def test_organization_b_builds_two_via_sequential_town_choices():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '組織經驗乙')]
    p.organizations = {'北京': 1}

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    first_town, first = resolve_first_build_town(g, p)
    assert first.get('success') and first.get('pending_choice'), first
    second_town, second = resolve_first_build_town(g, p)
    assert second.get('success'), second
    assert p.organizations == {'北京': 1, first_town: 1, second_town: 1}
    assert first_town != second_town



def test_organization_a_builds_one_even_with_ignore_distance_flag():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '組織經驗甲')]
    p.organizations = {'北京': 1}

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    built_town, resolved = resolve_first_build_town(g, p)
    assert resolved.get('success'), resolved
    assert p.organizations == {'北京': 1, built_town: 1}



def test_press_advantage_only_gains_card_costing_three_or_less_from_discard():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '乘勝追擊')]
    cheap = Card('CheapTarget', 'command', {})
    expensive = Card('ExpensiveTarget', 'command', {})
    p.deck.discard_pile = [cheap, expensive]
    g.structured_cards.append({'name': 'CheapTarget', 'cost': {'money': 2, 'propaganda': 0}})
    g.structured_cards.append({'name': 'ExpensiveTarget', 'cost': {'money': 4, 'propaganda': 0}})

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'card_choice'
    assert g.pending_choice['choice_key'] == 'gain_from_discard'
    assert names(g.pending_choice['cards']) == ['CheapTarget']
    resolved = g.resolve_pending_choice(p.id, 0)
    assert resolved.get('success'), resolved
    assert 'CheapTarget' in names(p.hand)
    assert 'ExpensiveTarget' not in names(p.hand)
    assert 'ExpensiveTarget' in names(p.deck.discard_pile)



def test_missing_cards_exist_in_structured_action_data():
    g = make_game()
    structured = {c['name']: c for c in g.structured_cards}
    for name in ['企業人脈', '產業滲透', '企畫遊說', '行動募資', '點燃熱情', '樹立信心', '凝聚共識', '擴大戰果', '爆料黑幕', '乘勝追擊']:
        assert name in structured
        assert structured[name].get('effect'), name


def test_planning_lobby_reveals_top_card_cost_and_grants_correct_money():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '企畫遊說')]
    p.deck.draw_pile = [Card('CheapBottom', 'command', {}), Card('ExpensiveTop', 'command', {})]
    # Make ExpensiveTop cost >= 3 via structured card lookup name.
    g.structured_cards.append({'name': 'ExpensiveTop', 'cost': {'money': 3, 'propaganda': 0}})

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert p.resources['money'] == 4
    assert names(p.deck.draw_pile)[-1] == 'ExpensiveTop'



def test_criticism_prompts_player_to_choose_card_from_hand_or_discard_then_trashes_selected_card():
    g = make_game()
    p = g.current_player()
    selected = Card('SelectedDiscard', 'command', {})
    other_discard = Card('OtherDiscard', 'command', {})
    hand_keep = Card('HandKeep', 'command', {})
    p.hand = [card(g, '批判'), hand_keep]
    p.deck.discard_pile = [selected, other_discard]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['choice_key'] == 'trash_from_hand_or_discard'
    assert g.pending_choice['type'] == 'card_choice'
    pending_cards = g.pending_choice['cards']
    assert [entry['zone'] for entry in pending_cards] == ['hand', 'discard', 'discard']
    assert [getattr(entry['card'], 'name', str(entry['card'])) for entry in pending_cards] == ['HandKeep', 'SelectedDiscard', 'OtherDiscard']

    resolved = g.resolve_pending_choice(p.id, 1)
    assert resolved.get('success'), resolved
    assert resolved.get('chosen_card') == 'SelectedDiscard'
    assert resolved.get('zone') == 'discard'
    assert 'SelectedDiscard' not in names(p.deck.discard_pile)
    assert 'OtherDiscard' in names(p.deck.discard_pile)
    assert 'HandKeep' in names(p.hand)
    assert g.pending_choice is None


if __name__ == '__main__':
    tests = [obj for name, obj in globals().items() if name.startswith('test_')]
    failures = 0
    for test in tests:
        try:
            test()
            print(f'PASS {test.__name__}')
        except Exception as exc:
            failures += 1
            print(f'FAIL {test.__name__}: {exc}')
    if failures:
        raise SystemExit(1)


def test_intel_network_first_option_adds_internal_conflict_to_up_to_three_other_players_only():
    g = Game([('p1', 'viewer'), ('p2', 'enemyA'), ('p3', 'enemyB'), ('p4', 'enemyC')])
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.pending_base_choices = {}
    pin_noop_event(g)
    actor, enemy_a, enemy_b, enemy_c = g.players
    actor.faction_id = 'red_army'
    for player in g.players[1:]:
        player.faction_id = 'hong_kong'
    actor.hand = [card(g, '情報網')]
    for player in g.players:
        player.deck.discard_pile = []

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert g.pending_choice and g.pending_choice['type'] == 'option_choice'

    resolved = g.resolve_pending_choice(actor.id, 0)

    assert resolved.get('success'), resolved
    assert names(actor.deck.discard_pile) == ['情報網']
    assert names(enemy_a.deck.discard_pile) == ['內鬥']
    assert names(enemy_b.deck.discard_pile) == ['內鬥']
    assert names(enemy_c.deck.discard_pile) == ['內鬥']


def _advance_one_full_turn(g):
    """Drive ACTION -> END -> next player's ACTION via the real turn-phase state
    machine (not manual field pokes). A round wrap draws a real random event, which
    can itself inject an unrelated pending_choice (e.g. an interactive event prompt)
    before we get a chance to look — re-pin the no-op event and clear it immediately
    after, rather than asserting pending_choice is None first."""
    assert g.turn_phase == TurnPhase.ACTION
    assert g.advance_turn_phase().get('success')
    assert g.turn_phase == TurnPhase.END
    g.advance_turn_phase()
    pin_noop_event(g)
    assert g.turn_phase == TurnPhase.ACTION


def test_產業滲透_reaction_prompt_reappears_on_a_later_turn_after_being_used():
    """2026-08-02 playtest 更正項：`產業滲透`第一次成功取消後，下一回合對手再打出可取消的
    卡牌時，觀察者懷疑取消詢問不再出現。透過真正的 `advance_turn_phase()`（而非手動改
    `current_player_index`）跑完一整輪回合，驗證：(a) reactor 的 `reaction_prompted_player_ids`
    只在「同一回合內」抑制重複詢問（既有行為，見
    `test_first_other_player_action_prompts_cancel_reaction_once_with_all_available_cards`），
    (b) 換到下一回合（`turn_log` 透過 `_end_turn()` 重建）後，只要 reactor 手上仍有一張
    `產業滲透`，取消詢問會正確地再次出現——排除「reaction_prompted_player_ids 或 turn_log
    未正確跨回合重置」的假設；playtest 觀察到的現象實際成因是第一張牌用掉後被棄置，
    需要重新抽到／購買新一張才有牌可用，並非程式錯誤。"""
    g = make_game()
    actor, reactor = g.players
    actor.hand = [card(g, '點燃熱情')]
    reactor.hand = [card(g, '產業滲透')]

    first = g.play_card(0, mode='action')
    assert first.get('pending_choice') is True, first
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['產業滲透']

    resolved = g.resolve_pending_choice(reactor.id, 1)
    assert resolved.get('success'), resolved
    assert resolved.get('reaction_card') == '產業滲透'
    # 點燃熱情 有資金費用 -> 產業滲透 的 conditional_draw(canceled_money_cost_card) 會讓
    # reactor 額外抽 1 張牌，因此手牌不會直接歸零；真正要驗證的不變量是「用掉的那張
    # 產業滲透本身」離開手牌、進了棄牌堆，而不是手牌總數。
    assert '產業滲透' not in names(reactor.hand)
    assert names(reactor.deck.discard_pile)[-1] == '產業滲透'

    # Simulate drawing/buying a fresh copy for the reactor's next opportunity —
    # the reaction-gating logic under test doesn't own the purchase economy.
    reactor.hand = list(reactor.hand) + [card(g, '產業滲透')]

    _advance_one_full_turn(g)  # actor's turn ends -> reactor's turn begins
    assert g.current_player_index == g.players.index(reactor)
    _advance_one_full_turn(g)  # reactor's turn ends -> wraps back to actor
    assert g.current_player_index == g.players.index(actor)

    actor.hand = [card(g, '點燃熱情')]
    second = g.play_card(0, mode='action')

    assert second.get('pending_choice') is True, second
    assert g.pending_choice and g.pending_choice['type'] == 'reaction_choice'
    assert '產業滲透' in [entry['name'] for entry in g.pending_choice['cards']]

    reaction_entry = next(e for e in g.pending_choice['cards'] if e['name'] == '產業滲透')
    second_resolved = g.resolve_pending_choice(reactor.id, g.pending_choice['cards'].index(reaction_entry) + 1)
    assert second_resolved.get('success'), second_resolved
    assert second_resolved.get('reaction_card') == '產業滲透'
    assert '產業滲透' not in names(reactor.hand)


def test_爆料黑幕_reaction_prompt_reappears_on_a_later_turn_after_being_used():
    """同上一項，換成 `爆料黑幕`（取消條件恆真，不要求被取消的牌有資金費用）——確認
    這兩張常被一起討論的取消反應卡，重置行為是共用同一段程式碼、結果一致。"""
    g = make_game()
    actor, reactor = g.players
    actor.hand = [card(g, '領導')]
    reactor.hand = [card(g, '爆料黑幕')]

    first = g.play_card(0, mode='action')
    assert first.get('pending_choice') is True, first
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['爆料黑幕']

    resolved = g.resolve_pending_choice(reactor.id, 1)
    assert resolved.get('success'), resolved
    assert resolved.get('reaction_card') == '爆料黑幕'
    # 領導有宣傳費用 -> 爆料黑幕的 conditional_draw(canceled_propaganda_card) 會讓 reactor
    # 額外抽 1 張牌；真正要驗證的不變量是用掉的那張爆料黑幕離開手牌、進了棄牌堆。
    assert '爆料黑幕' not in names(reactor.hand)
    assert names(reactor.deck.discard_pile)[-1] == '爆料黑幕'

    reactor.hand = list(reactor.hand) + [card(g, '爆料黑幕')]

    _advance_one_full_turn(g)
    assert g.current_player_index == g.players.index(reactor)
    _advance_one_full_turn(g)
    assert g.current_player_index == g.players.index(actor)

    actor.hand = [card(g, '領導')]
    second = g.play_card(0, mode='action')

    assert second.get('pending_choice') is True, second
    assert '爆料黑幕' in [entry['name'] for entry in g.pending_choice['cards']]

    reaction_entry = next(e for e in g.pending_choice['cards'] if e['name'] == '爆料黑幕')
    second_resolved = g.resolve_pending_choice(reactor.id, g.pending_choice['cards'].index(reaction_entry) + 1)
    assert second_resolved.get('success'), second_resolved
    assert second_resolved.get('reaction_card') == '爆料黑幕'
    assert '爆料黑幕' not in names(reactor.hand)


def test_reaction_prompt_no_longer_throttled_by_any_per_turn_bookkeeping():
    """2026-08-02 使用者更正後移除了 `reaction_prompted_player_ids` 這個 per-turn 節流欄位
    （原本讓同一位 reactor 這回合只會被問一次，是對卡面規則的誤解）。這裡直接確認
    `_new_turn_log()` 不再產生這個欄位，且同一回合內連續兩次出牌都會各自完整詢問一次。"""
    g = make_game()
    assert 'reaction_prompted_player_ids' not in g.turn_log

    actor, reactor = g.players
    actor.hand = [card(g, '點燃熱情')]
    reactor.hand = [card(g, '產業滲透')]
    g.play_card(0, mode='action')
    assert g.pending_choice is not None
    g.resolve_pending_choice(reactor.id, 1)
    assert 'reaction_prompted_player_ids' not in g.turn_log

    reactor.hand = [card(g, '產業滲透')]
    actor.hand = [card(g, '點燃熱情')]
    second = g.play_card(0, mode='action')
    assert second.get('pending_choice') is True, second


def test_red_army_aid_draw_is_logged_with_the_specific_card_name():
    """2026-08-04 使用者需求：抽牌類效果（含紅軍奧援）的紀錄要寫出因為使用什麼卡牌、
    實際抽到哪些牌，而不是只有「抽了1張牌」這種不具名的訊息。"""
    g = make_game()
    actor, red = g.players
    actor.faction_id = 'liberals'
    red.faction_id = 'red_army'
    actor.hand = [g._make_support_card('紅軍奧援')]
    actor.deck.draw_pile = [Card('SpecificDrawnCard', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert 'SpecificDrawnCard' in names(actor.hand)
    assert any('因紅軍奧援抽到：SpecificDrawnCard' in entry for entry in g.action_log), g.action_log


def test_standard_draw_effect_card_logs_the_specific_drawn_card_name():
    """同上一項，換成一般透過 `effect_engine.py` 的 `draw` 效果型別（例如『領導』）觸發的
    抽牌，確認也會寫出具體卡名，不只有紅軍奧援這個特判路徑才有。"""
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '領導')]
    p.deck.draw_pile = [Card('SpecificDrawnCard', 'command', {})]

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert 'SpecificDrawnCard' in names(p.hand)
    assert any('因領導抽到：SpecificDrawnCard' in entry for entry in g.action_log), g.action_log


def test_card_build_organization_candidates_refresh_live_after_a_move_between_builds():
    """2026-08-04 playtest 回報：先打出宣傳家／組織經驗丙這類牌，在桃園建立第一個組織，
    接著把組織移動到別的城鎮，第二次建立候選卻仍是移動前、臺北附近的舊清單。根因是
    `card_build_organization` 的候選城鎮只在佇列批次啟動當下（`_activate_next_queued_
    card_build`）算一次就固定存進 `choice['towns']`，之後即使玩家移動了組織，只要這批
    額度還沒被解決，候選清單就不會重新投影。這裡直接用真正的 `play_card()`／
    `resolve_pending_choice()`／`move_organization()`（不是走任何測試專用捷徑）重現
    「建立→移動→建立」序列，確認第二次候選會即時反映移動後的位置。"""
    g = make_game()
    actor = g.current_player()
    actor.faction_id = 'taiwan_green'
    actor.base = '臺北'
    actor.organizations = {'臺北': 1}
    actor.hand = [card(g, '組織經驗丙'), card(g, '組織經驗乙')]
    actor.moves_left = 10
    actor.resources = {'money': 0, 'propaganda': 0}

    g.play_card(0, mode='action')  # 組織經驗丙：range 1，先進入 card_build_organization
    g.play_card(0, mode='action')  # 組織經驗乙：疊加進同一個連續建立 session，共3個額度
    assert g.pending_choice['choice_key'] == 'card_build_organization'
    assert g._remaining_card_build_entitlements() == 3
    first_towns = sorted(t['town'] for t in g.pending_choice['towns'])
    assert first_towns == ['基隆', '新北', '桃園']  # 範圍1格內都是臺北的鄰居

    build_index = next(i for i, t in enumerate(g.pending_choice['towns']) if t['town'] == '桃園')
    resolved = g.resolve_pending_choice(actor.id, build_index)
    assert resolved.get('success'), resolved
    assert actor.organizations == {'臺北': 1, '桃園': 1}

    move_result = g.move_organization('桃園', '新竹', mode='rail')
    assert move_result.get('success'), move_result
    assert actor.organizations == {'臺北': 1, '新竹': 1}

    # 舊行為：候選清單仍停留在「桃園建立完當下」算好的舊快照（基隆／宜蘭／新北／新竹）。
    # 修正後：state() 序列化與 resolve 都會用目前的組織位置重新即時投影，新竹的鄰居
    # 苗栗要出現在候選裡；已經被移走、目前是空城的桃園要重新變回合法候選；已經不再
    # 鄰接任何己方組織的宜蘭則不該再出現。
    live_towns_from_state = sorted(t['town'] for t in g.state()['pending_choice']['towns'])
    assert live_towns_from_state == ['基隆', '新北', '桃園', '苗栗']
    assert '宜蘭' not in live_towns_from_state

    second_index = next(i for i, t in enumerate(g.pending_choice['towns']) if t['town'] == '苗栗')
    second_resolved = g.resolve_pending_choice(actor.id, second_index)
    assert second_resolved.get('success'), second_resolved
    assert actor.organizations == {'臺北': 1, '新竹': 1, '苗栗': 1}
    assert g._remaining_card_build_entitlements() == 1


def test_non_red_army_movement_is_not_restricted_by_build_development_space():
    """2026-08-04 playtest 回報＋更正：使用者先回報「紅軍以外玩家組織建立後可遷移至任意
    城鎮」，接著澄清：建立組織才受「發展空間」限制，遷移只要城鎮相鄰（含翻牆規則）、
    移動次數足夠就該成功，即使目的地不是該陣營可以建立組織的城鎮。這推翻了更早一次
    playtest（`scripts/validate_wall_crossing_movement.py` 的 `case_reported_dongsha_
    kwuntong`）錯誤回報的「應該擋下」判斷——使用者確認那次回報本身就錯了：翻牆本來就
    有獨立的2次移動成本限制，不需要再疊加發展空間限制。這裡直接用真正的
    `move_organization()` 重現東沙（牆外）→觀塘（牆內，不適用臺灣陣營）成功遷移。"""
    g = make_game()
    actor = g.current_player()
    actor.faction_id = 'taiwan_green'
    actor.base = '臺北'
    actor.organizations = {'臺北': 1, '東沙': 1}
    actor.moves_left = 5
    assert g.can_faction_develop_in_town('taiwan_green', '觀塘') is False

    result = g.move_organization('東沙', '觀塘', mode='road')

    assert result.get('success'), result
    assert actor.organizations == {'臺北': 1, '觀塘': 1}


def test_red_army_movement_still_restricted_to_red_army_development_space():
    """同上一項的對照組：紅軍自己的發展空間限制是獨立的一條檢查
    （`_validate_organization_move` 裡的 red_army 專屬分支），不受上面那項放寬影響——
    使用者的回報明確是「紅軍以外」的玩家，紅軍本身的遷移限制維持不變。"""
    g = make_game()
    actor = g.current_player()
    actor.faction_id = 'red_army'
    actor.base = '北京'
    actor.organizations = {'北京': 1, '沖繩': 1}
    actor.moves_left = 5
    assert g.can_faction_develop_in_town('red_army', '福岡') is False

    result = g.move_organization('沖繩', '福岡', mode='road')

    assert result.get('error') == 'Red Army organization cannot leave Red Army development space', result
    assert actor.organizations == {'北京': 1, '沖繩': 1}


def test_armory_town_organizations_reduce_armed_card_purchase_cost():
    """2026-08-04 使用者回報規則：玩家在軍火庫城鎮每擁有1個組織，購買每張武裝類卡牌
    所需支付的費用減少1點資金，至多可藉軍火庫減少3點資金。「一城一組織」invariant下
    每座軍火庫城鎮最多只會計1個組織，所以實際上是數「擁有幾座不同的軍火庫城鎮」。"""
    g = make_game()
    p = g.current_player()
    p.faction_id = 'taiwan_green'
    armed_card = card(g, '武裝集團')  # 印刷購買費用 資金4
    assert g._card_purchase_cost(armed_card) == {'money': 4, 'propaganda': 0}

    p.organizations = {}
    assert g._effective_purchase_cost(p, armed_card) == {'money': 4, 'propaganda': 0}

    p.organizations = {'佬沃': 1}
    assert g._effective_purchase_cost(p, armed_card) == {'money': 3, 'propaganda': 0}

    p.organizations = {'佬沃': 1, '美斯樂': 1}
    assert g._effective_purchase_cost(p, armed_card) == {'money': 2, 'propaganda': 0}

    p.organizations = {'佬沃': 1, '美斯樂': 1, '賀猛': 1}
    assert g._effective_purchase_cost(p, armed_card) == {'money': 1, 'propaganda': 0}

    # 第4座軍火庫城鎮不再繼續減免，維持3點上限。
    p.organizations = {'佬沃': 1, '美斯樂': 1, '賀猛': 1, '芒賽': 1}
    assert g._effective_purchase_cost(p, armed_card) == {'money': 1, 'propaganda': 0}

    # 非武裝類卡牌完全不受影響。
    non_armed_card = card(g, '領導')
    assert g._effective_purchase_cost(p, non_armed_card) == g._card_purchase_cost(non_armed_card)


def test_armory_discount_applies_to_the_actual_purchase_charge_not_just_the_display():
    """確認折扣不是只有顯示用——真的用 buy_cards() 購買時，實際扣款也要反映折扣後金額，
    而不是印刷原價。"""
    g = make_game()
    g.turn_phase = TurnPhase.END
    p = g.current_player()
    p.faction_id = 'taiwan_green'
    p.organizations = {'佬沃': 1, '美斯樂': 1}
    p.resources = {'money': 2, 'propaganda': 0}
    p.purchased_this_turn = []
    g.purchase_area[0] = card(g, '武裝集團')
    g.static_purchase_supply['武裝集團'] = 1

    result = g.buy_cards([0])

    assert result.get('success'), result
    assert p.resources['money'] == 0  # 印刷費用4 - 軍火庫折扣2 = 2，剛好用完手上的2資金
    assert '武裝集團' in names(p.deck.discard_pile)
