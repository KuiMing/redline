class EffectEngine:
    """
    Centralized effect execution pipeline.
    Now implements core executable effect types.
    """

    def _draw(self, player, count, game=None, card_name=None):
        # 2026-08-04 使用者需求：抽牌類效果的紀錄要寫出實際抽到哪些牌，而不是只有一行
        # 「打出了 X」看不到抽了什麼。`game`/`card_name` 是選填——`shared_draw` 自己組合
        # 兩位玩家的合併訊息，因此故意不在這裡自動記錄，避免重複寫兩行。
        drawn = player.deck.draw(count)
        player.hand.extend(drawn)
        if game is not None and drawn:
            names = '、'.join(getattr(c, 'name', str(c)) for c in drawn)
            if card_name:
                game.log(f"{player.name} 因{card_name}抽到：{names}")
            else:
                game.log(f"{player.name} 抽到：{names}")
        return drawn

    def _starter_names(self):
        return {"追隨者", "樂捐者"}

    def execute(self, effect, player, game, context=None):
        etype = effect.get("type")

        # ✅ Draw cards
        if etype == "draw":
            count = effect.get("count", 1)
            self._draw(player, count, game=game, card_name=(context or {}).get('card_name'))
            return

        # ✅ Discard self
        if etype == "discard_self":
            count = effect.get("count", 1)
            if len(player.hand) < count:
                count = len(player.hand)
            if count <= 0:
                return None
            cards = list(player.hand)
            if hasattr(game, '_set_pending_multi_card_choice'):
                extra = {'source_name': context.get('card_name') if context else None}
                if context and context.get('card_name') == '凝聚共識':
                    extra['grant_propaganda_if_all_non_starter'] = 2
                game._set_pending_multi_card_choice(
                    player,
                    'discard_self',
                    cards,
                    f'從所有手牌中棄掉任{count}張牌。',
                    count=count,
                    **extra,
                )
                return {'pending_choice': True}
            else:
                for _ in range(min(count, len(player.hand))):
                    card = player.hand.pop()
                    player.deck.discard([card])
            return None

        # ✅ Gain resources
        if etype == "gain_resource":
            player.resources["money"] += effect.get("money", 0)
            player.resources["propaganda"] += effect.get("propaganda", 0)
            return

        # ✅ Force discard opponents
        if etype == "force_discard":
            count = effect.get("count", 1)
            context = context or {}
            target_id = context.get("target_player_id") or effect.get("target_player_id")
            source_name = context.get("card_name")
            targets = []
            if target_id:
                target = next((p for p in game.players if getattr(p, "id", None) == target_id), None)
                if target is not None and target != player:
                    targets = [target]
            if source_name in {"武裝者", "武裝小隊", "武裝集團"} and targets:
                target = targets[0]
                choice_count = min(int(count or 1), len(target.hand))
                if choice_count <= 0:
                    return
                extra = {
                    'source_name': source_name,
                    'initiator_player_id': getattr(player, 'id', None),
                    'initiator_player_name': getattr(player, 'name', '其他玩家'),
                    'target_player_name': getattr(target, 'name', '目標玩家'),
                }
                if context.get('era_followup_target_choice'):
                    extra['era_followup_target_choice'] = context.get('era_followup_target_choice')
                if source_name == "武裝集團":
                    extra['draw_on_success'] = 1
                prompt = f"{source_name}：從所有手牌中棄掉任{choice_count}張牌。"
                if choice_count == 1:
                    game._set_pending_card_choice(target, 'armed_target_discard', list(target.hand), prompt, **extra)
                else:
                    game._set_pending_multi_card_choice(target, 'armed_target_discard', list(target.hand), prompt, count=choice_count, **extra)
                game.log(f"{player.name} used {source_name} to ask {target.name} to choose {choice_count} discard(s)")
                return {'pending_choice': True}
            if not targets:
                label = source_name or 'force_discard'
                game.log(f"{label} had no explicit discard target; no cards were discarded")
                return {'no_target': True}
            discarded_any = False
            for other in targets:
                discarded_names = []
                for _ in range(min(count, len(other.hand))):
                    card = other.hand.pop()
                    other.deck.discard([card])
                    discarded_names.append(getattr(card, 'name', str(card)))
                    discarded_any = True
                if discarded_names:
                    label = source_name or 'force_discard'
                    game.log(f"{label} forced {other.name} to discard {'、'.join(discarded_names)}")
            if discarded_any:
                game.turn_log["successful_discard"] = True
            return

        # ✅ Gain from discard (simplified cost handling)
        if etype == "gain_from_discard":
            max_cost = effect.get("max_cost")
            candidates = list(player.deck.discard_pile)
            if max_cost is not None:
                filtered = []
                for card in candidates:
                    cost = game._card_purchase_cost(card) if hasattr(game, '_card_purchase_cost') else {}
                    total_cost = int(cost.get('money', 0) or 0) + int(cost.get('propaganda', 0) or 0)
                    if total_cost <= int(max_cost):
                        filtered.append(card)
                candidates = filtered
            if not candidates:
                return
            gainable = []
            for card in candidates:
                ok, err = game._can_player_gain_flag_card(player, card)
                if ok:
                    gainable.append(card)
                else:
                    game.log(f"{player.name} could not gain {getattr(card, 'name', str(card))}: {err}")
            if not gainable:
                return
            if hasattr(game, '_set_pending_card_choice'):
                game._set_pending_card_choice(
                    player,
                    'gain_from_discard',
                    gainable,
                    f"從己方棄牌堆任選1張費用{int(max_cost)}點以下的牌加入手牌。" if max_cost is not None else '從己方棄牌堆任選1張牌加入手牌。',
                    source_name='乘勝追擊',
                    max_cost=max_cost,
                )
            else:
                game.pending_choice = {
                    'type': 'card_choice',
                    'choice_key': 'gain_from_discard',
                    'player_id': player.id,
                    'cards': gainable,
                    'prompt': f"從己方棄牌堆任選1張費用{int(max_cost)}點以下的牌加入手牌。" if max_cost is not None else '從己方棄牌堆任選1張牌加入手牌。',
                    'source_name': '乘勝追擊',
                    'max_cost': max_cost,
                }
            game.log(f"{player.name} may gain 1 eligible card from discard")
            return

        # ✅ Gain any from discard
        if etype == "gain_any_from_discard":
            cards = list(player.deck.discard_pile)
            if not cards:
                return
            gainable = []
            for card in cards:
                ok, err = game._can_player_gain_flag_card(player, card)
                if ok:
                    gainable.append(card)
                else:
                    game.log(f"{player.name} could not gain {getattr(card, 'name', str(card))}: {err}")
            if not gainable:
                return
            if hasattr(game, '_set_pending_card_choice'):
                game._set_pending_card_choice(
                    player,
                    'gain_any_from_discard',
                    gainable,
                    '擴大戰果：從己方棄牌堆任選1張牌加入手牌。',
                    source_name='擴大戰果',
                )
            else:
                game.pending_choice = {
                    'type': 'card_choice',
                    'choice_key': 'gain_any_from_discard',
                    'player_id': player.id,
                    'cards': gainable,
                    'prompt': '擴大戰果：從己方棄牌堆任選1張牌加入手牌。',
                    'source_name': '擴大戰果',
                }
            game.log(f"{player.name} may gain 1 card from discard")
            return

        # ✅ Choose from purchase deck (used by 地下黨)
        if etype == "choose_from_purchase_deck":
            game._resolve_underground_party(player, count=effect.get("count", 3))
            return

        # ✅ Leak top deck (走漏風聲)
        if etype == "leak_top_deck":
            context = context or {}
            target_id = context.get("target_player_id") or effect.get("target_player_id")
            target = None
            if target_id:
                target = next((p for p in game.players if getattr(p, "id", None) == target_id), None)
            if target is None:
                target = next((p for p in game.players if p != player), None)
            if target is None:
                return

            discarded = target.deck.draw(1)
            if not discarded:
                game.log(f"{player.name} leaked {target.name}'s plan, but their deck was empty")
                return

            top_card = discarded[0]
            target.deck.discard([top_card])
            card_name = getattr(top_card, "name", str(top_card))
            cost = game._card_purchase_cost(top_card) if hasattr(game, "_card_purchase_cost") else {}
            total_cost = int(cost.get("money", 0) or 0) + int(cost.get("propaganda", 0) or 0)
            if total_cost >= 1:
                cards = game._take_internal_conflict_cards(1, reason='走漏風聲') if hasattr(game, '_take_internal_conflict_cards') else []
                if cards:
                    target.deck.discard(cards)
                    placed = '、'.join(getattr(c, 'name', str(c)) for c in cards)
                    game.log(f"{player.name} used 走漏風聲 on {target.name}: discarded {card_name} and moved {placed} from supply to discard")
                else:
                    game.log(f"{player.name} used 走漏風聲 on {target.name}: discarded {card_name}, but 內鬥 supply was empty")
            else:
                game.log(f"{player.name} used 走漏風聲 on {target.name}: discarded {card_name}")
            return

        # ✅ Peek deck (MVP: no UI return)
        if etype == "peek_deck":
            return

        # ✅ Choose any card from own deck (網羅人才)
        if etype == "choose_from_own_deck":
            cards = list(player.deck.draw_pile)
            card_zones = [
                {'zone': 'draw_pile', 'zone_label': '牌庫'}
                for _ in player.deck.draw_pile
            ]
            if effect.get('include_discard_for_faction') == player.faction_id:
                discard_cards = list(player.deck.discard_pile)
                cards.extend(discard_cards)
                card_zones.extend(
                    {'zone': 'discard_pile', 'zone_label': '棄牌堆'}
                    for _ in discard_cards
                )
            if not cards:
                return
            if hasattr(game, '_set_pending_card_choice'):
                game._set_pending_card_choice(
                    player,
                    'recruit_talent',
                    cards,
                    '網羅人才：從己方牌庫或棄牌堆任選1張加入手牌，而後將牌庫洗牌。' if effect.get('include_discard_for_faction') == player.faction_id else '網羅人才：從己方牌庫任選1張加入手牌，而後將牌庫洗牌。',
                    card_zones=card_zones,
                )
            else:
                game.pending_choice = {
                    'type': 'card_choice',
                    'choice_key': 'recruit_talent',
                    'player_id': player.id,
                    'cards': cards,
                    'card_zones': card_zones,
                    'prompt': '網羅人才：從己方牌庫或棄牌堆任選1張加入手牌，而後將牌庫洗牌。' if effect.get('include_discard_for_faction') == player.faction_id else '網羅人才：從己方牌庫任選1張加入手牌，而後將牌庫洗牌。'
                }
            game.log(f"{player.name} may recruit 1 card from deck/discard" if effect.get('include_discard_for_faction') == player.faction_id else f"{player.name} may recruit 1 card from deck")
            return

        # ✅ Temporarily use another player's top deck card (模仿戰術)
        # Card rule: 選擇1位玩家展示其牌庫頂牌，本回合您可以使用該牌。使用後放回擁有者的牌庫頂。
        if etype == "imitate_topdeck":
            context = context or {}
            target_id = context.get("target_player_id") or effect.get("target_player_id")
            if target_id:
                # A target was already chosen (resumed) — perform the imitate directly.
                return game._perform_imitate_topdeck(player, target_id)
            # No target yet: prompt the player to choose which player's top card to imitate.
            return game._prompt_imitate_topdeck_target(player)

        # ✅ Top deck to hand
        if etype == "topdeck_to_hand":
            drawn = player.deck.draw(1)
            if drawn:
                player.hand.extend(drawn)
            return

        # ✅ Optional trash (choose current card or one hand card)
        if etype == "optional_trash":
            context = context or {}
            current_card = context.get('current_card')
            source_name = context.get('card_name') if context else None
            removable = []
            if current_card is not None:
                removable.append({
                    'card': current_card,
                    'zone': 'current_card',
                    'zone_label': '剛打出的牌',
                    'removes_current_card': True,
                })
            if source_name == '誘導虛耗':
                # 卡面：「打出可移除本牌。若移除本牌，可選擇1位玩家…」——
                # 可移除對象僅限剛打出的誘導虛耗本身，不含其他手牌；並提供「不移除」選項
                removable.append({
                    'skip': True,
                    'name': '不移除',
                    'zone': 'skip',
                    'zone_label': '不移除本牌（結束效果）',
                })
            else:
                for card in list(player.hand):
                    removable.append({
                        'card': card,
                        'zone': 'hand',
                        'zone_label': '手牌',
                        'removes_current_card': False,
                    })
            if not removable:
                return
            if source_name in {'宣傳家', '思想家', '資助者', '資本家', '分神'} and current_card is not None:
                returned = game._return_removed_card_to_purchase_supply(current_card) if hasattr(game, '_return_removed_card_to_purchase_supply') else None
                context['removed_current_card'] = True
                if hasattr(game, 'log'):
                    game.log(f"{player.name} removed {source_name} and returned it to static purchase supply")
                return {'removed_current_card': True, 'removed_card': returned}
            if hasattr(game, '_set_pending_card_choice'):
                if source_name == '誘導虛耗':
                    prompt = '誘導虛耗：可移除剛打出的誘導虛耗（僅限本牌）；若移除，可選擇 1 位玩家棄掉 1 張手牌。'
                else:
                    prompt = f"{source_name or '此牌'}：你可以移除剛打出的這張牌，或移除 1 張手牌。"
                targets = [
                    {
                        'id': getattr(other, 'id', None),
                        'label': getattr(other, 'name', str(getattr(other, 'id', '目標玩家'))),
                    }
                    for other in getattr(game, 'players', [])
                    if (
                        other != player
                        and getattr(other, 'id', None) is not None
                        and (source_name != '誘導虛耗' or bool(getattr(other, 'hand', None)))
                    )
                ]
                if source_name == '誘導虛耗' and not targets:
                    game.log('誘導虛耗 had no player with hand cards to target; optional trash was skipped')
                    return {'no_target': True}
                followup_target_choice = None
                if source_name == '誘導虛耗':
                    followup_target_choice = {
                        'choice_key': 'bait_exhaustion_target',
                        'prompt': '誘導虛耗：請選擇 1 位玩家棄掉 1 張手牌。',
                        'targets': targets,
                        'source_name': source_name,
                    }
                game._set_pending_card_choice(
                    player,
                    'optional_trash',
                    removable,
                    prompt,
                    source_name=source_name or '此牌',
                    context=context,
                    followup_target_choice=followup_target_choice,
                )
                return {'pending_choice': True}
            return

        # ✅ Build via card effect: prompt the player to choose a legal build town.
        if etype == "build":
            context = context or {}
            source_name = context.get('card_name') or '建立組織卡'
            if hasattr(game, '_card_build_town_choices') and hasattr(game, '_set_pending_town_choice'):
                towns = game._card_build_town_choices(player, effect)
                if towns:
                    game._set_pending_town_choice(
                        player,
                        'card_build_organization',
                        towns,
                        f"{source_name}：選擇要建立組織的城鎮。",
                        source_name=source_name,
                        context={
                            **context,
                            'source_name': source_name,
                            'effect': dict(effect),
                        },
                    )
                    return {'pending_choice': True}
                game.log(f"{player.name} had no legal town to build via {source_name}")
                return
            candidate_towns = list(getattr(game, 'map', {}).get('towns', {}).keys())
            target = next((town for town in candidate_towns if game.can_develop_in_town(player, town)), None)
            if target:
                if hasattr(game, '_place_organization'):
                    game._place_organization(player, target)
                else:
                    player.organizations[target] = 1
                game.log(f"{player.name} built organization in {target} via card effect")
            return

        # ✅ Move via card effect (MVP: grant extra movement points)
        if etype == "move":
            count = effect.get("count", 1)
            player.moves_left += count
            return

        # ✅ Shared draw with one selected target (MVP default: first other player)
        if etype == "shared_draw":
            count = effect.get("count", 1)
            drawn_self = self._draw(player, count)
            context = context or {}
            target_id = context.get("target_player_id") or effect.get("target_player_id")
            target = None
            if target_id:
                target = next((p for p in game.players if getattr(p, "id", None) == target_id), None)
            if target is None:
                target = next((p for p in game.players if p != player), None)
            if target is not None:
                drawn_target = self._draw(target, count)
                if hasattr(game, 'log'):
                    source_name = context.get('card_name') or 'shared draw'
                    self_names = '、'.join(getattr(c, 'name', str(c)) for c in drawn_self)
                    target_names = '、'.join(getattr(c, 'name', str(c)) for c in drawn_target)
                    game.log(
                        f"{player.name} 與 {target.name} 因 {source_name} 各抽 {count} 張："
                        f"{player.name}抽到 {self_names}；{target.name}抽到 {target_names}"
                    )
            return

        # ✅ Choose one branch via pending choice (情報網)
        if etype == "choose_one":
            context = context or {}
            options = effect.get('options') or []
            if not options:
                return
            if hasattr(game, '_set_pending_option_choice'):
                game._set_pending_option_choice(
                    player,
                    'choose_one',
                    options,
                    '情報網：選擇一個效果執行。',
                    source_name=context.get('card_name') if context else None,
                    context=context,
                )
            else:
                selected = context.get('choice_index', effect.get('default_index', 0))
                if not isinstance(selected, int) or selected < 0 or selected >= len(options):
                    selected = 0
                for nested in options[selected].get('effect', []):
                    self.execute(nested, player, game, context=context)
            return

        # ✅ Move a card bought this turn from discard to deck top (行動預告/行動募資)
        if etype == "topdeck_purchased_this_turn":
            context = context or {}
            purchased = list(game.turn_log.get('purchased_cards_this_turn') or [])
            candidates = [card for card in purchased if card in player.deck.discard_pile]
            if not candidates:
                game.log(f"{player.name} had no card bought this turn to place on deck top")
                return
            if len(candidates) == 1:
                card = candidates[0]
                player.deck.discard_pile.remove(card)
                player.deck.draw_pile.append(card)
                game.log(f"{player.name} placed bought card {getattr(card, 'name', str(card))} on deck top")
                return
            # 本回合買了多張：卡面「將本回合購得的1張牌置於牌庫頂」由玩家選擇哪一張
            source_name = context.get('card_name') or '行動預告'
            if hasattr(game, '_set_pending_card_choice'):
                game._set_pending_card_choice(
                    player,
                    'topdeck_purchased_choice',
                    list(candidates),
                    f'{source_name}：選擇 1 張本回合購得的牌置於牌庫頂。',
                    source_name=source_name,
                    context={
                        'card_name': source_name,
                        'remaining_effects': list(context.get('remaining_effects') or []),
                        'end_turn_topdeck_flow': bool(context.get('end_turn_topdeck_flow')),
                    },
                )
                return {'pending_choice': True}
            card = candidates[-1]
            player.deck.discard_pile.remove(card)
            player.deck.draw_pile.append(card)
            game.log(f"{player.name} placed bought card {getattr(card, 'name', str(card))} on deck top")
            return

        # ✅ Temporarily use a face-up purchase-area card (企業人脈)
        if etype == "use_purchase_area_card":
            static_count = len(game._static_purchase_cards()) if hasattr(game, '_static_purchase_cards') else 0
            start = static_count if effect.get('prefer_random_market', True) else 0
            choices = []
            for idx in range(start, len(getattr(game, 'purchase_area', []) or [])):
                candidate = game.purchase_area[idx]
                if candidate:
                    choices.append({
                        'card': candidate,
                        'name': getattr(candidate, 'name', str(candidate)),
                        'zone': 'purchase_area',
                        'zone_label': f'購買區槽位 {idx - start + 1}',
                        'purchase_index': idx,
                    })
            if not choices:
                return
            if hasattr(game, '_set_pending_card_choice'):
                game._set_pending_card_choice(
                    player,
                    'use_purchase_area_card',
                    choices,
                    '企業人脈：選擇購買區正面朝上的 1 張牌，視同打出該牌。',
                    source_name='企業人脈',
                )
                return {'pending_choice': True}
            source_entry = choices[0]
            source = source_entry['card']
            source_index = source_entry['purchase_index']
            borrowed = game._copy_purchase_card(source)
            setattr(borrowed, '_return_to_purchase_area_index', source_index)
            player.hand.append(borrowed)
            game.log(f"{player.name} borrowed {getattr(borrowed, 'name', str(borrowed))} from purchase area")
            return

        # ✅ Reveal top deck and gain money by purchase cost threshold (企畫遊說)
        if etype == "reveal_topdeck_cost_gain":
            if not player.deck.draw_pile:
                player.deck._reshuffle()
            if not player.deck.draw_pile:
                return
            top = player.deck.draw_pile[-1]
            cost = game._card_purchase_cost(top) if hasattr(game, '_card_purchase_cost') else {}
            total = int(cost.get('money', 0) or 0) + int(cost.get('propaganda', 0) or 0)
            threshold = int(effect.get('threshold', 3) or 3)
            if total >= threshold:
                player.resources['money'] += int(effect.get('money_if_at_least', 4) or 4)
            else:
                player.resources['money'] += int(effect.get('money_otherwise', 2) or 2)
            game.log(f"{player.name} revealed {getattr(top, 'name', str(top))} for 企畫遊說")
            return

        # ✅ Conditional draw
        if etype == "conditional_draw":
            condition = effect.get("condition")
            should_draw = False
            ctx = context or {}
            if condition == "played_propaganda_card":
                # "其它" (an *other* card this turn) — use the pre-this-card snapshot so a
                # card whose own cost includes propaganda can't satisfy its own condition.
                should_draw = bool(ctx.get("prior_played_propaganda_card", game.turn_log.get("played_propaganda_card")))
            elif condition == "played_money_card":
                should_draw = bool(ctx.get("prior_played_money_card", game.turn_log.get("played_money_card")))
            elif condition == "successful_discard":
                should_draw = bool(game.turn_log.get("successful_discard"))
            elif condition == "canceled_propaganda_card":
                should_draw = bool(game.turn_log.get("canceled_propaganda_card"))
            elif condition == "canceled_money_cost_card":
                should_draw = bool(game.turn_log.get("canceled_money_cost_card"))
            if should_draw:
                self._draw(player, effect.get("count", 1), game=game, card_name=ctx.get('card_name'))
            return

        # ✅ Add internal conflict cards (MVP: add named disruption cards to discard pile)
        if etype == "add_internal_conflict":
            count = effect.get("count", 1)
            from server.cards import Card
            context = context or {}
            target_id = context.get("target_player_id") or effect.get("target_player_id")
            targets = []
            if target_id:
                target = next((p for p in game.players if getattr(p, "id", None) == target_id), None)
                if target is not None:
                    targets = [target]
            elif effect.get("target_scope") == "others" or (context.get("card_name") == "情報網" and context.get("choice_index") == 0):
                # 離間／情報網A：「在至多3位玩家棄牌堆各放入1張內鬥」——對象是其他玩家，
                # 絕不包含施放者自己（P1 回報：紅軍離間把內鬥放進自己牌堆的 bug）
                max_targets = int(effect.get("max_targets", 3) or 3)
                targets = [other for other in game.players if other != player][:max_targets]
            if not targets:
                game.log(f"{player.name} 的 add_internal_conflict 沒有合法目標，未放置內鬥")
                return
            for target in targets:
                # 依 static supply 原則從供應取牌（內鬥耗盡時依 C1 裁決以雙倍分神替代）
                if hasattr(game, '_take_internal_conflict_cards'):
                    cards = game._take_internal_conflict_cards(count, reason=context.get('card_name') or 'add_internal_conflict')
                else:
                    cards = [Card("內鬥", "disruption", {}) for _ in range(count)]
                if cards:
                    target.deck.discard(cards)
                    game.log(f"{target.name} gained {len(cards)} card(s): {'、'.join(getattr(c, 'name', str(c)) for c in cards)}")
            return

        # ✅ Cancel card (MVP reaction hook: flags are prepared by Game.play_card; draw handled here)
        if etype == "cancel_card":
            context = context or {}
            reaction_player = context.get("reacting_player", player)
            canceled_name = context.get("canceled_card_name") or "unknown card"
            game.log(f"{reaction_player.name} canceled {canceled_name}")
            return

        # ✅ Conditional bonus
        if etype == "conditional_bonus":
            condition = effect.get("condition")
            ok = False
            if condition == "non_starter_discard":
                ok = bool(game.turn_log.get("non_starter_discard"))
            if ok:
                player.resources["money"] += effect.get("money", 0)
                player.resources["propaganda"] += effect.get("propaganda", 0)
            return

        # ✅ Dissolve (MVP: remove one in-range opponent org; optional self sacrifice)
        if etype == "dissolve":
            context = context or {}
            target_id = context.get("target_player_id") or effect.get("target_player_id")
            target = None
            if target_id:
                target = next((p for p in game.players if getattr(p, "id", None) == target_id), None)
            if target is None or target == player:
                label = context.get('card_name') or 'dissolve'
                game.log(f"{label} had no explicit dissolve target; no organization was dissolved")
                return {'no_target': True}
            opponents = [target]
            range_limit = int(effect.get("range", 1) or 1)
            if effect.get("requires_self_sacrifice"):
                owned = [
                    town for town, count in player.organizations.items()
                    if count > 0 and town != getattr(player, 'base', None)
                ]
                valid_sacrifice = None
                target_town = None
                for town in owned:
                    reachable = game._towns_within_steps([town], max_steps=range_limit)
                    for other in opponents:
                        for otown, count in other.organizations.items():
                            if (
                                count > 0
                                and otown in reachable
                                and game._can_dissolve_base_target(other, otown)[0]
                            ):
                                valid_sacrifice = town
                                target_town = otown
                                break
                        if target_town:
                            break
                    if target_town:
                        break
                if valid_sacrifice is None:
                    return {'no_target': True}
                player.organizations[valid_sacrifice] -= 1
                if player.organizations[valid_sacrifice] <= 0:
                    del player.organizations[valid_sacrifice]
                result = game.dissolve_organization(player, target, target_town, source="card")
                return result
            for other in opponents:
                if other is None:
                    continue
                town = game._find_target_town_within_steps_of_player(player, other, max_steps=range_limit)
                if town:
                    result = game.dissolve_organization(player, other, town, source="card")
                    if result.get("success"):
                        break
            return

        # ✅ Refresh purchase area (refresh random market only)
        if etype == "refresh_purchase_area":
            static_count = len(game._static_purchase_cards()) if hasattr(game, '_static_purchase_cards') else 0
            existing = list(getattr(game, 'purchase_area', []) or [])
            random_market = existing[static_count:]
            for card in random_market:
                returned = game._return_removed_card_to_purchase_supply(card)
                if returned is None:
                    game._remove_card_from_game(card)
            refreshed = game._draw_purchase_cards(len(random_market))
            game.purchase_area = existing[:static_count] + refreshed
            return

        # ✅ Trash from hand or discard
        if etype == "trash_from_hand_or_discard":
            count = effect.get("count", 1)
            candidates = []
            for idx, card in enumerate(list(player.hand)):
                candidates.append({
                    'card': card,
                    'zone': 'hand',
                    'zone_label': '手牌',
                    'zone_index': idx,
                })
            for idx, card in enumerate(list(player.deck.discard_pile)):
                candidates.append({
                    'card': card,
                    'zone': 'discard',
                    'zone_label': '棄牌堆',
                    'zone_index': idx,
                })
            if not candidates:
                return None
            prompt = f'請從己方手牌或棄牌堆中移除任{count}張牌。'
            if hasattr(game, '_set_pending_card_choice'):
                if int(count or 1) <= 1:
                    game._set_pending_card_choice(
                        player,
                        'trash_from_hand_or_discard',
                        candidates,
                        prompt,
                        count=1,
                        source_name=context.get('card_name') if context else None,
                    )
                    return {'pending_choice': True}
                if hasattr(game, '_set_pending_multi_card_choice'):
                    game._set_pending_multi_card_choice(
                        player,
                        'trash_from_hand_or_discard',
                        candidates,
                        prompt,
                        count=int(count or 1),
                        source_name=context.get('card_name') if context else None,
                    )
                    return {'pending_choice': True}
            return None

        # ✅ Extra move (increase movement points)
        if etype == "extra_move":
            count = effect.get("count", 1)
            player.moves_left += count
            return

        # ✅ Extend build range (temporary modifier stored on player)
        if etype == "extend_build_range":
            amount = effect.get("amount", 1)
            current = getattr(player, "build_range_bonus", 0)
            player.build_range_bonus = current + amount
            return

        # Other effect types handled elsewhere or future steps
        return
