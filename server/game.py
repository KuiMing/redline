# (Step 3.3 update)
# Only relevant modified sections shown for brevity in this environment.
# Full file retained, with added modifier hooks.

# ... existing imports remain unchanged ...

class Game:
    # ... existing __init__ unchanged ...

    # ---------- Era Modifiers ----------

    def _has_active_effect(self, effect_type):
        return any(
            era.effect.get("red_effect", {}).get("type") == effect_type or
            era.effect.get("rebel_effect", {}).get("type") == effect_type
            for era in getattr(self, "era_engine", []).active_eras
        ) if hasattr(self, "era_engine") else False

    def _get_effect_value(self, effect_type, key):
        for era in getattr(self, "era_engine", []).active_eras:
            for side in ["red_effect", "rebel_effect"]:
                eff = era.effect.get(side, {})
                if eff.get("type") == effect_type:
                    return eff.get(key)
        return None

    # ---------- Build Organization ----------

    def build_organization(self, town_name):
        if self.game_phase != GamePhase.MAIN:
            return {"error": "Invalid game phase"}
        if self.turn_phase != TurnPhase.ACTION:
            return {"error": "Can only build during ACTION phase"}

        player = self.current_player()

        if self._has_active_effect("restrict_build"):
            return {"error": "Building restricted by active era"}

        cost = 1
        bonus = self._get_effect_value("propaganda_bonus", "amount")

        if player.resources["propaganda"] < cost:
            return {"error": "Not enough propaganda to build"}

        player.resources["propaganda"] -= cost

        if bonus:
            player.resources["propaganda"] += bonus

        player.organizations[town_name] = player.organizations.get(town_name, 0) + 1
        return {"success": True}

    # ---------- Buy Card ----------

    def buy_card(self, card_index):
        player = self.current_player()
        if self.turn_phase != TurnPhase.ACTION:
            return {"error": "Can only buy in ACTION phase"}

        card = self.purchase_area[card_index]
        cost = 2

        reduction = self._get_effect_value("reduce_cost", "amount")
        if reduction:
            cost = max(0, cost - reduction)

        if player.resources["money"] < cost:
            return {"error": "Not enough money"}

        player.resources["money"] -= cost
        player.deck.discard([card])
        return {"success": True}

    # ---------- Move Organization ----------

    def move_organization(self, from_town, to_town, mode="road"):
        player = self.current_player()
        if self.turn_phase != TurnPhase.ACTION:
            return {"error": "Can only move in ACTION phase"}

        if player.organizations.get(from_town, 0) <= 0:
            return {"error": "No organization in source town"}

        ignore = self._has_active_effect("ignore_distance")

        if not ignore:
            connections = self.map["towns"].get(from_town, {})
            if to_town not in connections.get(mode, []):
                return {"error": "Towns not connected by this mode"}

        player.organizations[from_town] -= 1
        if player.organizations[from_town] == 0:
            del player.organizations[from_town]

        player.organizations[to_town] = player.organizations.get(to_town, 0) + 1
        return {"success": True}
