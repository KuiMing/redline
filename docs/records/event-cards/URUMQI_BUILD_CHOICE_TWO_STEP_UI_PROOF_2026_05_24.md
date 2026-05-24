# 烏魯木齊事件建立組織兩段式 UI Proof — 2026-05-24

Status: passed

## Scenario
- Endpoint: `POST /test/setup-urumqi-event-proof` with `{ "settle": true }`
- Event: `烏魯木齊七五事件`
- Pending choice: `type=town_choice`, `choice_key=event_build_organization`
- Candidate towns: `天津`, `石家莊`

## Verified UI flow
1. 正式 browser UI 連線到測試遊戲後，choice modal 顯示兩段式說明：先選城鎮並切到「戰略地圖」聚焦位置，確認後再建立組織。
2. 點 `先看地圖：天津` 後：
   - active tab 自動切到 `戰略地圖`。
   - modal 顯示 `第一段已在戰略地圖聚焦 天津`。
   - 按鈕狀態變為 `已聚焦：天津`、`先看地圖：石家莊`、`確認建立於 天津`。
   - iframe map hint 顯示已用橘色外框標出可選城鎮，並已聚焦天津。
3. 按 `確認建立於 天津` 後：
   - modal 關閉。
   - `pending_choice` 清空。
   - viewer 組織從 `北京: 1` 變為 `北京: 1, 天津: 1`。
   - current event 維持 `success` / progress `1/1` / settled `true`。

## Artifacts
- Screenshot: `docs/records/event-cards/URUMQI_BUILD_CHOICE_TWO_STEP_UI_2026_05_24.png`
- State/log JSON: `docs/records/event-cards/URUMQI_BUILD_CHOICE_TWO_STEP_UI_PROOF_2026_05_24.json`

## Notes
- 此流程重用既有 pending choice modal 與 `redline-choice-highlight` / `support-targets` map highlight 架構。
- 未重做情報網 target choice map highlight。
