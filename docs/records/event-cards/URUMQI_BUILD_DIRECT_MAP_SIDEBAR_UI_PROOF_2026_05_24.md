# 烏魯木齊七五事件：事件建組織改用戰略地圖側欄 proof（2026-05-24）

- 狀態：passed
- 場景：`烏魯木齊七五事件` 成功後產生 `event_build_organization` pending town choice。正式 UI 自動切到 `戰略地圖`，玩家選取 `天津`，使用左側既有直接建組織操作區的「在目前城鎮建立組織（事件卡）」按鈕完成 resolve。
- 截圖：`URUMQI_BUILD_DIRECT_MAP_SIDEBAR_UI_2026_05_24.png`

## 驗證重點

- `event_build_organization` 不再使用 choice modal 兩段式確認。
- 只重用既有 pending choice / map highlight 架構；地圖側欄直接建組織按鈕對事件卡 choice 送出 `resolve_choice`。
- 按鈕前 state：`pending_choice=event_build_organization`，viewer 組織為 `{北京: 1}`。
- 按鈕文字／提示：`在目前城鎮建立組織（事件卡）`；提示顯示天津可因事件卡建立組織。
- 按鈕後 state：`pending_choice=None`，viewer 組織為 `{北京: 1, 天津: 1}`，事件面板顯示成功已結算，地圖可見 `天津 1`。

## State proof 摘要

```json
{
  "status": "passed",
  "scenario": "烏魯木齊七五事件 success 觸發 event_build_organization；在正式戰略地圖側欄選天津並用直接建組織按鈕 resolve。",
  "screenshot": "docs/records/event-cards/URUMQI_BUILD_DIRECT_MAP_SIDEBAR_UI_2026_05_24.png",
  "before": {
    "pending_choice": "event_build_organization",
    "viewer_orgs": {
      "北京": 1
    },
    "map_button": "在目前城鎮建立組織（事件卡）",
    "map_hint": "目前選取 天津：事件卡效果允許在此建立組織；按上方按鈕完成建立。"
  },
  "action": {
    "via": "strategic_map_sidebar_direct_build_button",
    "town": "天津",
    "result": {
      "ok": true,
      "eventChoice": true,
      "index": 0
    }
  },
  "after": {
    "pending_choice": null,
    "viewer_orgs": {
      "北京": 1,
      "天津": 1
    },
    "current_event_status": "success/settled",
    "visible_town_label": "天津 1"
  },
  "notes": [
    "event_build_organization 不再用 choice modal 兩段式確認；pending town choice 被導向正式戰略地圖。",
    "地圖側欄沿用既有直接建組織區塊，事件卡可建城鎮時按鈕文字改為「在目前城鎮建立組織（事件卡）」。",
    "iframe map state 會 postMessage 回主 UI，按下地圖側欄按鈕後主 UI state 同步為 pending_choice=None。"
  ]
}
```
