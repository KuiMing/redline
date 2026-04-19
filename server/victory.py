class VictoryEngine:
    def __init__(self, factions_data, board_regions):
        self.factions = {f['id']: f for f in factions_data}
        self.board_regions = board_regions

    def check_player_victory(self, player):
        faction = self.factions.get(player.faction_id)
        if not faction:
            return False, None

        conditions = faction.get("win_conditions", [])

        for cond in conditions:
            cond_type = cond.get("type")

            if cond_type == "count_only":
                count = cond.get("count", 0)
                scope = cond.get("scope", "牆內")
                if self._count_scope(player, scope) >= count:
                    return True, player.name

            if cond_type == "count_and_required":
                count = cond.get("count", 0)
                required = set(cond.get("required_locations", []))
                if self._count_scope(player, cond.get("scope", "牆內")) >= count and required.issubset(player.organizations.keys()):
                    return True, player.name

        return False, None

    def _count_scope(self, player, scope):
        # simplified: treat "牆內" as china region
        if scope == "牆內":
            china_towns = set(self.board_regions.get("china", {}).get("towns", []))
            return sum(v for t, v in player.organizations.items() if t in china_towns)
        return player.total_organizations()
