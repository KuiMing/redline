# Lobby scroll layout validation

- total: 4
- passed: 4
- failed: 0

## Checks
- ✅ `lobby_uses_vertical_scroll` — #lobby must allow vertical scrolling for tall faction setup/detail content.
- ✅ `lobby_keeps_horizontal_clip` — #lobby should still avoid horizontal spill while allowing vertical scroll.
- ✅ `lobby_scroll_contained` — Scroll gestures should stay inside the fixed 1280x720 lobby stage.
- ✅ `lobby_no_single_overflow_hidden_shorthand` — A single overflow:hidden on #lobby clips the faction picker bottom on smaller screens.
