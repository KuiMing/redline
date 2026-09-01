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


def test_red_support_resource_mode_grants_resources_immediately_without_target_choice():
    # 2026-08-08 使用者更正：選擇反共玩家棄牌堆只是行動模式的效果（把牌傳給對手）；
    # 資源模式跟一般資源卡一樣，直接取得資源、卡片進自己棄牌堆，不問要放進誰的棄牌堆
    # （覆蓋 2026-08-07 曾經誤把行動模式的目標選擇也套用到資源模式的行為）。
    g = make_game()
    red = g.current_player()
    rebel = g.players[1]
    rebel.faction_id = 'hong_kong'
    # Even a legacy/debug object without resources metadata must use the canonical printed 1/1.
    red.hand = [Card('紅軍奧援', 'support', {})]
    red.resources = {'money': 0, 'propaganda': 0}
    rebel.deck.discard_pile = []

    result = g.play_card(0, mode='resource')

    assert result.get('success'), result
    assert not result.get('pending_choice')
    assert g.pending_choice is None
    assert red.resources == {'money': 1, 'propaganda': 1}
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


def test_taiwan_support_tier3_first_red_army_base_hit_succeeds_without_building():
    """紅軍根據地第 1 次命中尚未移除組織，因此不能補位；但瓦解命中本身已成功，
    API 應回傳成功且明確標示 built=False，而不是在部分結算後誤報整個效果失敗。"""
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

    assert resolved.get('success') is True, resolved
    assert resolved.get('red_base_hit') is True
    assert resolved.get('red_base_destroyed') is False
    assert resolved.get('built') is False
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



def test_red_support_resource_mode_from_rebel_hand_grants_resources_and_returns_to_red_discard():
    # 紅軍奧援是普通奧援「資源模式只棄置」的唯一例外。反共玩家使用時取得印刷的 1/1，
    # 不抽牌，並把牌放回紅軍玩家棄牌堆。
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
    assert rebel.resources == {'money': 1, 'propaganda': 1}
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
    # 此案例只驗證情報網的瓦解分支；固定為無盟旗學校的陣營，避免隨機蒙古能力改變前置條件。
    p2.faction_id = 'hong_kong'
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


def test_expose_scandal_and_industry_infiltration_action_mode_blocked_on_own_turn():
    """2026-08-07 使用者指出這兩張牌的取消能力感覺是被動觸發的——確認屬實：兩張卡的
    `effect` 只有 `cancel_card` + `conditional_draw`，沒有像情報網那樣的 choose_one
    主動分支，只能透過反應視窗（`_set_pending_reaction_choice`）在對方出牌時被動觸發，
    不會經過 `play_card()`。自己回合主動點「行動」等於取消不存在的目標、白白浪費這張
    卡，因此在 `play_card()` 擋下，比照其他需要合法對象才能打出的卡片。資源模式（打出
    拿卡面印的宣傳/資金）不受影響，仍可正常使用。"""
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '爆料黑幕'), card(g, '產業滲透')]
    p.resources = {'money': 0, 'propaganda': 0}

    scandal_action = g.play_card(0, mode='action')
    assert scandal_action.get('error'), scandal_action
    assert names(p.hand) == ['爆料黑幕', '產業滲透']  # 卡沒被消耗

    infiltration_action = g.play_card(1, mode='action')
    assert infiltration_action.get('error'), infiltration_action
    assert names(p.hand) == ['爆料黑幕', '產業滲透']

    scandal_resource = g.play_card(0, mode='resource')
    assert scandal_resource.get('success'), scandal_resource
    assert p.resources['propaganda'] == 2
    assert names(p.hand) == ['產業滲透']

    infiltration_resource = g.play_card(0, mode='resource')
    assert infiltration_resource.get('success'), infiltration_resource
    assert p.resources['money'] == 2
    assert names(p.hand) == []


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
    # 2026-08-05 修正：產業滲透能不能取消是無條件的（卡面「取消1張對方所打出行動卡之能力」
    # 沒有費用限制），資金費用只影響取消後有沒有 bonus 抽牌（「若被取消的牌購買費用有資金，
    # 抽1張牌」）。領導購買費用是宣傳1、資金0，產業滲透一樣要被列為候選——候選名單仍是逐次
    # 出牌各自重算，不是沿用第一次的名單，只是這裡不再排除產業滲透。
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['情報網', '爆料黑幕', '產業滲透']

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
    assert '爆料黑幕' not in names(second_reactor.hand)
    # 2026-08-05 反制鏈：second_reactor 打出的 爆料黑幕 本身也是一次可被反制的出牌。
    # first_reactor 手上還留著 產業滲透（爆料黑幕的購買費用含資金1，符合產業滲透取消條件），
    # 因此系統正確地又跳出一層取消視窗，問 first_reactor 是否反制。這裡讓它謝絕，
    # 這條鏈就停在深度2（點燃熱情被取消、爆料黑幕生效），與加入反制鏈前的最終結果一致。
    assert canceled.get('opened_counter_layer') is True
    assert g.pending_choice is not None
    assert g.pending_choice['player_id'] == first_reactor.id
    assert g.pending_choice['acting_player_id'] == second_reactor.id
    assert g.pending_choice['played_card_name'] == '爆料黑幕'
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['產業滲透']

    settled = g.resolve_pending_choice(first_reactor.id, 0)
    assert settled.get('success'), settled
    assert g.pending_choice is None
    assert names(actor.deck.discard_pile) == ['點燃熱情']  # 原始牌被取消、直接進棄牌堆
    assert names(second_reactor.deck.discard_pile) == ['爆料黑幕']
    assert names(first_reactor.hand) == ['產業滲透']  # 謝絕反制，卡留手上


def test_counter_cancel_depth3_lets_original_action_resolve():
    """2026-08-05 P2『被取消的一方應該也能反過來取消對方的取消』深度3：A 出 領導，
    B 用 情報網 取消，A 再用手上的 爆料黑幕 反制 B 的 情報網。結果應等同 A 的 領導
    從未被取消過——領導的抽牌效果正常執行，B 的 情報網 效果完全不發生（不放內鬥／
    不瓦解），A 的 爆料黑幕 因為成功取消了 情報網（其購買費用含宣傳3）而拿到 bonus 抽牌。"""
    g = make_game()
    actor, reactor = g.players
    actor.hand = [card(g, '領導'), card(g, '爆料黑幕')]
    actor.deck.draw_pile = [Card('D1', 'command', {}), Card('D2', 'command', {})]
    reactor.hand = [card(g, '情報網')]

    result = g.play_card(0, mode='action')
    assert result.get('pending_choice') is True, result
    assert g.pending_choice['player_id'] == reactor.id
    assert g.pending_choice['played_card_name'] == '領導'
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['情報網']

    canceled = g.resolve_pending_choice(reactor.id, 1)  # B 用 情報網 取消 領導
    assert canceled.get('success'), canceled
    assert canceled.get('reaction_card') == '情報網'
    assert canceled.get('canceled_card') == '領導'
    assert canceled.get('opened_counter_layer') is True
    assert g.pending_choice is not None
    assert g.pending_choice['player_id'] == actor.id
    assert g.pending_choice['acting_player_id'] == reactor.id
    assert g.pending_choice['played_card_name'] == '情報網'
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['爆料黑幕']
    # 反制層開啟前，領導的抽牌效果尚未執行（deferred resolution：先問完整條鏈再結算）；
    # actor 手上還留著尚未打出的 爆料黑幕（等一下要用來反制）。
    assert names(actor.hand) == ['爆料黑幕']
    assert names(actor.deck.draw_pile) == ['D1', 'D2']

    countered = g.resolve_pending_choice(actor.id, 1)  # A 用 爆料黑幕 反制 情報網
    assert countered.get('success'), countered
    assert countered.get('reaction_card') == '爆料黑幕'
    assert countered.get('canceled_card') == '情報網'
    assert g.pending_choice is None, '沒有第三方候選人，整條鏈應直接結算完畢'

    # 領導的效果正常生效（抽1張），且爆料黑幕成功取消 情報網（購買費用含宣傳3）拿到 bonus 抽牌
    assert sorted(names(actor.hand)) == ['D1', 'D2']
    assert names(actor.deck.draw_pile) == []
    assert names(actor.deck.discard_pile) == ['爆料黑幕', '領導']
    assert names(reactor.deck.discard_pile) == ['情報網']
    assert names(reactor.hand) == []


