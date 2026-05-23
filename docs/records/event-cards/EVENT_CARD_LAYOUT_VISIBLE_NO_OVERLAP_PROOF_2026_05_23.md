# Event Card Layout Visible No-Overlap Proof — 2026-05-23

## Scenario

- Endpoint: `POST /test/setup-event-card-proof`
- Event: `香港抗暴之戰`
- Browser URL: `http://127.0.0.1:8000/?v=event-visible-fix-3`
- Action: clicked `結束目前步驟` once to draw/show the event during EVENT phase.

## Fix verified

- `#eventCardPanel` is mounted at the global stage level near `#phaseActionBar`, not inside `#commandView`, so it is not clipped by command view overflow.
- Stylesheet URL now includes a cache-busting query so clients load the corrected layout CSS.
- The current-event panel is visible above the card grid and does not overlap hand or purchase cards.
- The phase button remains centered.

## Browser-measured evidence

- Loaded stylesheet: `/static/style.css?v=event-panel-visible-20260523`.
- Event panel display/visibility: `block` / `visible`.
- Event panel bounding box: `left≈844`, `top≈153`, `right≈1125`, `bottom≈230`.
- Earliest card top: `≈256`; card overlap list: `[]`.

## Screenshot

- `docs/records/event-cards/EVENT_CARD_LAYOUT_VISIBLE_NO_OVERLAP_UI_2026_05_23.png`
