from server.effect_engine import EffectEngine


class ActionCardEngine:
    def __init__(self, structured_cards):
        self.cards = {c["name"]: c for c in structured_cards}
        self.effect_engine = EffectEngine()

    def execute(self, card_name, player, game):
        card = self.cards.get(card_name)
        if not card:
            return

        # 1️⃣ 基礎資源
        for k, v in card.get("resources", {}).items():
            player.resources[k] += v

        # 2️⃣ 統一 effect pipeline
        for effect in card.get("effect", []):
            self.effect_engine.execute(effect, player, game)
