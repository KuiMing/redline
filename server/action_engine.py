from server.effect_engine import EffectEngine


class ActionCardEngine:
    def __init__(self, structured_cards):
        self.cards = {c["name"]: c for c in structured_cards}
        self.effect_engine = EffectEngine()

    def execute(self, card_name, player, game, context=None, include_resources=True):
        card = self.cards.get(card_name)
        if not card:
            return None

        # Resource mode: printed resources only.
        # Action mode passes include_resources=False so card effects do not also grant printed resources.
        if include_resources:
            for k, v in card.get("resources", {}).items():
                player.resources[k] += v

        # 統一 effect pipeline
        context = context or {}
        effects = card.get("effect", [])
        for idx, effect in enumerate(effects):
            context['remaining_effects'] = effects[idx + 1:]
            result = self.effect_engine.execute(effect, player, game, context=context)
            if isinstance(result, dict) and result.get('pending_choice'):
                return result
        return None
