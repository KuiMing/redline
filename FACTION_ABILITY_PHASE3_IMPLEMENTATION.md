# FACTION_ABILITY_PHASE3_IMPLEMENTATION

日期：2026-05-05

## 本輪完成的 phase3 engine 實作

這一輪先補了兩類高影響規則型能力：

### 1. 非暴力
已實作第一版禁止規則：
- 禁止打出 `armed` / `equipment` 類牌
- 禁止購買 `armed` / `equipment` 類牌

目前已套用到具有 `非暴力` 能力的 faction，例如：
- 維吾爾（慕尼黑）
- 西藏（達蘭薩拉）
- 民運派
- 性別革命

### 2. 游擊隊
已實作第一版 on-build 觸發：
- 若在牆內建立組織，且該 faction 具有 `游擊隊`
- 則每回合最多觸發 1 次
- 若紅軍有手牌：紅軍棄 1 張手牌
- 若紅軍無手牌：自己抽 1 張牌

目前適用：
- 維吾爾（伊斯坦堡）
- 西藏（德拉敦）
- 西藏（哲古宗）

## 主要程式改動

### server/game.py
新增 / 補上：
- `turn_log['guerrilla_triggered']`
- `_player_is_nonviolent()`
- `_card_is_banned_for_player()`
- `_apply_guerrilla_on_build()`

### 行為接線
- `play_card()`：非暴力玩家不能打出武裝 / 裝備類卡牌
- `buy_card()`：非暴力玩家不能購買武裝 / 裝備類卡牌
- `build_organization()`：建立成功後會檢查是否觸發游擊隊
- `build_organization_with_support()`：安全屋 / 支援建立也會檢查游擊隊

## 驗證
新增：
- `scripts/validate_faction_abilities_phase3.py`

輸出：
- `FACTION_ABILITY_PHASE3_VALIDATION.json`
- `FACTION_ABILITY_PHASE3_VALIDATION.md`

### 驗證結果
- total: 4
- passed: 4
- failed: 0

已涵蓋：
- 非暴力：打牌限制
- 非暴力：購買限制
- 游擊隊：紅軍有手牌時被迫棄牌
- 游擊隊：紅軍沒手牌時改為自己抽牌

## 仍未完成
- 非暴力尚未涵蓋「持有 / 得牌即攔截」等更深層入口
- 印度研究分析室的旗幟限制尚未接線
- 共用組織尚未實作
- 民族祭儀尚未實作
- 民運派 / 自由派 / 澳門 / 法輪功 / 性別革命其他特殊能力尚未實作
