# Safehouse — 被動能力不該有專屬按鈕（Validation）

Generated at: `2026-08-09T21:07:29`

Summary: 4 passed / 0 failed / 4 total.

## Scope
- 安全屋在 `data/factions/all_faction.integrated.v2.json` 是 `type: "passive"`，
  只該在玩家用正常方式（打出帶 `build` 效果的行動卡）建立組織時，把牆內目標的
  可建立距離 +1；不該有自己的按鈕、面板或地圖捷徑。
- 負面驗證：開局（行動階段、未出任何牌）指揮中心沒有「支援建立」面板、沒有任何
  安全屋字樣的可點擊元素；戰略地圖沒有安全屋專屬高亮，點 2 格外的牆內城鎮不會建組織。
- 正面驗證：以香港城根據地打出「組織經驗丙」（`build` range 1）後，候選清單仍包含
  1 格內的牆內城鎮與 2 格外的牆內城鎮（廣州／沙田等），並且實際建得起來。

## no_safehouse_button_at_game_start_base_臺北 — passed

- screenshot: `docs/records/safehouse/safehouse-no-button-at-game-start-臺北.png`

## no_safehouse_button_at_game_start_base_香港城 — passed

- screenshot: `docs/records/safehouse/safehouse-no-button-at-game-start-香港城.png`

## map_has_no_safehouse_build_shortcut — passed

- screenshot: `docs/records/safehouse/safehouse-map-no-shortcut.png`

## card_triggered_build_still_offers_two_step_inner_town — passed

- screenshot: `docs/records/safehouse/safehouse-card-build-choice-includes-two-step-inner.png`
- 卡牌建立候選城鎮: ['九龍城', '廣州', '柴灣', '沙田', '油尖旺', '澳門', '葵青', '西貢', '觀塘', '赤柱', '赤臘角']
