from server.game import Game

# ✅ 模擬兩人局：紅軍 + 香港
players_data = [
    ("red_id", "Red Army"),
    ("hk_id", "Hong Kong")
]

g = Game(players_data)

# ✅ 找到香港玩家
hk_player = None
for p in g.players:
    if p.name == "Hong Kong":
        hk_player = p
        break

if not hk_player:
    print("❌ 找不到 Hong Kong 玩家")
    exit()

# ✅ 取得香港區 town
hong_kong_towns = g.board_regions.get("hong_kong", {}).get("towns", [])

if not hong_kong_towns:
    print("❌ 找不到 hong_kong region")
    exit()

# ✅ 在第一個香港 town 疊 10 個組織
hk_player.organizations[hong_kong_towns[0]] = 10

# ✅ 手動觸發 Era 檢查
g._check_era_trigger()

print("Active Eras after trigger:", g.era_engine.get_active_eras())

# ✅ 模擬兩回合（兩次完整回合結束）
g._end_turn()
g._end_turn()

print("Active Eras after 2 turns:", g.era_engine.get_active_eras())
