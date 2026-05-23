# Event Card Layout No-Overlap Proof — 2026-05-23

## Scenario

- Endpoint: `POST /test/setup-event-card-proof`
- Event: `香港抗暴之戰`
- Browser URL: `http://127.0.0.1:8000/`
- Action: clicked `結束目前步驟` once to draw/show the event during EVENT phase.

## Verified UI Layout

- The `目前事件` panel is moved upward in the upper-right command area.
- It does not overlap hand cards or purchase-area cards.
- The `結束事件階段` button remains horizontally centered.

## Browser-measured evidence

- Event panel bounding box: `left≈911`, `top≈114`, `right≈1192`, `bottom≈205`.
- Earliest card top: `≈256`; card overlap list: `[]`.
- Advance button center: `640` in the 1280px viewport.

## Screenshot

- `docs/records/event-cards/EVENT_CARD_LAYOUT_NO_OVERLAP_UI_2026_05_23.png`
