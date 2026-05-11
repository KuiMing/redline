# FACTION_CATEGORY_UI_REFINEMENT

日期：2026-05-04

## 本輪修正

根據規則與使用者要求，陣營選擇頁第一層現在只顯示 9 個主陣營：

1. 紅軍
2. 臺灣
3. 香港
4. 維吾爾
5. 西藏
6. 滿洲
7. 蒙古
8. 哈薩克
9. 反賊

## 已實作

### server/main.py
- `GET /factions` 現在改為直接回傳 `categories`
- categories 已按玩家感知上的主陣營分組
- 並標記 mode：
  - `direct`
  - `variant`
  - `base_selection_family`

### static/app.js
- faction picker 第一層現在只顯示主陣營 categories
- 維吾爾 / 西藏 / 臺灣 / 反賊 會在第二層再顯示其細項
- 第一層主陣營仍受唯一性限制（不能被多位玩家重複選）

## 截圖驗證

已產生並傳送：
- `faction_main_categories.png`

## 結果

主頁 faction 選擇 UI 現在更貼近規則：
- 第一層只顯示主陣營
- 不再直接把所有內部 faction id 平鋪在第一層
