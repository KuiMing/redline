"""Pure event display/text-formatting helpers (label lookups + string
formatting only, no Game/player mutation).

`_track_event_progress`, `_apply_event_effect`, `_settle_current_event`,
`_start_event_phase`, and the rest of the event trigger/settlement
machinery stay in `game.py` — those mutate turn_log, pending_choice, and
player state, unlike everything here.
"""


def event_condition_text(trigger, event=None):
    if not trigger:
        return '無'
    labels = {
        'use_faction_ability': '使用或觸發陣營特殊能力',
        'play_card_with_money': '打出購買費用含資金的卡牌',
        'play_card_with_propaganda': '打出購買費用含宣傳的卡牌',
        'buy_card': '購買符合條件的卡牌',
        'end_turn_state': '回合結束時符合狀態',
        'build_organization': '建立組織',
        'move_organization': '進行組織遷移',
        'draw': '藉由卡牌效果或能力抽牌',
    }
    count = int(trigger.get('count', 1) or 1)
    scope = trigger.get('scope')
    scope_text = f'（{scope}）' if scope else ''
    detail = ''
    if trigger.get('type') == 'buy_card':
        criteria = []
        if trigger.get('min_cost') is not None:
            criteria.append(f"總費用 {trigger.get('min_cost')} 點以上")
        if trigger.get('card_names'):
            criteria.append('或'.join(trigger.get('card_names') or []))
        if criteria:
            detail = f"（{' / '.join(criteria)}）"
    if trigger.get('type') == 'end_turn_state' and trigger.get('condition') == 'own_organization_in_scope':
        detail = f"（己方至少 {count} 個組織）"
    return f"{labels.get(trigger.get('type'), trigger.get('type') or '未知條件')}{scope_text}{detail}至少 {count} 次"


def event_result_text(event, event_progress):
    if not event:
        return ''
    progress = dict(event_progress or {})
    status = progress.get('status') or 'active'
    if event.get('type') == 'mission':
        if status == 'success_pending':
            return '非紅軍任務條件已達成，等待全體玩家行動結束後結算'
        if status == 'success':
            return '非紅軍任務成功'
        if status == 'failure':
            return '非紅軍任務失敗，紅軍效果生效'
        return '非紅軍任務進行中'
    if status == 'auto':
        return '紅軍事件效果已自動套用'
    if status == 'auto_pending':
        target_name = progress.get('auto_target_player_name') or '紅軍'
        return f'等待 {target_name} 回合發動紅軍事件效果'
    if status == 'idle':
        return '本次事件無效果'
    return ''


def event_effect_actor_text(effect, default_actor=None):
    actor = effect.get('player_faction') or effect.get('target_faction') or effect.get('target_camp') or default_actor
    labels = {
        'red_army': '紅軍',
        'anti_red': '反共陣營',
        'non_red': '非紅軍玩家',
        'rebel': '反共陣營',
        'taiwan': '台灣',
        'hong_kong': '香港',
        'tibet': '西藏',
        'uyghur': '維吾爾',
    }
    if not actor:
        return ''
    return labels.get(actor, str(actor))


def event_region_text(region):
    labels = {
        'southeast_asia': '南洋',
        'middle_east': '天方',
        'outer_manchuria': '外滿洲',
        'china': '牆內',
        '牆內': '牆內',
    }
    return labels.get(region, region or '指定區域')


def event_effect_text(effect, default_actor=None):
    if not effect or effect.get('type') == 'none':
        return '無'
    t = effect.get('type')
    count = int(effect.get('count', effect.get('amount', 1)) or 1)
    card = effect.get('card')
    actor_text = event_effect_actor_text(effect, default_actor=default_actor)
    scope_text = f"（{effect.get('scope')}）" if effect.get('scope') else ''
    labels = {
        'draw': f'抽 {count} 張牌',
        'gain_card': f'獲得 {count} 張{card or "指定牌"}',
        'discard_self': f'選 {count} 張手牌棄掉',
        'discard_random': f'被隨機棄掉 {count} 張手牌',
        'red_dissolve': f'瓦解 {count} 個組織{scope_text}',
        'add_internal_conflict': f'獲得 {count} 張內鬥',
        'move': f'獲得 {count} 次組織遷移',
        'reduce_cost': f'本回合購牌費用降低 {effect.get("amount", 1)}',
        'restrict_build': '本回合建立組織受限',
        'ignore_distance': '本回合無視距離限制',
        'scoped_card_range': f'本回合{event_region_text(effect.get("target_region"))}目標距離增加為 {effect.get("range", 1)} 格',
        'build_organization': f'建立 {count} 個組織',
        'build_organization_in_region': f'在{event_region_text(effect.get("region"))}免費建立 {count} 個組織',
        'build_organization_near_own': f'在己方組織 {effect.get("max_steps", 1)} 格內建立 {count} 個組織',
        'topdeck_from_discard': f'從棄牌堆選 {count} 張置於牌庫頂',
        'trash_from_hand_or_discard': f'從手牌或棄牌堆移除 {count} 張牌',
    }
    text = labels.get(t, t or '未知效果')
    if actor_text:
        return f'{actor_text}：{text}'
    return text


def event_display_payload(event, event_progress):
    if not event:
        return None
    trigger = event.get('trigger') or {}
    success = event.get('success') or {}
    failure = event.get('failure') or {}
    effect = event.get('effect') or {}
    progress = dict(event_progress or {})
    return {
        'id': event.get('id'),
        'name': event.get('name'),
        'type': event.get('type'),
        'trigger': trigger,
        'success': success,
        'failure': failure,
        'effect': effect,
        'progress': progress,
        'status': progress.get('status') or 'active',
        'result_text': event_result_text(event, event_progress),
        'trigger_text': event_condition_text(trigger, event),
        'success_text': event_effect_text(success, default_actor='非紅軍'),
        'failure_text': event_effect_text(failure, default_actor='紅軍'),
        'effect_text': event_effect_text(effect),
    }
