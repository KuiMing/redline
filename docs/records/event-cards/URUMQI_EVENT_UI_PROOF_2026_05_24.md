# 烏魯木齊七五事件 UI Proof — 2026-05-24

Status: passed

## Scope
- Event: `烏魯木齊七五事件`
- Raw 對齊重點：回合結束時牆內有己方組織；成功後免費在己方組織 1 格內建立 1 個組織。
- UI 原則：重用既有 `pending_choice` / `town_choice` modal；未重做情報網 target-choice map highlight。

## Proof screenshots
- Choice modal: `docs/records/event-cards/URUMQI_EVENT_CHOICE_UI_2026_05_24.png`
  - 可見 `烏魯木齊七五事件：在己方組織 1 格內免費建立 1 個組織。`
  - 可選城鎮：`天津`、`石家莊`
- Resolved panel: `docs/records/event-cards/URUMQI_EVENT_RESOLVED_UI_2026_05_24.png`
  - 可見事件面板：`狀態：成功已結算`
  - 可見進度：`1/1`
  - 可見 `viewer 組織 2`

## Runtime/UI state evidence
- `pending_choice.type`: `town_choice`
- `pending_choice.choice_key`: `event_build_organization`
- `pending_choice.towns`: `天津`, `石家莊`
- Resolved town: `天津`
- Viewer organizations after resolve: `北京: 1`, `天津: 1`
- Action log: `[Turn 1] viewer built organization in 天津 via event`

## Related validator
- `scripts/validate_event_cards_runtime.py`
  - `test_urumqi_end_turn_wall_org_builds_near_own_org`
  - `test_urumqi_end_turn_without_wall_org_fails_random_discard`
  - `test_urumqi_structured_matches_raw_rule`
