class EffectEngine:
    """
    Centralized effect execution pipeline.
    Now implements core executable effect types.
    """

    def execute(self, effect, player, game, context=None):
        etype = effect.get("type")

        # ✅ Draw cards
        if etype == "draw":
            count = effect.get("count", 1)
            player.hand.extend(player.deck.draw(count))
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

        # Other effect types handled elsewhere or future steps
        return
