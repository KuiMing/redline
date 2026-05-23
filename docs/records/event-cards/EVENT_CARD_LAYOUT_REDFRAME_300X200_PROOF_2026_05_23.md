# Event Card Layout Redframe 300x200 Proof — 2026-05-23

## Scenario

- Endpoint: `POST /test/setup-event-card-proof`
- Event: `香港抗暴之戰`
- Browser URL: `http://127.0.0.1:8000/?v=event-panel-h200`
- Action: clicked `結束事件階段` once to draw/show the event during EVENT phase.

## Requested layout

- Keep the current-event panel in the red-frame upper-right location.
- Change event panel CSS height from 238px to 200px for visual review.
- Keep width at 300px.

## Browser-measured evidence

- Loaded stylesheet: `/static/style.css?v=event-panel-h200-20260523`.
- Event panel display/visibility: `block` / `visible`.
- Event panel CSS size: `width=300px`, `height=200px`, `max-height=200px`.
- Event panel rendered bounding box after stage scale: `left≈918`, `top≈44`, `right≈1182`, `bottom≈219`, `width≈264`, `height≈176`.
- Card overlap count: `0`.
- The phase button remains centered and is not covered by the event panel.

## Screenshot

- `docs/records/event-cards/EVENT_CARD_LAYOUT_REDFRAME_300X200_UI_2026_05_23.png`
