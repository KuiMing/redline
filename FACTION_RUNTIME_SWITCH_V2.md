# FACTION_RUNTIME_SWITCH_V2

日期：2026-05-05

## 本輪完成

runtime faction 載入路徑已切換到：
- `data/factions/all_faction.integrated.v2.json`

## 修改檔案

- `server/game.py`
  - `FACTIONS_PATH` 改讀 `all_faction.integrated.v2.json`
- `server/main.py`
  - `/factions` 改讀 `all_faction.integrated.v2.json`

## 驗證結果

### /factions API
- categories 維持 9 個主陣營：
  - 紅軍
  - 臺灣
  - 香港
  - 維吾爾
  - 西藏
  - 滿洲
  - 蒙古
  - 哈薩克
  - 反賊
- `rebel` 第二層選項數量：47
- 確認已包含：
  - 民運派
  - 改革開放派
  - 法輪功
  - 性別革命
  - 幽燕
  - 朝鮮
  - 澳門

### Browser UI
- 已驗證主頁點選「反賊」後，第二層會列出 47 個反賊 faction
- 截圖：`rebel_selection_integrated_v2.png`

## 目前仍未完成

- 尚未驗證所有新反賊 faction 的 base selection 是否都能正確進入 `BASE_SELECTION`
- 尚未將新 rebel faction 的 abilities / win conditions 完整對齊既有 structured engine schema
- 尚未完成新整合 faction source 下的 2 / 3 / 4 人完整開局回歸驗證
