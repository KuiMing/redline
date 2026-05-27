# Hong Kong Era Notification UI Proof — 2026-05-27

## Scope

補齊 `[香港]香港人被自殺` 時代關卡達成大彈窗的人類可讀文字，避免前端 fallback 顯示 `（暫缺）`。

## Browser UI proof

- URL: `http://127.0.0.1:8000/?game_id=3d0a7827-b742-45c6-94b3-ec82b77c6380&player_id=dab409f7-04b1-40e9-9ad7-3667ccf5f83d`
- Screenshot: `docs/records/event-cards/HONG_KONG_ERA_NOTIFICATION_UI_PROOF_2026_05_27.png`
- Browser snapshot showed:
  - `時代關卡達成`
  - `達成條件：[香港抗爭遍地開花]香港在牆內擁有至少10個有效組織`
  - `紅軍壓制` / `[新型態的血腥鎮壓]紅軍每次對香港使用間諜類卡牌時，可再隨機棄掉香港1張手牌。持續2回合。`
  - `革命反撲` / `[沉冤待雪香港報仇]香港購買每張武裝類卡牌之費用額外減少2點資金。持續2回合。`
  - `效果期限：持續 2 回合｜剩餘 2 回合`

## State / console evidence

- `window.lastGameState` present: `true`
- `document.body.innerText.includes("暫缺")`: `false`
- `contains_missing_placeholder`: `false`
- `era_notification.trigger_text`: `[香港抗爭遍地開花]香港在牆內擁有至少10個有效組織`
- `era_notification.success_text`: `[新型態的血腥鎮壓]紅軍每次對香港使用間諜類卡牌時，可再隨機棄掉香港1張手牌。持續2回合。`
- `era_notification.fail_text`: `[沉冤待雪香港報仇]香港購買每張武裝類卡牌之費用額外減少2點資金。持續2回合。`
- `era_notification.duration_text`: `持續 2 回合`

## Notes

Vision analysis hit provider usage limit (429), but the screenshot was still captured from the official browser UI and paired with browser snapshot / console state evidence.
