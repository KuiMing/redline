class VictoryEngine:
    def __init__(self, factions_data, board_regions):
        self.factions = {f['id']: f for f in factions_data}
        self.board_regions = board_regions

    def evaluate(self, game):
        # 1. Red Army default survival (turn 20 rule)
        if game.turn > 20:
            red_player = next((p for p in game.players if p.faction_id == "red_army"), None)
            if red_player:
                return True, "red_army"

        # 2. Evaluate each player's faction conditions
        for player in game.players:
            win, winner = self._check_player_conditions(player, game)
            if win:
                return True, winner

        return False, None

    def _check_player_conditions(self, player, game):
        faction = self.factions.get(player.faction_id)
        if not faction:
            return False, None

        conditions = faction.get("win_conditions", [])
        met_conditions = 0

        for cond in conditions:
            cond_type = cond.get("type")

            if cond_type == "count_only":
                if self._count_scope(player, cond.get("scope", "牆內"), game) >= cond.get("count", 0):
                    met_conditions += 1

            elif cond_type == "count_and_required":
                required = set(cond.get("required_locations", []))
                if (self._count_scope(player, cond.get("scope", "牆內"), game) >= cond.get("count", 0)
                        and required.issubset(player.organizations.keys())):
                    met_conditions += 1

            elif cond_type == "map_specific_count":
                # Simplified: treat as count_only in current map
                if player.total_organizations() >= cond.get("count", 0):
                    met_conditions += 1

            elif cond_type == "taiwan_override":
                if player.faction_id == "red_army":
                    if self._count_taiwan_orgs(player) >= 14:
                        return True, "red_army"

            elif cond_type == "default_survival":
                # handled globally above
                continue

        # 共同勝利：達成 2/3 條件
        if conditions:
            required = max(1, (len(conditions) * 2) // 3)
            if met_conditions >= required:
                return True, player.name

        return False, None

    def _count_scope(self, player, scope, game):
        if scope == "牆內":
            china_towns = set(self.board_regions.get("china", {}).get("towns", []))
            return sum(v for t, v in player.organizations.items() if t in china_towns)
        return player.total_organizations()

    def _count_taiwan_orgs(self, player):
        taiwan_towns = set(self.board_regions.get("taiwan", {}).get("towns", []))
        return sum(v for t, v in player.organizations.items() if t in taiwan_towns)