def test_counter_cancel_depth3_with_bystander_who_always_declines():
    """三人局：C 全程持有可取消卡但每一層都選擇不取消，結果應與只有 A、B 兩人時完全
    一樣——C 手握合格反應卡這件事本身不該改變任何結算，只是多一次詢問。"""
    g = Game([('p1', 'P1'), ('p2', 'P2'), ('p3', 'P3')])
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.pending_base_choices = {}
    pin_noop_event(g)
    g.players[0].faction_id = 'red_army'
    actor, b, c = g.players
    actor.hand = [card(g, '領導'), card(g, '爆料黑幕')]
    actor.deck.draw_pile = [Card('D1', 'command', {}), Card('D2', 'command', {})]
    b.hand = [card(g, '情報網')]
    c.hand = [card(g, '爆料黑幕')]  # 全程候選人，但每次都選擇不取消

    result = g.play_card(0, mode='action')
    assert result.get('pending_choice') is True, result
    # 最初這層：B、C 都持合格卡，先問 B（players 順序）
    assert g.pending_choice['player_id'] == b.id
    assert [entry['name'] for entry in g.pending_choice['remaining_candidates'][0]['cards']] == ['爆料黑幕']

    canceled = g.resolve_pending_choice(b.id, 1)  # B 用 情報網 取消 領導（C 沒被問到，因為 B 先取消了）
    assert canceled.get('success'), canceled
    assert canceled.get('opened_counter_layer') is True
    # 反制層：候選人是 A（自己的爆料黑幕）與 C（爆料黑幕），排除剛出牌的 B。players 順序 A 先問。
    assert g.pending_choice['player_id'] == actor.id
    assert g.pending_choice['remaining_candidates'] and g.pending_choice['remaining_candidates'][0]['player'] is c

    countered = g.resolve_pending_choice(actor.id, 1)  # A 反制
    assert countered.get('success'), countered
    assert g.pending_choice is not None, 'C 仍是候選人，其反應卡對 A 的爆料黑幕也合格'
    assert g.pending_choice['player_id'] == c.id
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['爆料黑幕']

    declined = g.resolve_pending_choice(c.id, 0)  # C 選擇不取消
    assert declined.get('success'), declined
    assert g.pending_choice is None

    assert sorted(names(actor.hand)) == ['D1', 'D2']
    assert names(actor.deck.discard_pile) == ['爆料黑幕', '領導']
    assert names(b.deck.discard_pile) == ['情報網']
    assert names(c.hand) == ['爆料黑幕']  # C 從未出牌，卡還在手上
    assert names(c.deck.discard_pile) == []


def test_counter_cancel_depth4_third_player_joins_chain_and_recancels_original():
    """使用者確認的產品設計：A 出牌、B 取消、A 反制、C 也能加入反制鏈再取消 A 的反制——
    使 A 的原始牌最終還是被取消（堆疊上方存活的取消次數為偶數→翻回取消）。"""
    g = Game([('p1', 'P1'), ('p2', 'P2'), ('p3', 'P3')])
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.pending_base_choices = {}
    pin_noop_event(g)
    g.players[0].faction_id = 'red_army'
    actor, b, c = g.players
    actor.hand = [card(g, '領導'), card(g, '爆料黑幕')]
    actor.deck.draw_pile = [Card('D1', 'command', {}), Card('D2', 'command', {})]
    b.hand = [card(g, '情報網')]
    c.hand = [card(g, '產業滲透')]  # 爆料黑幕購買費用含資金1，符合產業滲透取消條件

    result = g.play_card(0, mode='action')
    assert result.get('pending_choice') is True, result
    assert g.pending_choice['player_id'] == b.id

    step1 = g.resolve_pending_choice(b.id, 1)  # B 用 情報網 取消 A 的 領導
    assert step1.get('success'), step1
    assert g.pending_choice['player_id'] == actor.id
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['爆料黑幕']

    step2 = g.resolve_pending_choice(actor.id, 1)  # A 用 爆料黑幕 反制 B 的 情報網
    assert step2.get('success'), step2
    assert step2.get('opened_counter_layer') is True
    assert g.pending_choice is not None, 'C 手上的 產業滲透 對 A 的 爆料黑幕（含資金費用1）合格，應繼續開新層'
    assert g.pending_choice['player_id'] == c.id
    assert g.pending_choice['acting_player_id'] == actor.id
    assert g.pending_choice['played_card_name'] == '爆料黑幕'
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['產業滲透']

    step3 = g.resolve_pending_choice(c.id, 1)  # C 用 產業滲透 反制 A 的 爆料黑幕
    assert step3.get('success'), step3
    assert step3.get('reaction_card') == '產業滲透'
    assert step3.get('canceled_card') == '爆料黑幕'
    assert g.pending_choice is None, '沒有更多候選人（B、A 手牌已空），整條深度4的鏈直接結算'

    # 交替結算：stack = [領導, 情報網(B), 爆料黑幕(A), 產業滲透(C)]，n=3（奇數）
    # resolved[3]=True（頂端，沒人能取消它）→ resolved[2]=not resolved[3]=False（A 的爆料黑幕
    # 被取消）→ resolved[1]=not resolved[2]=True（B 的情報網翻回生效）→
    # resolved[0]=not resolved[1]=False（A 的領導最終仍是被取消）。
    assert names(actor.hand) == []  # 領導被取消，沒有抽牌
    assert names(actor.deck.draw_pile) == ['D1', 'D2']  # 沒人動用這副牌，領導的抽牌效果從未執行
    # actor 打出的兩張牌（領導＝原始牌、爆料黑幕＝反制用掉的反應卡）都被消耗進自己的棄牌堆，
    # 即使各自的效果都沒有生效（領導被取消；爆料黑幕本身也被 C 取消，沒有 bonus 抽牌）。
    assert names(actor.deck.discard_pile) == ['爆料黑幕', '領導']
    # 情報網翻回生效：`_resolve_reaction_context` 對『作為反應卡使用』的情報網固定只執行
    # cancel_card（不會走它印刷的 choose_one／放內鬥效果——那是情報網當作自己回合行動卡時
    # 才有的分支，2026-08-02 的既有規則），所以這裡只驗證它已從 B 手上消耗並進棄牌堆。
    assert names(b.deck.discard_pile) == ['情報網']
    # 產業滲透生效：取消的是 爆料黑幕（購買費用含資金1）→ 觸發 canceled_money_cost_card bonus 抽牌
    assert names(c.deck.discard_pile) == ['產業滲透']


def test_counter_cancel_chain_cannot_ask_same_reactor_twice_with_one_card():
    """終止性檢查：B 手上只有一張 爆料黑幕；B 在最初一層取消 A 的牌之後，即使 A 反制、
    鏈條繼續，B 也不該被『再問一次』——因為那張唯一的反應卡在第一次打出時就已經從手上
    移除。用一場「B 只有一張反應卡、A 反制後鏈條自然終止（B 沒有第二張可用）」的深度3
    情境驗證：手牌真的空了，且從未再次出現在任何一層的候選名單中。"""
    g = make_game()
    actor, b = g.players
    actor.hand = [card(g, '領導'), card(g, '爆料黑幕')]
    # 領導最終會生效（抽1），爆料黑幕反制情報網成功也會有 bonus 抽牌（見深度3測試的交替結算）
    # ——備兩張抽牌堆卡片，避免因抽牌堆耗盡觸發洗牌，讓斷言與這次終止性檢查無關的細節脫鉤。
    actor.deck.draw_pile = [Card('D1', 'command', {}), Card('D2', 'command', {})]
    b.hand = [card(g, '情報網')]  # B 唯一一張合格反應卡

    result = g.play_card(0, mode='action')
    assert result.get('pending_choice') is True, result
    assert g.pending_choice['player_id'] == b.id

    step1 = g.resolve_pending_choice(b.id, 1)  # B 用僅有的 情報網 取消
    assert step1.get('success'), step1
    assert names(b.hand) == [], 'B 唯一的反應卡打出後手牌應為空'
    # 反制層的候選人只計算 A（B 已經沒有合格卡，且遞迴排除了剛出牌的 B 本人）
    assert g.pending_choice['player_id'] == actor.id
    assert not g.pending_choice.get('remaining_candidates')

    step2 = g.resolve_pending_choice(actor.id, 1)  # A 反制
    assert step2.get('success'), step2
    assert g.pending_choice is None, 'B 手上已無合格卡，不應再被問一次；鏈條在此自然結束'
    assert names(b.hand) == []
    assert names(b.deck.discard_pile) == ['情報網']
    # 附帶驗證整條鏈仍照交替規則正確結算（與深度3測試同一種牌組合）：領導效果生效、
    # 爆料黑幕成功取消情報網並拿到 bonus 抽牌。
    assert sorted(names(actor.hand)) == ['D1', 'D2']
    assert names(actor.deck.discard_pile) == ['爆料黑幕', '領導']


