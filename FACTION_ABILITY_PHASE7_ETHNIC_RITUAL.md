# FACTION_ABILITY_PHASE7_ETHNIC_RITUAL

日期：2026-05-06

## 本輪完成

已把 `民族祭儀` 補進 engine，並且接上和 `賭徒耳語` 同等級的猜奇偶 UI。

## Engine 行為

### 民族祭儀
- 將 1 張手牌放進牌庫底
- 猜牌庫頂牌購買費用的奇偶
- 展示並結算：
  - 猜中 → `+2 money`、`+2 propaganda`
  - 猜錯 → `+2 propaganda`

目前採用：
- `action = 'faction_action'`
- `name = '民族祭儀'`
- `guess = 'odd' | 'even'`

## 影響 faction
目前這批少數民族 faction 都可使用民族祭儀 UI：
- `dian_zhuang`
- `zhuang`
- `yi`
- `bai`
- `hani`
- `dai`
- `miao`
- `tujia`
- `dong`
- `buyei`
- `yao`
- `li`

## UI

### static/app.js
- 新增 `openEthnicRitualGuessModal()`
- `renderFactionActionPanel(state)` 現在會對民族祭儀系 faction 顯示：
  - `發動 民族祭儀`
- 點下後打開與賭徒耳語相同風格的中央霧面玻璃 modal
- 可選：
  - `猜奇數`
  - `猜偶數`

### static/index.html / static/style.css
- 共用既有 faction action modal 結構與霧面玻璃樣式
- 額外顯示 reward hint：
  - 猜中可獲得 2 點宣傳與 2 點資金；沒猜中則獲得 2 點宣傳。

## 驗證
新增：
- `scripts/validate_ethnic_ritual_ui_and_engine.py`

輸出：
- `ETHNIC_RITUAL_UI_AND_ENGINE_VALIDATION.json`
- `ETHNIC_RITUAL_UI_AND_ENGINE_VALIDATION.md`

### 驗證結果
- total: 3
- passed: 3
- failed: 0

已涵蓋：
- engine 結算成功
- 猜中資源獎勵正確
- UI panel 顯示成功
- modal 顯示成功

## 目前剩餘缺口
- 印度研究分析室
- 共用組織進一步整合到控制 / 勝利條件 / map 顯示
- 非暴力更深層的持有 / 得牌限制
