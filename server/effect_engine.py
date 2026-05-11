class EffectEngine:
    """
    Centralized effect execution pipeline.
    Now implements core executable effect types.
    """

    def _draw(self, player, count):
        player.hand.extend(player.deck.draw(count))

    def _starter_names(self):
        return {"追隨者", "樂捐者"}

    def execute(self, effect, player, game, context=None):
        etype = effect.get("type")

        # ✅ Draw cards
        if etype == "draw":
            count = effect.get("count", 1)
            self._draw(player, count)
            return

        # ✅ Discard self
        if etype == "discard_self":
            count = effect.get("count", 1)
            for _ in range(min(count, len(player.hand))):
                card = player.hand.pop()
                player.deck.discard([card])
            return

        # ✅ Gain resources
        if etype == "gain_resource":
            player.resources["money"] += effect.get("money", 0)
            player.resources["propaganda"] += effect.get("propaganda", 0)
            return

        # ✅ Force discard opponents
        if etype == "force_discard":
            count = effect.get("count", 1)
            for other in game.players:
                if other != player:
                    for _ in range(min(count, len(other.hand))):
                        card = other.hand.pop()
                        other.deck.discard([card])
            return

        # ✅ Gain from discard (simplified cost handling)
        if etype == "gain_from_discard":
            if player.deck.discard_pile:
                card = player.deck.discard_pile[-1]
                ok, err = game._can_player_gain_flag_card(player, card)
                if not ok:
                    game.log(f"{player.name} could not gain {getattr(card, 'name', str(card))}: {err}")
                    return
                card = player.deck.discard_pile.pop()
                player.hand.append(card)
            return

        # ✅ Gain any from discard
        if etype == "gain_any_from_discard":
            if player.deck.discard_pile:
                card = player.deck.discard_pile[-1]
                ok, err = game._can_player_gain_flag_card(player, card)
                if not ok:
                    game.log(f"{player.name} could not gain {getattr(card, 'name', str(card))}: {err}")
                    return
                card = player.deck.discard_pile.pop()
                player.hand.append(card)
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
                supply = int(getattr(game, "static_purchase_supply", {}).get("內鬥", 0) or 0)
                if supply > 0:
                    from server.cards import Card
                    game.static_purchase_supply["內鬥"] = supply - 1
                    target.deck.discard([Card("內鬥", "disruption", {})])
                    game.log(f"{player.name} used 走漏風聲 on {target.name}: discarded {card_name} and moved 內鬥 from supply to discard")
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
            if effect.get('include_discard_for_faction') == player.faction_id:
                cards.extend(player.deck.discard_pile)
            if not cards:
                return
            game.pending_choice = {
                'type': 'recruit_talent',
                'player_id': player.id,
                'cards': cards,
                'source_cards': cards[:],
                'prompt': '網羅人才：從己方牌庫任選1張加入手牌，而後將牌庫洗牌。'
            }
            game.log(f"{player.name} may recruit 1 card from deck")
            return

        # ✅ Temporarily use another player's top deck card (模仿戰術)
        if etype == "imitate_topdeck":
            context = context or {}
            target_id = context.get("target_player_id") or effect.get("target_player_id")
            target = None
            if target_id:
                target = next((p for p in game.players if getattr(p, "id", None) == target_id), None)
            if target is None:
                target = next((p for p in game.players if p != player), None)
            if target is None:
                return
            drawn = target.deck.draw(1)
            if not drawn:
                return
            borrowed = drawn[0]
            setattr(borrowed, '_return_to_owner_topdeck', target.id)
            player.hand.append(borrowed)
            game.log(f"{player.name} imitated {target.name}'s top card {getattr(borrowed, 'name', str(borrowed))}")
            return

        # ✅ Top deck to hand
        if etype == "topdeck_to_hand":
            drawn = player.deck.draw(1)
            if drawn:
                player.hand.extend(drawn)
            return

        # ✅ Optional trash (MVP: trash the last card in hand if any)
        if etype == "optional_trash":
            context = context or {}
            current_card = context.get('current_card')
            if current_card is not None:
                returned = game._return_removed_card_to_purchase_supply(current_card)
                if returned:
                    context['removed_current_card'] = True
                    game.log(f"{player.name} removed {getattr(current_card, 'name', str(current_card))} and it returned to {returned.get('zone')}")
            elif player.hand:
                trashed = player.hand.pop()
                returned = game._return_removed_card_to_purchase_supply(trashed)
                game.log(f"{player.name} removed {getattr(trashed, 'name', str(trashed))}")
                if returned:
                    game.log(f"{getattr(trashed, 'name', str(trashed))} returned to {returned.get('zone')}")
            return

        # ✅ Build via card effect (MVP: reinforce current base or first owned legal town)
        if etype == "build":
            target = player.base if player.base and player.organizations.get(player.base, 0) > 0 and game.can_develop_in_town(player, player.base) else None
            if not target:
                owned = [town for town, count in player.organizations.items() if count > 0 and game.can_develop_in_town(player, town)]
                target = owned[0] if owned else None
            if target:
                player.organizations[target] = player.organizations.get(target, 0) + 1
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
            self._draw(player, count)
            context = context or {}
            target_id = context.get("target_player_id") or effect.get("target_player_id")
            target = None
            if target_id:
                target = next((p for p in game.players if getattr(p, "id", None) == target_id), None)
            if target is None:
                target = next((p for p in game.players if p != player), None)
            if target is not None:
                self._draw(target, count)
            return

        # ✅ Choose one branch, defaulting to the first option until UI choice is wired (情報網)
        if etype == "choose_one":
            context = context or {}
            options = effect.get('options') or []
            selected = context.get('choice_index', effect.get('default_index', 0))
            if not isinstance(selected, int) or selected < 0 or selected >= len(options):
                selected = 0
            for nested in options[selected].get('effect', []):
                self.execute(nested, player, game, context=context)
            return

        # ✅ Move a card bought this turn from discard to deck top (行動預告/行動募資)
        if etype == "topdeck_purchased_this_turn":
            purchased = list(game.turn_log.get('purchased_cards_this_turn') or [])
            for card in reversed(purchased):
                if card in player.deck.discard_pile:
                    player.deck.discard_pile.remove(card)
                    player.deck.draw_pile.append(card)
                    game.log(f"{player.name} placed bought card {getattr(card, 'name', str(card))} on deck top")
                    break
            return

        # ✅ Temporarily use a face-up purchase-area card (企業人脈; MVP first non-static random card)
        if etype == "use_purchase_area_card":
            static_count = len(game._static_purchase_cards()) if hasattr(game, '_static_purchase_cards') else 0
            start = static_count if effect.get('prefer_random_market', True) else 0
            source = None
            source_index = None
            for idx in range(start, len(getattr(game, 'purchase_area', []) or [])):
                candidate = game.purchase_area[idx]
                if candidate:
                    source = candidate
                    source_index = idx
                    break
            if source is None:
                return
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
            if condition == "played_propaganda_card":
                should_draw = bool(game.turn_log.get("played_propaganda_card"))
            elif condition == "played_money_card":
                should_draw = bool(game.turn_log.get("played_money_card"))
            elif condition == "successful_discard":
                should_draw = bool(game.turn_log.get("successful_discard"))
            elif condition == "canceled_propaganda_card":
                should_draw = bool(game.turn_log.get("canceled_propaganda_card"))
            elif condition == "canceled_money_cost_card":
                should_draw = bool(game.turn_log.get("canceled_money_cost_card"))
            if should_draw:
                self._draw(player, effect.get("count", 1))
            return

        # ✅ Add internal conflict cards (MVP: add named disruption cards to discard pile)
        if etype == "add_internal_conflict":
            count = effect.get("count", 1)
            from server.cards import Card
            cards = [Card("內鬥", "disruption", {}) for _ in range(count)]
            player.deck.discard(cards)
            game.log(f"{player.name} gained {count} 內鬥 card(s)")
            return

        # ✅ Cancel card (MVP: set turn flag for later conditional checks)
        if etype == "cancel_card":
            game.turn_log["canceled_propaganda_card"] = True
            game.log(f"{player.name} triggered cancel-card effect")
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

        # ✅ Dissolve (MVP: remove one org from first available opponent town; optional self sacrifice)
        if etype == "dissolve":
            if effect.get("requires_self_sacrifice"):
                owned = [town for town, count in player.organizations.items() if count > 0]
                if owned:
                    town = owned[0]
                    player.organizations[town] -= 1
                    if player.organizations[town] <= 0:
                        del player.organizations[town]
            for other in game.players:
                if other == player:
                    continue
                owned = [town for town, count in other.organizations.items() if count > 0]
                if owned:
                    town = owned[0]
                    result = game.dissolve_organization(player, other, town, source="card")
                    if result.get("success"):
                        break
            return

        # ✅ Refresh purchase area (MVP: expose top 3 cards from current player's deck)
        if etype == "refresh_purchase_area":
            game.purchase_area = player.deck.draw(3)
            return

        # ✅ Trash from hand or discard
        if etype == "trash_from_hand_or_discard":
            count = effect.get("count", 1)
            starters = self._starter_names()
            for _ in range(count):
                card = None
                for i, c in enumerate(player.hand):
                    if getattr(c, "name", str(c)) not in starters:
                        card = player.hand.pop(i)
                        game.turn_log["non_starter_discard"] = True
                        break
                if card is None:
                    for i, c in enumerate(player.deck.discard_pile):
                        if getattr(c, "name", str(c)) not in starters:
                            card = player.deck.discard_pile.pop(i)
                            game.turn_log["non_starter_discard"] = True
                            break
                if card is None and player.hand:
                    card = player.hand.pop()
                elif card is None and player.deck.discard_pile:
                    card = player.deck.discard_pile.pop()
                if card is not None:
                    game.log(f"{player.name} trashed {getattr(card, 'name', str(card))}")
            return

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