def test_support_card_now_prompts_cancel_reaction_and_cancel_prevents_build():
    """2026-08-05 P2：先前『奧援卡（support card）不觸發取消反應』是刻意的 workaround
    ——因為奧援卡效果在 play_card 內即時結算，事後才跳取消詢問會留下 stale pending_choice。
    現在改為在奧援卡結算「之前」就開取消視窗（把 _execute_support_card 延後到
    _resume_reaction_pending_action），所以奧援卡也會正常跳取消詢問；取消成功時，被延後的
    建組織效果完全不會執行。此測試以東洋奧援 III 級（interactive_build_anywhere_inner）驗證。"""
    g = make_game()
    actor, reactor = g.players
    actor.faction_id = 'red_army'
    actor.organizations = {'北京': 1, '供應占用': 0}
    reactor.hand = [card(g, '爆料黑幕')]
    g._support_card_tier = lambda player, cardobj: (3, 0, [])
    actor.hand = [g._make_support_card('東洋奧援')]
    orgs_before = dict(actor.organizations)

    result = g.play_card(0, mode='action')
    assert result.get('pending_choice') is True, result
    assert g.pending_choice['type'] == 'reaction_choice', g.pending_choice
    assert g.pending_choice['player_id'] == reactor.id
    assert g.pending_choice['played_card_name'] == '東洋奧援'
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['爆料黑幕']
    # 反應視窗開在建組織之前——此時尚未有任何 support_interaction / 城鎮選擇 pending
    assert g.pending_choice['choice_key'] == 'cancel_other_player_action'

    canceled = g.resolve_pending_choice(reactor.id, 1)  # 用爆料黑幕取消
    assert canceled.get('success'), canceled
    assert canceled.get('canceled') is True, canceled
    assert g.pending_choice is None, g.pending_choice
    assert actor.organizations == orgs_before, '取消後不應建立任何組織'
    assert '爆料黑幕' in names(reactor.deck.discard_pile)
    assert '東洋奧援' in names(actor.deck.discard_pile)


def test_support_card_cancel_reaction_declined_lets_the_build_resolve():
    """對手不取消時，東洋奧援的建組織互動照常開啟、可完成建造（沒有被延後機制吃掉效果）。"""
    g = make_game()
    actor, reactor = g.players
    actor.faction_id = 'red_army'
    actor.organizations = {'北京': 1, '供應占用': 0}
    reactor.hand = [card(g, '爆料黑幕')]
    g._support_card_tier = lambda player, cardobj: (3, 0, [])
    actor.hand = [g._make_support_card('東洋奧援')]

    result = g.play_card(0, mode='action')
    assert g.pending_choice['type'] == 'reaction_choice', g.pending_choice

    skipped = g.resolve_pending_choice(reactor.id, 0)  # 不取消
    assert skipped.get('success'), skipped
    assert g.pending_choice and g.pending_choice['choice_key'] == 'support_interaction', g.pending_choice
    town = g.pending_choice['towns'][0]['town']
    built = g.resolve_pending_choice(actor.id, 0)
    assert built.get('success'), built
    assert actor.organizations.get(town, 0) >= 1, (town, actor.organizations)
    assert '爆料黑幕' in names(reactor.hand), '不取消時反應卡應保留在手'


def test_noninteractive_support_cancel_reaction_prevents_effect():
    """非互動型奧援（歐洲奧援 III 級＝獲得 4 宣傳）同樣會跳取消詢問；取消成功時效果不發生。"""
    g = make_game()
    actor, reactor = g.players
    actor.faction_id = 'federalists'
    actor.resources = {'money': 0, 'propaganda': 0}
    reactor.hand = [card(g, '情報網')]
    g._support_card_tier = lambda player, cardobj: (3, 0, [])
    actor.hand = [g._make_support_card('歐洲奧援')]

    result = g.play_card(0, mode='action')
    assert g.pending_choice['type'] == 'reaction_choice', g.pending_choice
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['情報網']

    canceled = g.resolve_pending_choice(reactor.id, 1)  # 情報網取消
    assert canceled.get('canceled') is True, canceled
    assert g.pending_choice is None
    assert actor.resources['propaganda'] == 0, '取消後不應獲得宣傳'
    assert '歐洲奧援' in names(actor.deck.discard_pile)
    assert '情報網' not in names(reactor.hand)


def test_command_then_support_card_each_prompt_cancel_reaction():
    """使用者原始情境（P2）：先打宣傳家（command）對手跳出爆料黑幕詢問；接著打東洋奧援
    （support）對手『這次也要』跳出爆料黑幕詢問——舊行為第二次完全不跳，是本項要修的 bug。"""
    g = make_game()
    actor, reactor = g.players
    actor.faction_id = 'red_army'
    actor.organizations = {'北京': 1, '供應占用': 0}
    reactor.hand = [card(g, '爆料黑幕'), card(g, '爆料黑幕')]

    actor.hand = [card(g, '宣傳家')]
    first = g.play_card(0, mode='action')
    assert first.get('pending_choice') is True, first
    assert g.pending_choice['type'] == 'reaction_choice', g.pending_choice
    assert g.pending_choice['played_card_name'] == '宣傳家'
    g.resolve_pending_choice(reactor.id, 0)  # 不取消宣傳家
    while g.pending_choice:  # 完成宣傳家自己的建組織/移動流程
        g.resolve_pending_choice(actor.id, 0)

    g._support_card_tier = lambda player, cardobj: (3, 0, [])
    actor.hand = [g._make_support_card('東洋奧援')]
    second = g.play_card(0, mode='action')
    assert second.get('pending_choice') is True, second
    assert g.pending_choice['type'] == 'reaction_choice', g.pending_choice
    assert g.pending_choice['played_card_name'] == '東洋奧援', '第二次（奧援卡）也必須跳出取消詢問'
    # 對手第一次沒取消，兩張爆料黑幕都還在手上，故第二次仍以兩張為候選
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['爆料黑幕', '爆料黑幕']


def test_illegal_support_card_is_rejected_before_cancel_reaction_window():
    """無合法目標的互動型奧援必須在開取消視窗『之前』就被打回手牌，不能白白讓對手花掉
    一張反應卡去取消一個本來就不合法的出牌。"""
    g = make_game()
    actor, reactor = g.players
    actor.faction_id = 'red_army'
    reactor.hand = [card(g, '爆料黑幕')]
    g._support_card_tier = lambda player, cardobj: (3, 0, [])
    support_card = g._make_support_card('東洋奧援')
    actor.hand = [support_card]
    # 以共用的 target source of truth 直接令其無合法目標
    g._support_interaction_targets = lambda *args, **kwargs: []

    result = g.play_card(0, mode='action')
    assert result.get('no_legal_target') is True, result
    assert result.get('error') == 'No legal target for interactive support card', result
    assert g.pending_choice is None, g.pending_choice
    assert actor.hand == [support_card], '不合法出牌應原樣退回手牌'
    assert names(reactor.hand) == ['爆料黑幕'], '對手的反應卡不該被消耗'


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
        # play_card now decides "no legal target" up front via the shared
        # _support_interaction_targets pre-check (before any mutation / reaction window),
        # so force *that* to report no targets rather than the downstream
        # _start_support_interaction opener.
        g._support_interaction_targets = lambda *args, **kwargs: []

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
    # play_card now detects "no legal target" via the shared _support_interaction_targets
    # pre-check before _execute_support_card runs (so no board/reaction-card is spent on an
    # illegal play), so the rejection log comes from play_card's own message.
    assert any('could not play 天方奧援: no legal target' in line for line in g.action_log)


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


def test_announce_action_banks_topdeck_right_and_grants_propaganda_immediately():
    g = make_game()
    p = g.current_player()
    bought = Card('PurchasedCard', 'command', {})
    p.deck.discard_pile = [bought]
    g.turn_log['purchased_cards_this_turn'] = [bought]

    p = play_only(g, '行動預告')

    # 打出當下立刻拿到宣傳，但頂牌只是銀行化成 1 次權利，購得的牌仍留在棄牌堆。
    assert p.resources['propaganda'] == 1
    assert g.turn_log['pending_topdeck_uses'] == 1
    assert 'PurchasedCard' in names(p.deck.discard_pile)
    assert not p.deck.draw_pile or names(p.deck.draw_pile)[-1] != 'PurchasedCard'

    used = g.use_pending_topdeck_right()

    assert used.get('success'), used
    assert g.turn_log['pending_topdeck_uses'] == 0
    assert names(p.deck.draw_pile)[-1] == 'PurchasedCard'
    assert 'PurchasedCard' not in names(p.deck.discard_pile)


