# Era HUD Row Clickable — Validation

Generated at: `2026-08-09T23:37:07`

Summary: 2 passed / 0 failed / 2 total.

## Scope
- 指揮中心／戰略地圖分頁上方的時代關卡提示列（`.hud-era-pill`）改為可點擊，
  點擊直接叫出該時代的完整說明；四人局最多 3 個時代關卡同時生效時，各自獨立可點。
- 連帶修正 `#phaseActionBar` 寫死 `top:90px` 蓋住多行 HUD 的既有 layout bug。

## three_simultaneous_eras_hud_row_each_independently_clickable — passed

- screenshot: `docs/records/era-restrict-ignore-distance/hud-row-three-eras.png`

## single_era_phase_action_bar_still_reachable — passed

