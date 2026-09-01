# FACTION_ABILITY_PHASE10_SUPPORT_CARD_EFFECTS_BATCH2

日期：2026-05-08

## 本輪完成

延續 phase10 的奧援卡 runtime，補上第二批可驗證效果：
- 東洋奧援
- 北國奧援
- 臺灣奧援

## 已完成

### 1. 東洋奧援
#### server/game.py
- III：`build_anywhere_inner`
- II：`build_near_inner`
- I：`+2 propaganda`

### 2. 北國奧援
#### server/game.py
- III：`dissolve_many_near` x2
- II：`dissolve_many_near` x1
- I：`dissolve_self_and_enemy`

### 3. 臺灣奧援
#### server/game.py
- III：`dissolve_and_build`
- II：`dissolve_many_near` x1
- I：`+1 propaganda`

### 4. tier fallback 修正
#### server/game.py
- `_support_card_tier()` 原本在完全無 matched rulers 時回傳 `(1, None, [])`
- 這會讓 I 級 text/effect 取不到 region entry
- 現已改為：
  - 若存在 `regions`，I 級 fallback 仍綁定第 0 個 region entry

這修正了所有 I 級奧援卡無法正常落地的問題。

## 驗證
更新：
- `scripts/validate/validate_support_card_effects_runtime.py`

輸出：
- `SUPPORT_CARD_EFFECTS_RUNTIME_VALIDATION.json`
- `SUPPORT_CARD_EFFECTS_RUNTIME_VALIDATION.md`

### 最新結果
- total: 6
- passed: 6
- failed: 0

### 本輪新增覆蓋
1. `東洋奧援` I 級：獲得 2 點宣傳
2. `北國奧援` II 級：成功瓦解 1 個對手組織
3. `臺灣奧援` I 級：獲得 1 點宣傳

## 目前仍未完成
- 天方奧援（discard target / random / target-chosen 語義）
- 東洋奧援 II / III 真實 build path 實戰截圖
- 北國奧援 I / III 與臺灣奧援 II / III 的更完整 UI 驗證
- 隨機 18 張奧援卡混入正式購買區牌庫
