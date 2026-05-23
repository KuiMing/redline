# Event Card Layout Proof — 2026-05-23

## Scenario

- Endpoint: `POST /test/setup-event-card-proof`
- Event: `香港抗暴之戰`
- Browser URL: `http://127.0.0.1:8000/`
- Action: clicked `結束目前步驟` once to draw/show the event during EVENT phase.

## Verified UI Layout

- `#eventCardPanel` is rendered as the current-event block at the upper-right of the command view.
- `#advanceStepBtn` shows `結束事件階段` and is horizontally centered in the phase action bar.

## Browser-measured evidence

- Event panel bounding box: `left≈928`, `top≈228`, `width≈264` in the 1280px viewport.
- Advance button center: `640` in the 1280px viewport.

## Screenshot

- `docs/records/event-cards/EVENT_CARD_LAYOUT_TOP_RIGHT_UI_2026_05_23.png`
