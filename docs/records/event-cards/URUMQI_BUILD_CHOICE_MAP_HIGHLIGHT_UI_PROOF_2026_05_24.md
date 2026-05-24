# 烏魯木齊事件可建城鎮地圖提示 UI Proof（2026-05-24）

Status: passed

## Scenario
- 使用 `/test/setup-urumqi-event-proof` 建立正式遊戲狀態。
- `烏魯木齊七五事件` 成功結算後產生 `event_build_organization` 的 `town_choice`。
- 正式 browser UI 連線到該遊戲，開啟原本的 pending choice modal 與戰略地圖 iframe。

## Verified evidence
- Pending choice: `type=town_choice`, `choice_key=event_build_organization`。
- Choice towns: `天津`, `石家莊`。
- Modal hint: `地圖會同步高亮可以建立組織的城鎮；主操作仍以此處列表為準。你也可以切到「戰略地圖」查看城鎮位置、連線與控制資訊。`
- Map iframe hint: `地圖上已用橘色外框標出可選城鎮。`
- Map connected: true。
- Orange choice circle markers in iframe: 4（兩個城鎮各外框與中心點）。

## Screenshots
- Modal proof: `URUMQI_BUILD_CHOICE_MAP_HIGHLIGHT_MODAL_UI_2026_05_24.png`
- Map proof: `URUMQI_BUILD_CHOICE_MAP_HIGHLIGHT_MAP_UI_2026_05_24.png`