def test_action_fundraising_banks_topdeck_right_and_grants_money_immediately():
    g = make_game()
    p = g.current_player()
    bought = Card('PurchasedCard', 'command', {})
    p.deck.discard_pile = [bought]
    g.turn_log['purchased_cards_this_turn'] = [bought]

    p = play_only(g, '行動募資')

    assert p.resources['money'] == 1
    assert g.turn_log['pending_topdeck_uses'] == 1
    assert 'PurchasedCard' in names(p.deck.discard_pile)

    used = g.use_pending_topdeck_right()

    assert used.get('success'), used
    assert names(p.deck.draw_pile)[-1] == 'PurchasedCard'
    assert 'PurchasedCard' not in names(p.deck.discard_pile)


def test_use_topdeck_right_before_any_purchase_errors_without_consuming_the_right():
    g = make_game()
    p = play_only(g, '行動預告')

    result = g.use_pending_topdeck_right()

    assert result.get('error'), result
    assert g.turn_log['pending_topdeck_uses'] == 1


def test_use_topdeck_right_with_two_purchases_lets_player_choose():
    g = make_game()
    p = play_only(g, '行動預告')
    bought1, bought2 = Card('先買的牌', 'command', {}), Card('後買的牌', 'command', {})
    p.deck.discard_pile = [bought1, bought2]
    g.turn_log['purchased_cards_this_turn'] = [bought1, bought2]

    used = g.use_pending_topdeck_right()

    assert used.get('pending_choice') is True
    assert g.pending_choice['choice_key'] == 'topdeck_purchased_choice'
    offered = names(g.pending_choice['cards'])
    assert sorted(offered) == ['先買的牌', '後買的牌']

    resolved = g.resolve_pending_choice(p.id, offered.index('先買的牌'))

    assert resolved.get('success'), resolved
    assert not g.pending_choice
    assert names(p.deck.draw_pile)[-1] == '先買的牌'
    assert '後買的牌' in names(p.deck.discard_pile)
    assert g.turn_log['pending_topdeck_uses'] == 0


def test_two_announce_action_plays_bank_two_independent_topdeck_rights():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '行動預告'), card(g, '行動預告')]
    p.resources = {'money': 0, 'propaganda': 0}

    assert g.play_card(0, mode='action').get('success')
    assert g.play_card(0, mode='action').get('success')

    assert p.resources['propaganda'] == 2
    assert g.turn_log['pending_topdeck_uses'] == 2

    bought1, bought2 = Card('先買的牌', 'command', {}), Card('後買的牌', 'command', {})
    p.deck.discard_pile = [bought1, bought2]
    g.turn_log['purchased_cards_this_turn'] = [bought1, bought2]

    first = g.use_pending_topdeck_right()
    assert first.get('pending_choice') is True
    offered = names(g.pending_choice['cards'])
    g.resolve_pending_choice(p.id, offered.index('先買的牌'))
    assert g.turn_log['pending_topdeck_uses'] == 1
    assert names(p.deck.draw_pile)[-1] == '先買的牌'

    second = g.use_pending_topdeck_right()
    assert second.get('success') and not second.get('pending_choice')
    assert g.turn_log['pending_topdeck_uses'] == 0
    assert names(p.deck.draw_pile)[-1] == '後買的牌'


def test_end_turn_auto_drains_unused_topdeck_right_with_two_purchases_before_refill():
    g = make_game()
    p = g.current_player()
    bought1, bought2 = Card('先買的牌', 'command', {}), Card('後買的牌', 'command', {})
    p.hand = [Card('Filler', 'command', {})]
    p.deck.draw_pile = [Card(f'Bottom{i}', 'command', {}) for i in range(1, 8)]
    p.deck.discard_pile = [bought1, bought2]
    g.turn_log['purchased_cards_this_turn'] = [bought1, bought2]
    g.turn_log['pending_topdeck_uses'] = 1
    g.turn_phase = TurnPhase.END

    result = g.advance_turn_phase()

    assert result.get('pending_choice') is True
    assert g.pending_choice['choice_key'] == 'topdeck_purchased_choice'
    offered = names(g.pending_choice['cards'])
    assert sorted(offered) == ['先買的牌', '後買的牌']

    resolved = g.resolve_pending_choice(p.id, offered.index('先買的牌'))

    assert resolved.get('success'), resolved
    # 現行回合模型（action-first）：回合結束後直接輪到下一位玩家的 ACTION，沒有 EVENT 階段。
    assert g.turn_phase == TurnPhase.ACTION
    assert g.current_player().name == 'P2'
    assert '先買的牌' in names(p.hand)
    assert '後買的牌' in names(p.deck.discard_pile)


def test_end_turn_drops_pending_topdeck_right_with_no_candidates_without_blocking_turn():
    g = make_game()
    p = g.current_player()
    p.hand = [Card('Filler', 'command', {})]
    p.deck.draw_pile = [Card(f'Bottom{i}', 'command', {}) for i in range(1, 8)]
    p.deck.discard_pile = []
    g.turn_log['purchased_cards_this_turn'] = []
    g.turn_log['pending_topdeck_uses'] = 1
    g.turn_phase = TurnPhase.END

    result = g.advance_turn_phase()

    assert not result.get('pending_choice')
    assert g.turn_phase == TurnPhase.ACTION
    assert g.current_player().name == 'P2'
    assert any('沒有可頂的牌，作廢' in line for line in g.action_log)



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
    # 2026-08-09 改用真實購買區卡牌（乘勝追擊，購買費用 2=偶數）而非亂編名稱＋任意資源
    # 字典：能力猜的是「購買費用」，不是印刷資源，用假卡名只會巧合湊出偶數、掩蓋不了
    # `_top_card_cost_total` 曾經優先看資源、購買費用查詢分支形同 dead code 的問題。
    g = make_game()
    p = g.current_player()
    # 立場試探現屬自由派（liberals）；舊測試用的 'fujian' 陣營 id 已不存在。
    p.faction_id = 'liberals'
    p.hand = []
    p.deck.draw_pile = [Card('Bottom', 'command', {}), card(g, '乘勝追擊')]

    result = g._activated_faction_action(p, '立場試探')

    assert result.get('success'), result
    assert names(p.hand) == []
    assert names(p.deck.discard_pile) == ['乘勝追擊']
    assert g.turn_log.get('faction_action_used') is True



def test_liberals_stance_probe_treats_starter_donor_as_even_cost_and_discards_it():
    # 2026-08-09 使用者 playtest 回報並更正：立場試探／賭徒耳語／民族祭儀猜的是牌庫頂牌
    # 的「購買費用」，不是印刷資源；樂捐者是起始牌，從未在購買區出現，真正購買費用是 0
    # （偶數）。舊實作優先讀 card.resources（樂捐者印 1 資金）誤判成奇數，這支測試先前
    # 名稱與斷言把這個錯誤行為當成正確答案寫死，現在改成驗證正確結果：偶數費用應該被
    # 放入棄牌堆，不是加入手牌。
    g = make_game()
    p = g.current_player()
    # 立場試探現屬自由派（liberals）；舊測試用的 'fujian' 陣營 id 已不存在。
    p.faction_id = 'liberals'
    p.hand = [Card('Existing', 'command', {})]
    p.deck.draw_pile = [Card('Bottom', 'command', {}), Card('樂捐者', 'money', {'money': 1})]
    p.deck.discard_pile = []

    result = g._activated_faction_action(p, '立場試探')

    assert result.get('success'), result
    assert names(p.hand) == ['Existing']
    assert names(p.deck.discard_pile) == ['樂捐者']
    assert g.action_log[-1] == '[Turn 1] P1 triggered 立場試探 and discarded 樂捐者'



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



