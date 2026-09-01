# FACTION_ABILITY_PHASE1_IMPLEMENTATION

日期：2026-05-05

## 本輪完成的第一批 engine 實作

這一輪先補了主陣營第一批、相對低風險且高價值的 faction abilities：

### 香港
- `攬炒策略`
  - 在遊戲開始時，免費將 1 張 `宣傳家` 放進起始牌庫（目前實作為加入起始 deck 的棄牌區，之後會隨洗牌進循環）
- `國際線`
  - 當根據地為倫敦時，money 類牌也會被視為 propaganda 類型，用於觸發 propaganda 型條件

### 臺灣
- `本土社團`（綠線）
  - 若本回合曾在牆內建立組織，行動階段結束時額外抽 1 張牌
- `民國之心`（藍線）
  - 若本回合曾在牆內或南洋建立組織，行動階段結束時額外抽 1 張牌
  - 目前先以「有建立組織」作為第一版接線，後續可再細分區域條件

### 蒙古
- `盟族學校`
  - 現在會限制只能在帶有 `蒙古` camp tag 的空間建立組織

### 哈薩克
- `民族調和`（`first_propaganda_draw`）
  - 第一張 propaganda 類牌的觸發旗標已可被引擎辨識，用於後續條件接線

## 主要程式改動

### server/game.py
新增 / 補上：
- `self.ability_templates`
- `_resolve_faction_abilities()`
- `_player_base_data()`
- `_player_effective_abilities()`
- `_player_has_ability()`
- `_starter_card()`
- `_apply_setup_abilities()`
- `turn_log['built_towns']`
- `build_organization()` 記錄 built town
- `play_card()` 支援 `國際線` 對 card type 的影響
- `build_organization()` 支援 `盟族學校` 的發展限制
- `buy_card()` 補了一個最小可用版本

### server/main.py
- `/start` 在 lobby base 套用完成後，也會呼叫 `game._apply_setup_abilities(player)`

### 驗證腳本
新增：
- `scripts/validate/validate_faction_abilities_phase1.py`

輸出：
- `FACTION_ABILITY_PHASE1_VALIDATION.json`
- `FACTION_ABILITY_PHASE1_VALIDATION.md`

## 驗證結果

phase1 驗證目前是：
- total: 6
- passed: 6
- failed: 0

已涵蓋：
- 香港 `攬炒策略`
- 香港 `國際線`
- 臺灣綠線 `本土社團`
- 臺灣藍線 `民國之心`
- 蒙古 `盟族學校`
- 哈薩克 `民族調和`（第一張 propaganda 觸發旗標）

## 仍未完成

這一輪仍然只是 phase1，還沒有補完：
- `安全屋` 真正影響 build distance
- `商貿組織` / `展現實力` / `殉道者` / `民族祭儀` 等大量模板能力
- 維吾爾 / 西藏分支能力的完整 engine 接線
- 非暴力 / 特殊購買 / 奇偶判定 / 額外看牌堆等複雜能力
