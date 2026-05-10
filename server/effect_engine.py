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

        # ✅ Peek deck (MVP: no UI return)
        if etype == "peek_deck":
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

        # ✅ Shared draw
        if etype == "shared_draw":
            count = effect.get("count", 1)
            for other in game.players:
                self._draw(other, count)
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