def test_industry_infiltration_cancels_a_no_money_cost_card_but_gets_no_bonus_draw():
    """2026-08-05 修正：產業滲透能不能取消一張牌是無條件的（卡面「取消1張對方所打出行動卡
    之能力」沒有費用限制）；「若被取消的牌購買費用有資金，抽1張牌」只影響取消後的 bonus
    抽牌，不影響能不能取消。凝聚共識購買費用是宣傳5、資金0——產業滲透一樣能成功取消它
    （p1 的抽3棄2效果完全不執行），只是取消後沒有 bonus 抽牌（p2 手牌沒有多抽任何牌）。
    這支測試原本斷言「產業滲透無法取消、p1 的牌正常生效」，那是舊版 `_reaction_card_
    cancel_predicate` 誤把 bonus 抽牌的費用條件當成取消資格本身的 bug；已改寫為斷言
    正確行為。"""
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '凝聚共識')]
    p1.deck.draw_pile = [Card('Bottom', 'command', {}), Card('WouldHaveDrawn', 'command', {})]
    p2.hand = [card(g, '產業滲透')]
    p2.deck.draw_pile = [Card('ReactionDraw', 'command', {})]

    result = g.play_card(0, mode='action', reaction={'player_id': p2.id, 'card_index': 0})

    assert result.get('success'), result
    # 產業滲透成功取消凝聚共識：p1 的抽3棄2效果完全不執行。
    assert names(p1.hand) == []
    assert names(p1.deck.draw_pile) == ['Bottom', 'WouldHaveDrawn']
    assert names(p1.deck.discard_pile) == ['凝聚共識']
    # 產業滲透本身被消耗，但因為被取消的牌沒有資金費用，沒有 bonus 抽牌。
    assert 'ReactionDraw' not in names(p2.hand)
    assert names(p2.deck.discard_pile) == ['產業滲透']
    assert g.turn_log.get('canceled_money_cost_card') is False


def test_industry_infiltration_is_offered_as_a_candidate_for_propaganda_only_static_card():
    """使用者原始回報：打出宣傳家（常設購買區靜態卡，購買費用只有宣傳3、資金0）時，
    產業滲透完全不會被列為候選反應卡。直接重現：對手手上只有產業滲透，打出宣傳家後
    應該正確跳出取消詢問。"""
    g = make_game()
    actor, reactor = g.players
    # 紅軍起始根據地只有北京這個選項，明確指定以避免依賴 make_game() 的預設值——
    # 宣傳家有建立組織效果，_card_action_legality() 現在會先檢查合法城鎮，若這裡
    # 依賴預設狀態、剛好沒有起始據點，會在測到反應視窗之前就先被擋下來。
    actor.organizations = {'北京': 1}
    actor.hand = [card(g, '宣傳家')]
    reactor.hand = [card(g, '產業滲透')]

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert g.pending_choice['played_card_name'] == '宣傳家'
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['產業滲透']


def test_red_army_aid_now_prompts_cancel_reaction_and_cancel_prevents_draw():
    """2026-08-05 使用者回報：打出紅軍奧援時，對手的爆料黑幕/產業滲透/情報網完全不會
    自動跳出取消詢問——紅軍奧援有自己一套獨立於一般奧援卡的結算邏輯
    （_resolve_red_support_target_choice），過去整段在 play_card() 裡直接執行完畢並
    return，從未檢查過反應候選，跟東洋奧援等一般奧援卡在 9e2c6e9 修好之前的情況一樣。
    這裡重現紅軍自己打出紅軍奧援、對手用爆料黑幕取消：抽牌效果完全不執行，紅軍奧援
    直接進紅軍自己的棄牌堆（紅軍自己打出，不是「非紅軍借用」情境，不觸發歸還邏輯）。"""
    g = make_game()
    red, other = g.players
    red.faction_id = 'red_army'
    other.faction_id = 'liberals'
    red.hand = [g._make_support_card('紅軍奧援')]
    red.deck.draw_pile = [Card('ShouldNotDraw', 'command', {})]
    other.hand = [card(g, '爆料黑幕')]

    result = g.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert g.pending_choice['player_id'] == other.id
    assert g.pending_choice['played_card_name'] == '紅軍奧援'
    assert [entry['name'] for entry in g.pending_choice['cards']] == ['爆料黑幕']

    canceled = g.resolve_pending_choice(other.id, 1)

    assert canceled.get('success'), canceled
    assert canceled.get('canceled') is True, canceled
    assert names(red.hand) == [], '取消後不應抽牌'
    assert names(red.deck.draw_pile) == ['ShouldNotDraw']
    assert names(red.deck.discard_pile) == ['紅軍奧援']
    assert '爆料黑幕' not in names(other.hand)


def test_red_army_aid_cancel_reaction_declined_lets_the_draw_and_pass_resolve():
    """對手不取消時，紅軍奧援照常結算（抽1張牌＋依規則歸還到正確棄牌堆），沒有被延後
    機制吃掉效果。此情境是非紅軍玩家（借用/取得後）打出紅軍奧援，結算後應歸還紅軍
    棄牌堆——確認延後結算不影響既有的「借用牌歸位」規則。"""
    g = make_game()
    p1, red = g.players
    p1.faction_id = 'liberals'
    red.faction_id = 'red_army'
    g.current_player_index = 0
    p1.hand = [g._make_support_card('紅軍奧援')]
    p1.deck.draw_pile = [Card('ShouldDraw', 'command', {})]
    red.hand = [card(g, '爆料黑幕')]

    result = g.play_card(0, mode='action')
    assert g.pending_choice['type'] == 'reaction_choice', g.pending_choice

    skipped = g.resolve_pending_choice(red.id, 0)

    assert skipped.get('success'), skipped
    assert names(p1.hand) == ['ShouldDraw']
    assert names(red.deck.discard_pile) == ['紅軍奧援']
    assert '爆料黑幕' in names(red.hand), '不取消時反應卡應保留在手'


def test_red_army_aid_cancel_reaction_still_returns_borrowed_card_to_red_discard():
    """非紅軍玩家打出紅軍奧援被取消時，紙牌歸位規則不變——即使效果被取消，紅軍奧援本身
    仍要回到紅軍棄牌堆（既有「借用牌歸位」規則），不是留在打出者自己的棄牌堆。"""
    g = make_game()
    p1, red = g.players
    p1.faction_id = 'liberals'
    red.faction_id = 'red_army'
    g.current_player_index = 0
    p1.hand = [g._make_support_card('紅軍奧援')]
    p1.deck.draw_pile = [Card('ShouldNotDraw', 'command', {})]
    red.hand = [card(g, '爆料黑幕')]

    g.play_card(0, mode='action')
    canceled = g.resolve_pending_choice(red.id, 1)

    assert canceled.get('canceled') is True, canceled
    assert names(p1.hand) == [], '取消後不應抽牌'
    assert names(p1.deck.discard_pile) == [], '紅軍奧援不留在打出者自己的棄牌堆'
    assert '紅軍奧援' in names(red.deck.discard_pile), '取消後仍應歸還紅軍棄牌堆'


def test_reactively_played_reaction_card_counts_toward_its_own_cost_based_event_trigger():
    """2026-08-06 使用者回報：反應性地打出爆料黑幕（或產業滲透/情報網）取消對手的牌時，
    完全不會計入「打出購買費用有資金/宣傳的卡牌」這類事件任務進度（例如『重大災難』：
    trigger `play_card_with_propaganda`）——根因是這個追蹤只存在於 play_card() 自己的
    主動出牌流程裡，反應結算路徑（_build_reaction_context／_resolve_reaction_choice）
    從未呼叫過。爆料黑幕印刷購買費用是資金1＋宣傳4，兩者都>0，反應性地打出它本身就該
    算一次「打出購買費用有資金/有宣傳的牌」，不管它有沒有真的成功取消對方的牌。這裡刻意
    讓被取消的牌（乘勝追擊，資金2、宣傳0）本身完全不含宣傳費用，確保進度只可能來自
    爆料黑幕這次反應性出牌，不是被取消的牌自己的費用。"""
    g = make_game()
    actor, reactor = g.players
    actor.faction_id = 'taiwan_green'
    reactor.faction_id = 'liberals'
    pin_active_mission_event(g, '重大災難')
    actor.hand = [card(g, '乘勝追擊')]
    reactor.hand = [card(g, '爆料黑幕')]

    result = g.play_card(0, mode='action')
    assert result.get('pending_choice') is True, result

    canceled = g.resolve_pending_choice(reactor.id, 1)

    assert canceled.get('success'), canceled
    assert g.event_progress['succeeded'] is True
    assert g.event_progress['count'] >= 1


