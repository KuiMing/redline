class EffectEngine:
    """
    Centralized effect execution pipeline.
    Currently supports skeleton handling for all defined effect types.
    Concrete logic will be filled incrementally.
    """

    def execute(self, effect, player, game, context=None):
        etype = effect.get("type")

        # Card flow
        if etype == "draw":
            count = effect.get("count", 1)
            player.hand.extend(player.deck.draw(count))
            return

        if etype == "discard_self":
            count = effect.get("count", 1)
            for _ in range(min(count, len(player.hand))):
                card = player.hand.pop()
                player.deck.discard([card])
            return

        if etype == "gain_resource":
            player.resources["money"] += effect.get("money", 0)
            player.resources["propaganda"] += effect.get("propaganda", 0)
            return

        # Movement / build modifiers handled in Game layer
        if etype in [
            "build",
            "move",
            "extra_move",
            "extend_build_range",
            "ignore_distance",
            "reduce_cost",
            "restrict_build",
            "add_internal_conflict",
            "add_distraction",
            "dissolve",
            "gain_from_discard",
            "gain_any_from_discard",
            "peek_deck",
            "topdeck_to_hand",
            "cancel_card",
            "force_discard",
            "conditional_draw",
            "conditional_bonus",
            "conditional_trash_bonus",
            "refresh_purchase_area",
        ]:
            # Placeholder for structured handling in next steps
            return

        # Unknown effect: ignore safely
        return
