# 一帶一路南洋 Map Build UI Proof — 2026-05-24

Status: passed

## Scope
- Event: `一帶一路 南洋`
- Runtime effect: `build_organization_in_region`
- Expected UI: reuse existing `event_build_organization` pending town choice / Strategic Map highlight flow.
- No fake DOM/CSS proof; screenshot was captured from the running browser UI.

## Evidence
- Screenshot: `docs/records/event-cards/BELT_ROAD_SOUTHEAST_MAP_BUILD_UI_2026_05_24.png`
- Browser setup: `POST /test/setup-event-card-proof {"event_name": "一帶一路 南洋"}`
- State proof:
  - `current_event.name`: `一帶一路 南洋`
  - `current_event.status`: `auto`
  - `pending_choice.choice_key`: `event_build_organization`
  - `pending_choice.player`: `red`
  - `pending_choice.region`: `southeast_asia`
  - `pending_choice.free`: `true`
  - `pending_choice.ignore_distance`: `true`
  - Sample selectable towns: `仰光`、`佬沃`、`吉隆坡`、`新加坡`、`曼谷`、`老街`、`芒賽`、`賀猛`、`邦康`、`雅加達`、`馬尼拉`

## Browser UI observation
The formal browser screenshot shows the active event panel for `一帶一路 南洋`, the Strategic Map tab/sidebar, and orange-highlight selectable towns in the 南洋 / Southeast Asia region. The sidebar prompt instructs the player to select an orange town and use the existing event build organization map action.
