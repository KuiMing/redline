class Card:
    def __init__(self, name, card_type, resources=None, effect=None):
        self.name = name
        self.card_type = card_type
        self.resources = resources or {"money": 0, "propaganda": 0}
        self.effect = effect

    def apply(self, player, game):
        # Add resources
        player.resources["money"] += self.resources.get("money", 0)
        player.resources["propaganda"] += self.resources.get("propaganda", 0)

        # Basic effect handler
        if callable(self.effect):
            self.effect(player, game)
