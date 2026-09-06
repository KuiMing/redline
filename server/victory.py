# 宛擴充地圖（2026-09-06 建模）：宛陣營勝利條件的「全宛地」範圍＝主地圖南陽＋這 20 個
# 宛地圖城鎮（見 data/map.json 對應條目；統治者皆為紅軍，可建組織陣營僅紅軍／反賊）。
WAN_EXPANSION_TOWNS = frozenset({
    "南陽",
    "十堰", "丹江口", "老河口", "襄陽", "棗陽",
    "西峽", "淅川", "內鄉", "鎮平", "南召", "臥龍",
    "鄧州", "新野", "博望", "方城", "社旗", "唐河", "泌陽", "桐柏", "舞陽",
})


class VictoryEngine:
    def __init__(self, factions_data):
        self.factions = {f['id']: f for f in factions_data}

    def _towns_for_ruler(self, game, ruler):
        towns_by_ruler = getattr(game, 'towns_by_ruler', None) or {}
        return set(towns_by_ruler.get(ruler, []))

    def evaluate(self, game):
        # 1. Evaluate explicit faction conditions first. The turn-20 Red Army rule
        # is a survival fallback, not a priority override: if a non-red faction
        # still satisfies its condition at the round-wrap check, that faction wins.
        for player in game.players:
            win, winner = self._check_player_conditions(player, game)
            if win:
                return True, winner

        # 2. Red Army default survival (turn 20 rule)
        if game.turn > 20:
            red_player = next((p for p in game.players if p.faction_id == "red_army"), None)
            if red_player:
                return True, "red_army"

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
                any_of_groups = cond.get("required_any_of") or []
                if (self._count_scope(player, cond.get("scope", "牆內"), game) >= cond.get("count", 0)
                        and all(game._shared_org_count(player, town) > 0 for town in required)
                        and all(any(game._shared_org_count(player, town) > 0 for town in group) for group in any_of_groups)):
                    met_conditions += 1

            elif cond_type == "map_specific_count":
                # Simplified: treat as count_only in current map
                if player.total_organizations() >= cond.get("count", 0):
                    met_conditions += 1

            elif cond_type == "taiwan_override":
                if player.faction_id == "red_army" and self._taiwan_faction_present(game):
                    if self._count_taiwan_orgs(player, game) >= 14:
                        return True, "red_army"

            elif cond_type == "default_survival":
                # handled globally above
                continue

        # 勝利：達成任一條件即獲勝
        if conditions and met_conditions >= 1:
            return True, player.name

        return False, None

    def condition_progress(self, player, game):
        """回傳玩家對自身陣營勝利條件的最高達成比例（0.0~1.0+）。
        用於 rules.md「共同勝利」：反共玩家獲勝時，其他反共玩家達成比例 >= 2/3 即為共同勝利者
        （2026-07-11 使用者裁決 A4）。count_and_required 以組織數比例衡量（必含城鎮不另計，
        屬簡化，若之後裁定需併入可再調整）。"""
        faction = self.factions.get(getattr(player, 'faction_id', None)) or {}
        best = 0.0
        for cond in faction.get("win_conditions", []) or []:
            cond_type = cond.get("type")
            required = int(cond.get("count", 0) or 0)
            if required <= 0:
                continue
            if cond_type in {"count_only", "count_and_required"}:
                best = max(best, self._count_scope(player, cond.get("scope", "牆內"), game) / required)
            elif cond_type == "map_specific_count":
                best = max(best, player.total_organizations() / required)
        return best

    def co_winners(self, game, winner_name):
        """反共陣營玩家獲勝時，其他反共玩家達成自身條件 2/3 以上（含）者為共同勝利者。
        紅軍獲勝（含第20回合保底與臺灣壓制）不適用。"""
        winner_player = next((p for p in game.players if p.name == winner_name), None)
        if winner_player is None or getattr(winner_player, 'faction_id', None) == 'red_army':
            return []
        threshold = 2.0 / 3.0 - 1e-9
        names = []
        for p in game.players:
            if p is winner_player or getattr(p, 'faction_id', None) == 'red_army':
                continue
            if self.condition_progress(p, game) >= threshold:
                names.append(p.name)
        return names

    def _count_scope(self, player, scope, game):
        def shared_count(towns):
            return sum(1 for town in towns if game._shared_org_count(player, town) > 0)

        all_org_towns = {
            town
            for p in game.players
            for town, count in p.organizations.items()
            if count > 0
        }

        if scope == "牆內":
            scope_counts = getattr(game, "_player_organization_scope_counts", None)
            if callable(scope_counts):
                counts = scope_counts(player, include_shared=True)
                if isinstance(counts, dict):
                    return int(counts.get("inside_wall", 0) or 0)
            china_towns = self._towns_for_ruler(game, "紅軍")
            return shared_count(china_towns)
        if scope == "牆內與牆外":
            return shared_count(all_org_towns)
        if scope == "宛地":
            # 宛（win_condition：全宛地）＝主地圖南陽＋宛擴充地圖城鎮（2026-09-06 已建模）
            return shared_count(WAN_EXPANSION_TOWNS)
        return shared_count(all_org_towns)

    def _taiwan_faction_present(self, game):
        return any(
            (self.factions.get(getattr(player, "faction_id", None)) or {}).get("camp") == "taiwan"
            for player in game.players
        )

    def _count_taiwan_orgs(self, player, game):
        taiwan_towns = self._towns_for_ruler(game, "臺灣")
        return sum(1 for town, count in player.organizations.items() if town in taiwan_towns and count > 0)
