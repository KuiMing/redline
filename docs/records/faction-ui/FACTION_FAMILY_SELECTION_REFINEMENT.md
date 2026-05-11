# FACTION_FAMILY_SELECTION_REFINEMENT

日期：2026-05-04

## 本輪修正

根據規則與使用者回饋，faction selection 不應把所有 variant 直接平鋪成平行陣營，而應先收斂成玩家感知上的主陣營，再讓玩家選擇其 variant / 根據地版本。

## 已實作

### server/main.py
`GET /factions` 現在除了原始 `factions` 外，還會額外回傳：
- `families`
- `singles`

其中：
- `families`：同名但不同 variant 的陣營，例如 維吾爾 / 西藏 / 臺灣
- `singles`：本來就是單一陣營的 faction

### static/app.js
faction picker 現在改成兩層：

#### 第一層
先列：
- 單一 faction
- faction family（例如 維吾爾 / 西藏 / 臺灣）

#### 第二層
當玩家點選 family 後，再顯示對應 variant：
- 維吾爾 → 伊斯坦堡 / 慕尼黑 / 華盛頓 / 阿拉木圖
- 西藏 → 達蘭薩拉 / 德拉敦 / 哲古宗
- 臺灣 → 綠線 / 藍線

## 截圖驗證

已產生並傳送：
- `faction_family_ui.png`

## 目前結果

玩家感知上的開局流程現在更接近正確規則：
- 先選主陣營
- 再選其版本 / 根據地版本
