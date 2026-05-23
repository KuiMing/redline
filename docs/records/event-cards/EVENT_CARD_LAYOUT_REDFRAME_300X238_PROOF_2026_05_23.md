# Event Card Layout Redframe 300x238 Proof — 2026-05-23

## Scenario

- Endpoint: `POST /test/setup-event-card-proof`
- Event: `香港抗暴之戰`
- Browser URL: `http://127.0.0.1:8000/?v=event-redframe-4`
- Action: clicked `結束事件階段` once to draw/show the event during EVENT phase.

## Requested layout

- Restore current-event panel to the right-top layout size: CSS `width: 300px`, `height: 238px`.
- Move it to the upper-right empty area indicated by the user's red-frame annotation.
- Keep the panel mounted at the global stage level so it is not clipped by `#commandView` overflow.

## Browser-measured evidence

- Loaded stylesheet: `/static/style.css?v=event-panel-redframe-20260523b`.
- Event panel display/visibility: `block` / `visible`.
- Event panel CSS size: `width=300px`, `height=238px`.
- Event panel rendered bounding box after stage scale: `left≈918`, `top≈44`, `right≈1182`, `bottom≈253`, `width≈264`, `height≈209`.
- Card overlap count: `0`.
- The phase button remains centered and is not covered by the event panel.

## Screenshot

- `docs/records/event-cards/EVENT_CARD_LAYOUT_REDFRAME_300X238_UI_2026_05_23.png`