def test_reactively_played_reaction_card_counting_is_unaffected_by_being_counter_canceled():
    """反應卡本身被算入「打出購買費用有…的牌」的時機是「花掉這張卡去反應」那個當下，
    跟它後續有沒有被反制、真正的取消效果有沒有生效無關——比照 play_card() 既有的「出牌
    本身就計入，之後被取消也不會撤銷」語意。這裡讓 A 用爆料黑幕（宣傳4）取消 B 的牌，
    A 自己的爆料黑幕又被 C 用另一張爆料黑幕反制（B 的原始效果最終翻回生效），確認 A 的
    爆料黑幕仍然計入宣傳費用觸發的任務進度。"""
    g = Game([('p1', 'P1'), ('p2', 'P2'), ('p3', 'P3')])
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.pending_base_choices = {}
    pin_noop_event(g)
    g.players[0].faction_id = 'red_army'
    actor, b, c = g.players
    actor.faction_id = 'taiwan_green'
    b.faction_id = 'liberals'
    c.faction_id = 'hong_kong'
    pin_active_mission_event(g, '重大災難')
    actor.hand = [card(g, '乘勝追擊')]
    b.hand = [card(g, '爆料黑幕')]
    c.hand = [card(g, '爆料黑幕')]

    result = g.play_card(0, mode='action')
    assert result.get('pending_choice') is True, result
    step1 = g.resolve_pending_choice(b.id, 1)  # B 用爆料黑幕取消 A 的乘勝追擊
    assert step1.get('opened_counter_layer') is True, step1
    step2 = g.resolve_pending_choice(c.id, 1)  # C 用爆料黑幕反制 B 的爆料黑幕
    assert step2.get('success'), step2
    assert g.pending_choice is None

    assert g.event_progress['succeeded'] is True


def test_canceled_red_army_action_still_counts_as_used_this_turn():
    """2026-08-06 使用者回報：用產業滲透/爆料黑幕取消紅軍能力後，該次能力額度完全沒有
    被標記為已使用——紅軍可以在同一回合再試一次，等於白白浪費對手一張反應卡也擋不住。
    這裡重現：紅軍發動統戰部被產業滲透取消，確認 `red_army_action_count` 仍然遞增，
    同一回合再次嘗試任何紅軍陣營行動都會被「本回合已達上限」擋下。"""
    g = make_game()
    red, other = g.players
    red.faction_id = 'red_army'
    other.faction_id = 'liberals'
    other.hand = [card(g, '產業滲透')]

    before_count = g.turn_log.get('red_army_action_count', 0)
    result = g._activated_faction_action(red, '統戰部')
    assert result.get('pending_choice') is True, result

    canceled = g.resolve_pending_choice(other.id, 1)
    assert canceled.get('canceled') is True, canceled
    assert g.turn_log.get('red_army_action_count', 0) == before_count + 1

    retry = g._activated_faction_action(red, '統戰部')
    assert retry.get('error') == 'Red Army faction action limit reached this turn', retry


def test_canceled_targeted_red_army_action_marks_that_target_as_used():
    """政工部/國安部是「每回合對同一目標各一次」的額度——取消後這個目標專屬的標記也
    要正確設定，不能讓紅軍對同一目標重複騷擾對手的反應卡。"""
    g = make_game()
    red, other = g.players
    red.faction_id = 'red_army'
    other.faction_id = 'liberals'
    other.hand = [card(g, '爆料黑幕')]

    result = g._activated_faction_action(red, '政工部', target_player_id=other.id)
    assert result.get('pending_choice') is True, result

    canceled = g.resolve_pending_choice(other.id, 1)
    assert canceled.get('canceled') is True, canceled
    assert g.turn_log.get('red_army_targeted_actions', {}).get('政工部:' + other.id) is True


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



def test_build_action_cards_are_unusable_when_no_town_can_receive_an_organization():
    build_cards = ['宣傳家', '思想家', '組織經驗丙', '組織經驗乙', '組織經驗甲']
    for card_name in build_cards:
        g = make_game()
        p = g.current_player()
        p.hand = [card(g, card_name)]
        p.organizations = {'北京': 1}
        p.moves_left = 0
        g.event_modifiers = [{'type': 'restrict_build', 'remaining_turns': 1}]
        hand_before = list(p.hand)
        discard_before = list(p.deck.discard_pile)

        result = g.play_card(0, mode='action')

        assert result == {
            'error': '目前沒有城鎮可以建立組織。',
            'no_legal_build_town': True,
            'card_name': card_name,
        }
        assert p.hand == hand_before
        assert p.deck.discard_pile == discard_before
        assert p.moves_left == 0
        assert g.pending_choice is None


def test_state_projects_no_legal_build_reason_for_each_build_card_only():
    g = make_game()
    p = g.current_player()
    p.hand = [
        card(g, '宣傳家'),
        card(g, '思想家'),
        card(g, '組織經驗丙'),
        card(g, '資助者'),
    ]
    g.event_modifiers = [{'type': 'restrict_build', 'remaining_turns': 1}]

    legality = g.state(p.id)['players'][0]['hand_action_legality']

    assert legality[:3] == [
        {'playable': False, 'reason': '目前沒有城鎮可以建立組織。', 'no_legal_build_town': True},
        {'playable': False, 'reason': '目前沒有城鎮可以建立組織。', 'no_legal_build_town': True},
        {'playable': False, 'reason': '目前沒有城鎮可以建立組織。', 'no_legal_build_town': True},
    ]
    assert legality[3] == {'playable': True}


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
    assert g.turn_phase == TurnPhase.ACTION
    assert g.current_player() is not actor



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
    """Drive one player's whole action phase to the next player's ACTION via the real
    turn-phase state machine (not manual field pokes). A round wrap draws a real random
    event, which can itself inject an unrelated pending_choice (e.g. an interactive event
    prompt) before we get a chance to look — re-pin the no-op event and clear it
    immediately after, rather than asserting pending_choice is None first."""
    assert g.turn_phase == TurnPhase.ACTION
    assert g.advance_turn_phase().get('success')
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


def pin_active_mission_event(g, event_name):
    g.current_event = dict(g._event_by_name(event_name))
    trigger = g.current_event.get('trigger') or {}
    required = int(trigger.get('count', 0) or 0)
    g.event_progress = {'count': 0, 'required': required, 'succeeded': False, 'settled': False, 'status': 'active'}
    g.event_modifiers = []
    g.pending_choice = None
    return g


def test_beijing_power_struggle_progresses_on_ordinary_draw_effect_card():
    """2026-08-03 使用者playtest回報：事件卡『北京政爭』（trigger: {"type": "draw", "count": 1}）
    用網羅人才選到樹立信心，應該算任務成功。稽核發現根因比原本想的更大：`effect_engine.py`
    的 `_draw()`（一般行動卡如樹立信心／領導的 draw 效果都走這裡）完全沒呼叫
    `_track_event_progress`，只有 `game.py:_draw_player_cards()`（紅軍奧援／各奧援卡／時代
    效果）那條路徑有追蹤——不管直接打出樹立信心還是透過網羅人才拿到它再打出，都不會讓
    『北京政爭』推進，網羅人才本身不是唯一漏掉的途徑。"""
    g = make_game()
    actor = g.current_player()
    actor.faction_id = 'taiwan_green'
    pin_active_mission_event(g, '北京政爭')
    actor.hand = [card(g, '樹立信心')]
    actor.resources = {'money': 10, 'propaganda': 10}

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.event_progress['succeeded'] is True
    assert g.event_progress['status'] == 'success_pending'


def test_beijing_power_struggle_progresses_on_shared_draw_effect_card():
    """同上一項，換成 `shared_draw` 效果型別（例如『合作談判』），確認兩位玩家各自的抽牌
    也都會計入事件任務進度，不是只有單純 `draw` 型別才被追蹤到。"""
    g = make_game()
    actor, other = g.players
    actor.faction_id = 'taiwan_green'
    other.faction_id = 'liberals'
    pin_active_mission_event(g, '北京政爭')
    actor.hand = [card(g, '合作談判')]
    actor.resources = {'money': 10, 'propaganda': 10}

    result = g.play_card(0, mode='action', target_player_id=other.id)

    assert result.get('success'), result
    assert g.event_progress['succeeded'] is True


