# FACTION_ABILITY_PHASE6_IMPLEMENTATION

日期：2026-05-06

## 本輪完成的 phase6 engine 實作

這一輪先補上：

### 1. 共用組織（第一版）
目前已實作第一版 shared organization access：
- 若 faction 之間具有共用組織規則
- 則可把對方在共享城鎮的組織，視為自己可用的建立據點

目前已解析的共享組織來源：
- `shared_organizations_with`
- `special_rules` 中的文字規則（如：
  - 與粵、澳門共用組織
  - 與綠線臺灣共用組織
  - 與藍線臺灣共用組織）

### 2. 華文傳媒 / 民主陣線 / 立場試探 / 賭徒耳語
這些特殊能力也已進一步完成：
- 華文傳媒：以 money 支付 propaganda 類購買成本
- 民主陣線：2 點任意資源換 1 張已移除牌代理卡
- 立場試探：翻頂牌並依奇偶決定去向
- 賭徒耳語：底牌後猜奇數流程，猜中得 3 資金 + 3 宣傳

## 主要程式改動

### server/game.py
新增 / 補上：
- `_factions_sharing_with(faction_id)`
- `_town_has_shared_org_access(player, town)`

### can_develop_in_town()
- 現在可接受 shared organization access 作為可建立依據之一

### build_organization()
- 不再只接受玩家自己在該城鎮有組織
- 若該城鎮屬於共享組織可用據點，也可建立

## 驗證
新增：
- `scripts/validate/validate_shared_organizations_phase6.py`

輸出：
- `SHARED_ORGANIZATIONS_PHASE6_VALIDATION.json`
- `SHARED_ORGANIZATIONS_PHASE6_VALIDATION.md`

### 驗證結果
- 香港 / 粵 的共享組織測試通過
- 可透過共享的 `香港城` 作為建立據點成功建立組織

## 目前仍未完成
- 共享組織目前只先接到「建立據點可用性」
- 尚未完整接到：
  - 控制顯示
  - 勝利條件計數
  - 瓦解 / 移動 / map UI 層共同判定
- 民族祭儀尚未實作
- 印度研究分析室尚未實作
