# Map Integration Status

## Current canonical path

Main UI map tab now uses:

- `iframe#strategicMapFrame`
- `src=/static/leaflet_game_map.html?gameId=...&playerId=...`

This is the current stable path because it preserves the standalone map rendering while still allowing direct game-engine communication.

## Current data / action flow

- Main UI handles room / join / start flow.
- `app.js` sets the iframe URL with `gameId` + `playerId` query params.
- `leaflet_game_map.html` connects to the game websocket directly from inside the iframe.
- Map interactions (select / highlight / move) happen inside the iframe page.

## Deprecated / non-canonical paths

These files/paths are no longer the preferred main UI integration route:

- `static/leaflet_game_map_embed_fragment.html`
- old same-page embedded map mounting approach
- earlier `leaflet_embed_logic.js` path

Keep them only until final cleanup confirms nothing references them.