def test_beijing_power_struggle_ignores_red_army_draws():
    """確認這次修法沒有連帶放寬『非紅軍』的既有限制——`_event_trigger_actor_allowed()` 仍然
    排除紅軍，紅軍玩家自己的抽牌不應該讓『北京政爭』被判定成功。"""
    g = make_game()
    actor = g.current_player()
    actor.faction_id = 'red_army'
    pin_active_mission_event(g, '北京政爭')
    actor.hand = [card(g, '樹立信心')]
    actor.resources = {'money': 10, 'propaganda': 10}

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.event_progress['succeeded'] is False
    assert g.event_progress['count'] == 0


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
    playtest（`scripts/validate/validate_wall_crossing_movement.py` 的 `case_reported_dongsha_
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


def test_npc_progresses_when_hong_kong_safe_house_triggers_on_inner_build():
    """安全屋是香港目前根據地提供的被動陣營能力；牆內建立成功即算觸發能力。"""
    g = make_game()
    actor = g.current_player()
    actor.faction_id = 'hong_kong'
    actor.base = '香港城'
    pin_active_mission_event(g, '全國人大召開')

    assert g._player_has_ability(actor, '安全屋') is True
    assert '南寧' in set(g._towns_for_region_alias('china'))
    g._record_action_build(actor, '南寧')

    assert g.event_progress['succeeded'] is True
    assert g.event_progress['status'] == 'success_pending'
    assert any('triggered 安全屋 while building in 南寧' in entry for entry in g.action_log)


def test_npc_does_not_count_safe_house_when_hong_kong_base_no_longer_has_it():
    """遷到倫敦後目前能力是國際線；牆內建立不能再冒算安全屋。"""
    g = make_game()
    actor = g.current_player()
    actor.faction_id = 'hong_kong'
    actor.base = '倫敦'
    pin_active_mission_event(g, '全國人大召開')

    assert g._player_has_ability(actor, '安全屋') is False
    g._record_action_build(actor, '南寧')

    assert g.event_progress['succeeded'] is False
    assert g.event_progress['count'] == 0


def test_npc_progresses_on_turn_end_inner_build_draw_ability():
    """2026-08-05 使用者playtest回報：事件卡『全國人大召開』（trigger:
    {"type": "use_faction_ability", "count": 1}）——臺灣綠線用東洋奧援在牆內建立組織，
    回合結束時觸發本土社團（牆內建組織→多抽1張），這個特殊能力發動本身就應該滿足
    『全國人大召開』的成功條件。稽核發現根因比單一事件更大：`use_faction_ability` 追蹤
    先前只掛在「玩家主動按下的陣營行動」（紅軍統戰部/政工部…以及非紅軍的立場試探/民族
    祭儀等），而「自動觸發型」的陣營能力——回合結束牆內建組織抽牌（本土社團/還我河山/
    還我河山/民國之心）與出牌後首張帶資金/宣傳費用的觸發（商貿組織/民族調和/星星之火/
    人同此心/基金會/共合會/展現實力）——發動時完全沒呼叫 `_track_event_progress`，
    所以任何靠 `use_faction_ability` 判定的事件都不會被這些能力推進。這裡走真正的
    `_end_turn()` 流程（本土社團就是在補牌後於 `_apply_turn_end_faction_abilities` 觸發），
    `built_towns` 依實際建造在牆內城鎮的結果填入，確認事件被判定成功、而不是失敗。"""
    g = make_game()
    actor = g.current_player()
    actor.faction_id = 'taiwan_green'
    pin_active_mission_event(g, '全國人大召開')
    # 本回合在牆內城鎮（南寧、廣州）建立組織——與東洋奧援建組織後 build_organization
    # 寫入 turn_log['built_towns'] 的結果一致。
    g.turn_log['built_towns'] = ['南寧', '廣州']

    g._end_turn()

    assert g.event_progress['succeeded'] is True
    assert g.event_progress['status'] == 'success_pending'


def test_npc_progresses_on_first_money_cost_trigger_ability_immediate_play():
    """涵蓋重複的「本回合首張帶資金/宣傳費用」觸發區塊之一：`play_card()` 直接出牌路徑
    （game.py 內以 `cost_has_money` 為守衛的那份）。聯邦派擁有商貿組織（首張帶資金費用的
    牌→多抽1張）；打出帶資金購買費用的牌讓商貿組織發動，同樣要計入『全國人大召開』。"""
    g = make_game()
    actor, other = g.players
    actor.faction_id = 'federalists'
    other.faction_id = 'liberals'
    other.hand = []  # 對手無手牌→不觸發取消反應詢問，直接走即時出牌區塊
    pin_active_mission_event(g, '全國人大召開')
    actor.hand = [card(g, '樹立信心')]  # 購買費用含資金
    actor.resources = {'money': 10, 'propaganda': 10}

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.turn_log.get('faction_first_money_triggered') is True
    assert g.event_progress['succeeded'] is True
    assert g.event_progress['status'] == 'success_pending'


def test_npc_progresses_on_first_money_cost_trigger_ability_deferred_reaction_resume():
    """涵蓋重複的「首張帶資金費用」觸發區塊的另一份：延後反應（deferred reaction）結算後
    的 `_resume_reaction_pending_action()` 路徑（以 `trigger_cost_has_money` 為守衛）。
    這份與即時出牌那份幾乎逐行重複，若日後只還原其中一份，這個測試會抓到。設定：聯邦派
    打出帶資金費用的牌時，對手手上握有『情報網』會跳出取消詢問→出牌延後；對手選擇不取消
    後，行動在 resume 路徑結算，商貿組織才發動，同樣要計入『全國人大召開』。"""
    g = make_game()
    actor, reactor = g.players
    actor.faction_id = 'federalists'
    reactor.faction_id = 'liberals'
    pin_active_mission_event(g, '全國人大召開')
    actor.hand = [card(g, '樹立信心')]  # 購買費用含資金
    actor.resources = {'money': 10, 'propaganda': 10}
    reactor.hand = [card(g, '情報網')]  # 握有取消卡→出牌會先跳出取消反應詢問

    result = g.play_card(0, mode='action')
    assert result.get('pending_choice') is True, result
    assert g.pending_choice['choice_key'] == 'cancel_other_player_action'
    # 尚未結算，商貿組織還沒發動，事件也還沒成功
    assert g.event_progress['succeeded'] is False

    skipped = g.resolve_pending_choice(reactor.id, 0)  # 選擇不取消→走 resume 路徑

    assert skipped.get('success'), skipped
    assert g.turn_log.get('faction_first_money_triggered') is True
    assert g.event_progress['succeeded'] is True
    assert g.event_progress['status'] == 'success_pending'


def test_npc_ignores_red_army_own_faction_ability():
    """確認這次修法沒有放寬『非紅軍』的既有限制——`_event_trigger_actor_allowed()` 仍排除
    紅軍。紅軍發動自己的陣營行動（統戰部）雖然也會呼叫 `_track_event_progress(
    'use_faction_ability')`，但因為行動者是紅軍，不應該讓『全國人大召開』被判定成功。"""
    g = make_game()
    actor, other = g.players
    actor.faction_id = 'red_army'
    other.faction_id = 'liberals'  # 需有非紅軍玩家，紅軍行動額度才 >0
    pin_active_mission_event(g, '全國人大召開')

    result = g._activated_faction_action(actor, '統戰部')

    assert result.get('success'), result
    assert g.event_progress['succeeded'] is False
    assert g.event_progress['count'] == 0


def _force_event_deck(g, event_name):
    """Force the event deck to always draw `event_name` (survives reshuffles)."""
    event = g._event_by_name(event_name)

    class _AlwaysDraw:
        def __init__(self):
            self.draw_pile = [dict(event)]
            self.discard_pile = []

        def draw(self):
            return dict(event)

    g.event_deck = _AlwaysDraw()


def test_shanghai_cooperation_org_at_round_wrap_does_not_deadlock_non_red_actor():
    """Playtest 回報（最高嚴重度）：第 11 回合抽到『上海合作組織』，非紅軍陣營完成回合後，
    雙方都卡住無法執行任何步驟。

    根因不在事件機制本身（紅軍目標事件的 auto_pending 會在紅軍回合經 _end_turn 自動套用），
    而在同輪 round-wrap 觸發的『藏國騷亂』紅軍壓制——一個互動時代效果：舊行為在 round-wrap
    當下（當前玩家是非紅軍起始玩家）就把 pending_choice 掛在紅軍身上，非紅軍當前玩家因此被
    這個別人的待選擇卡死（advance_turn_phase／play_card 皆被擋），紅軍又不是當前玩家，雙方卡死；
    抽到的『上海合作組織』只是被記成 auto_deferred 的表象。修法：互動對象非當前玩家的時代啟動
    延後到該對象自己的回合，非紅軍玩家不再被卡，紅軍在自己的回合處理壓制、事件隨後套用。
    """
    g = Game([('actor', 'dafdsaf'), ('red', 'RED')])
    g.game_phase = GamePhase.MAIN
    g.pending_base_choices = {}
    g.pending_choice = None
    # players[0] = non-red round-start faction (Tibet), players[1] = Red Army.
    g.players[0].faction_id = 'tibet'
    g.players[1].faction_id = 'red_army'
    tibet, red = g.players

    # Tibet holds 7 organizations inside the wall (also Tibet-region towns) so 藏國騷亂
    # qualifies at the round wrap, and Red Army can build near them.
    china_towns = g._towns_for_region_alias('china')
    tibet.organizations = {town: 1 for town in china_towns[:7]}
    tibet_region_towns = g._towns_for_region_alias('tibet_region')
    tibet.organizations[tibet_region_towns[0]] = 1
    red.hand = [Card('追隨者', 'propaganda', {'propaganda': 1}) for _ in range(3)]

    _force_event_deck(g, '上海合作組織')
    g.current_event = None
    g.event_progress = None

    # Drive the round wrap: Red Army (index 1) ends their turn, wrapping back to the
    # non-red round-start player (index 0).
    g.turn = 10
    g.current_player_index = 1
    g.round_start_player_index = 0
    g.turn_phase = TurnPhase.ACTION
    g._end_turn()

    # 紅軍回合結束後立即判定藏國騷亂。先保留紅軍席位完成自己的時代選擇，
    # 再交棒給非紅軍玩家；這樣不會把別人的 pending_choice 掛在 Tibet 身上。
    assert g.current_player() is red
    assert g.turn == 11
    assert g.pending_choice is not None
    assert g.pending_choice['choice_key'] == 'era_red_discard_to_build_near_target'
    assert g.pending_choice['player_id'] == red.id

    g.resolve_pending_choice(red.id, [0])
    while g.pending_choice is not None and g.pending_choice.get('choice_key', '').startswith('era_'):
        g.resolve_pending_choice(g.pending_choice['player_id'], 0)

    assert g.current_player() is tibet
    assert g.turn_phase == TurnPhase.ACTION
    assert g.pending_choice is None
    assert (g.event_progress or {}).get('status') == 'auto_pending'

    # Tibet 可正常完成回合。換到紅軍後，上海合作組織才套用，雙方皆不會卡死。
    assert g.advance_turn_phase() == {'success': True}
    assert g.current_player() is red
    while g.pending_choice is not None:
        g.resolve_pending_choice(g.pending_choice['player_id'], 0)
    assert (g.event_progress or {}).get('status') == 'auto'
    assert g.event_progress.get('settled') is True
    assert any('上海合作組織' in line and 'scoped_card_range' in line for line in g.action_log)


def _urumqi_round_wrap_game():
    """[non-red round-start player (index 0), Red Army LAST (index 1)] with 烏魯木齊七五事件
    active and the non-red player holding one inside-the-wall organization.

    Red Army goes last so its own turn happens AFTER the old (final-non-red) settlement
    point — the exact ordering the stale-snapshot bug needs. make_game() is not reused
    here because it seats Red Army first (index 0), where Red Army acts *before* the
    settlement point and the bug cannot manifest.
    """
    g = Game([('p1', 'P1'), ('p2', 'P2')])
    g.game_phase = GamePhase.MAIN
    g.pending_base_choices = {}
    g.pending_choice = None
    g.players[0].faction_id = 'tibet'
    g.players[1].faction_id = 'red_army'
    b, red = g.players
    inner = g._towns_for_region_alias('china')[0]
    b.organizations = {inner: 1}
    b.hand = [Card('追隨者', 'propaganda', {'propaganda': 1}) for _ in range(5)]
    red.hand = [Card('追隨者', 'propaganda', {'propaganda': 1}) for _ in range(3)]
    pin_active_mission_event(g, '烏魯木齊七五事件')
    g.turn = 5
    g.current_player_index = 0
    g.round_start_player_index = 0
    g.turn_phase = TurnPhase.ACTION
    return g, b, red, inner


def test_urumqi_state_trigger_settles_after_red_army_turn_not_before():
    """Playtest 回報：『烏魯木齊七五事件也是啊～～所有事件卡都應該要所有人都輪過該回合才結算』。
    根因：`烏魯木齊七五事件`（data/events_structured.v1.1.json，唯一使用 `trigger.type ==
    "end_turn_state"` 的事件）是「回合結束時活狀態檢查」，不是累積計數。舊碼在
    advance_turn_phase() 的 TurnPhase.END 於「最後一位非紅軍玩家」（紅軍回合之前）就結算，
    對 own_organization_in_scope 這種活狀態用了紅軍行動前的過期快照——紅軍緊接著的回合把牆內
    組織瓦解掉，任務卻已用舊快照判成功。修法：只有 end_turn_state 觸發改到真正的 round-wrap
    邊界（整輪含紅軍都行動完）結算，計數型觸發維持原點不動。這裡驗證：非紅軍玩家回合結束時
    事件『尚未結算』，等紅軍瓦解組織、整輪結束後才判定為失敗（discard_random 罰非紅軍持有者）。
    """
    g, b, red, inner = _urumqi_round_wrap_game()

    # Non-red player's turn ends. Under the old code the end_turn_state mission settled
    # HERE (before Red Army acted). Now it must stay unsettled, with the settlement target
    # already captured as the non-red owner.
    assert g.advance_turn_phase() == {'success': True}   # 結束行動階段 -> _end_turn -> Red Army seat
    assert g.current_player() is red
    assert not (g.event_progress or {}).get('settled')
    assert (g.event_progress or {}).get('settlement_target_player_id') == b.id

    # Red Army dissolves the inside-the-wall org on its own turn; then the round wraps.
    b.organizations = {}
    b_hand_before = len(b.hand)
    assert g.advance_turn_phase() == {'success': True}   # 結束行動階段 -> _end_turn wraps -> settle

    # Condition (own inside-wall org) no longer holds after Red Army's turn -> failure,
    # judged against the FINAL state of the round, not the stale pre-Red snapshot.
    assert any('烏魯木齊七五事件' in line and 'failure' in line for line in g.action_log)
    assert not any('烏魯木齊七五事件' in line and 'success' in line for line in g.action_log)
    assert len(b.hand) == b_hand_before - 1   # discard_random penalty hit the non-red owner
    assert b.organizations == {}              # no bogus success build occurred


def test_urumqi_state_trigger_succeeds_when_org_survives_full_round():
    """Counterpart to the failure case: when Red Army does NOT dissolve the inside-the-wall
    org, the same end_turn_state mission is judged a SUCCESS — but still only at the true
    round-wrap boundary (after Red Army), never at the earlier final-non-red point."""
    g, b, red, inner = _urumqi_round_wrap_game()

    assert g.advance_turn_phase() == {'success': True}   # 結束行動階段 -> Red Army seat
    assert g.current_player() is red
    assert not (g.event_progress or {}).get('settled')   # not judged before Red Army acts

    # Red Army leaves the org intact; round wraps with the condition still satisfied.
    assert g.advance_turn_phase() == {'success': True}   # 結束行動階段 -> wrap -> settle
    assert any('烏魯木齊七五事件' in line and 'success' in line for line in g.action_log)
    assert b.organizations.get(inner, 0) == 1            # owning org preserved through the round


def test_count_based_mission_still_settles_at_final_non_red_turn():
    """Guardrail for the 烏魯木齊 fix: it must move ONLY end_turn_state settlement. A
    count-based mission (北京政爭, trigger {"type": "draw"}) must still settle at the final
    non-red turn — i.e. right after the last non-red player's END, BEFORE Red Army's own
    turn — exactly as before. Same [non-red, Red-last] seating as the urumqi tests so the
    contrast is apples-to-apples: urumqi is unsettled at this point, this one is settled."""
    g = Game([('p1', 'P1'), ('p2', 'P2')])
    g.game_phase = GamePhase.MAIN
    g.pending_base_choices = {}
    g.pending_choice = None
    g.players[0].faction_id = 'tibet'
    g.players[1].faction_id = 'red_army'
    b, red = g.players
    b.hand = [Card('追隨者', 'propaganda', {'propaganda': 1}) for _ in range(5)]
    red.hand = [Card('追隨者', 'propaganda', {'propaganda': 1}) for _ in range(3)]
    pin_active_mission_event(g, '北京政爭')
    g.event_progress['count'] = 1
    g.event_progress['succeeded'] = True
    g.event_progress['status'] = 'success_pending'
    g.event_progress['last_actor_id'] = b.id
    g.turn = 5
    g.current_player_index = 0
    g.round_start_player_index = 0
    g.turn_phase = TurnPhase.ACTION

    assert g.advance_turn_phase() == {'success': True}   # 結束行動階段 -> _end_turn -> Red Army seat
    assert g.current_player() is red
    # Count-based trigger is settled BEFORE Red Army's turn, unchanged by the fix.
    assert (g.event_progress or {}).get('settled') is True
    assert (g.event_progress or {}).get('status') == 'success'
    assert any('北京政爭' in line and 'success resolved' in line for line in g.action_log)
