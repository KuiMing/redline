# SUPPORT_CARD_EFFECTS_UI_RUNTIME_2026_05_08

日期：2026-05-08

## 本輪完成

將奧援卡效果的 runtime 驗證延伸到主畫面真實 play_card 流程，並輸出 Telegram 截圖。

## 新增測試入口
### server/main.py
新增：
- `POST /test/setup-support-card-play`

用途：
- 建立單張奧援卡在手牌中的實戰情境
- 可指定 faction / base / orgs / support_name
- 直接進主畫面測試 play_card 路徑

## 截圖驗證情境
### 1. 印度奧援 III 級
- faction: `tibet_dehradun`
- orgs: `河內` + `紐約`
- matched rulers: `南洋` + `英美`
- tier: III
- log：
  - `player triggered 印度研究分析室 and gained 2 money`
  - `player resolved 印度奧援 at tier 3 (matched rulers: 南洋, 英美)`

### 2. 英美奧援 II 級
- faction: `federalists`
- orgs: `東京`
- matched ruler: `東洋`
- tier: II
- hud after: `MONEY 2`
- log：
  - `player resolved 英美奧援 at tier 2 (matched rulers: 東洋)`

### 3. 南洋奧援 I 級
- faction: `federalists`
- orgs: `北京`
- matched rulers: none
- tier: I
- log：
  - `player resolved 南洋奧援 at tier 1 (matched rulers: none)`

## 產物
- `SUPPORT_CARD_EFFECTS_UI_BATTLESHOT.json`
- `india_support_tier3_play.png`
- `anglo_support_tier2_play.png`
- `nanyang_support_tier1_play.png`

## 備註
- 截圖已依使用者偏好直接透過 Telegram 傳送
- 這一輪驗證的是主畫面 `play_card()` 路徑，不是僅 backend unit test
