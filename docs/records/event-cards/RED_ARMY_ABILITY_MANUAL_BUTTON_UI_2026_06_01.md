# Red Army ability manual button UI proof — 2026-06-01

Scenario: deterministic `/test/setup-red-army-abilities-proof`, Red Army is current player before purchase/end flow.

Verified live browser state:

- Before click: `紅軍能力 0/2` button displayed (`display: flex`) and enabled.
- Before click: faction action modal was not auto-opened (`display: none`).
- After clicking the button: modal opened (`display: flex`) with title `紅軍能力`.
- Modal choices: `發動 統戰部`, `發動 政工部`, `發動 國安部`, `發動 中紀委`.

Screenshot: `docs/records/event-cards/RED_ARMY_ABILITY_MANUAL_BUTTON_UI_2026_06_01.png`

Note: browser vision analysis failed after capturing the original UI screenshot; the screenshot is preserved and paired with live DOM/state evidence above.
