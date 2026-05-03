class EffectEngine:
    """
    Centralized effect execution pipeline.
    Now implements core executable effect types.
    """

    def _draw(self, player, count):
        player.hand.extend(player.deck.draw(count))

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
                card = player.deck.discard_pile.pop()
                player.hand.append(card)
            return

        # ✅ Gain any from discard
        if etype == "gain_any_from_discard":
            if player.deck.discard_pile:
                card = player.deck.discard_pile.pop()
                player.hand.append(card)
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
            if player.hand:
                trashed = player.hand.pop()
                game.log(f"{player.name} trashed {getattr(trashed, 'name', str(trashed))}")
            return

        # ✅ Build via card effect (MVP: reinforce current base or first owned town)
        if etype == "build":
            target = player.base if player.base and player.organizations.get(player.base, 0) > 0 else None
            if not target:
                owned = [town for town, count in player.organizations.items() if count > 0]
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
