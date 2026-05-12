class VictoryEngine:
    def __init__(self, factions_data, board_regions=None):
        self.factions = {f['id']: f for f in factions_data}
        self.board_regions = board_regions or {}

    def _towns_for_ruler(self, game, ruler):
        towns_by_ruler = getattr(game, 'towns_by_ruler', None) or {}
        return set(towns_by_ruler.get(ruler, []))

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
                        and all(game._shared_org_count(player, town) > 0 for town in required)):
                    met_conditions += 1

            elif cond_type == "map_specific_count":
                # Simplified: treat as count_only in current map
                if player.total_organizations() >= cond.get("count", 0):
                    met_conditions += 1

            elif cond_type == "taiwan_override":
                if player.faction_id == "red_army":
                    if self._count_taiwan_orgs(player, game) >= 14:
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
        def shared_count(towns):
            total = 0
            for town in towns:
                total += game._shared_org_count(player, town)
            return total

        all_org_towns = {
            town
            for p in game.players
            for town, count in p.organizations.items()
            if count > 0
        }

        if scope == "牆內":
            china_towns = self._towns_for_ruler(game, "紅軍")
            return shared_count(china_towns)
        if scope == "牆內與牆外":
            return shared_count(all_org_towns)
        return shared_count(all_org_towns)

    def _count_taiwan_orgs(self, player, game):
        taiwan_towns = self._towns_for_ruler(game, "臺灣")
        return sum(v for t, v in player.organizations.items() if t in taiwan_towns)
