# 烏魯木齊事件可建城鎮地圖提示 UI Proof（clean，2026-05-24）

Status: passed

## Scenario
- 使用 `/test/setup-urumqi-event-proof` 建立正式遊戲狀態，並以 `settle=true` 讓 `烏魯木齊七五事件` 成功結算。
- Proof endpoint 的 viewer 改用 `taiwan_green`，避免自由派 `立場試探` 文案混入事件卡地圖 proof。
- 正式 browser UI 連線後顯示原本 pending choice modal，並切到戰略地圖確認高亮提示。

## Verified evidence
- Pending choice: `type=town_choice`, `choice_key=event_build_organization`。
- Choice towns: `天津`, `石家莊`。
- Viewer faction: `taiwan_green`。
- Choice modal: 顯示 `烏魯木齊七五事件`，按鈕為 `天津` / `石家莊`。
- Modal hint: `地圖會同步高亮可以建立組織的城鎮；主操作仍以此處列表為準。你也可以切到「戰略地圖」查看城鎮位置、連線與控制資訊。`
- Faction action modal display: `none`；畫面流程沒有 `立場試探` modal 干擾。
- Map iframe hint: `地圖上已用橘色外框標出可選城鎮。`
- Map labels observed in iframe: `天津`, `石家莊`。

## Screenshots
- Modal clean proof: `URUMQI_BUILD_CHOICE_MAP_HIGHLIGHT_MODAL_UI_CLEAN_2026_05_24.png`
- Map clean proof: `URUMQI_BUILD_CHOICE_MAP_HIGHLIGHT_MAP_UI_CLEAN_2026_05_24.png`
