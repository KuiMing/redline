# SUPPORT_CARD_EFFECTS_UI_RUNTIME_BATCH2_2026_05_08

日期：2026-05-08

## 本輪完成

將第二批奧援卡 runtime 驗證延伸到主畫面真實 play_card 截圖，並透過 Telegram 直接交付。

## 截圖情境
### 1. 東洋奧援
- faction: `federalists`
- orgs: `東京` + `北京`
- 實測結果：tier 1
- matched rulers: none
- log：`player resolved 東洋奧援 at tier 1 (matched rulers: none)`

### 2. 北國奧援
- faction: `federalists`
- orgs: `東京`
- 實測結果：tier 2
- matched rulers: `東洋`
- log：`player resolved 北國奧援 at tier 2 (matched rulers: 東洋)`

### 3. 臺灣奧援
- faction: `federalists`
- orgs: `莫斯科`
- 實測結果：tier 1
- matched rulers: none
- log：`player resolved 臺灣奧援 at tier 1 (matched rulers: none)`

## 產物
- `SUPPORT_CARD_EFFECTS_UI_BATTLESHOT_BATCH2.json`
- `east_asia_support_tier1_play.png`
- `northland_support_tier2_play.png`
- `taiwan_support_tier1_play.png`

## 備註
- 截圖已依使用者偏好直接透過 Telegram 傳送
- 本輪真實截圖中，東洋奧援實際落在 I 級，不是先前測試腳本的 build 型分支
- 這也代表下一步若要驗東洋奧援 II / III，應另外設計更精準的 ruler / 城鎮配置場景
