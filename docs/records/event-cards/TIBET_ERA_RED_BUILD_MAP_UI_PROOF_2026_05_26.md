# 藏國時代關卡：紅軍棄牌後地圖建組織 UI proof（2026-05-26）

- 狀態：passed
- 場景：`[藏國]藏國騷亂` 紅軍壓制效果觸發後，紅軍先棄 1 張手牌，再進入 `era_red_build_near_target` pending town choice。
- 截圖：`TIBET_ERA_RED_BUILD_MAP_UI_2026_05_26.png`

## 驗證重點

- `era_red_build_near_target` 重用既有 `pending_choice` / `support-targets` / 戰略地圖側欄建立組織流程。
- 沒有重做情報網 target choice map highlight。
- 正式 browser UI 的戰略地圖中，可選城鎮以橘色高亮顯示：`加德滿都`、`博卡拉`、`日喀則`。
- 地圖提示顯示：`選擇要免費建立紅軍組織的城鎮`，並指示玩家點選橘色城鎮後使用側欄「在目前城鎮建立組織（效果）」完成。
- 透過側欄直接建組織流程 resolve 後，`pending_choice=None`，紅軍在 `加德滿都` 增加 1 個組織，且棄牌堆保留 `紅軍棄牌 UI proof`。

## State proof 摘要

```json
{
  "status": "passed",
  "before": {
    "current_player": "紅軍",
    "hand_count": 0,
    "discard": ["紅軍棄牌 UI proof"],
    "pending_choice_key": "era_red_build_near_target",
    "pending_choice_type": "town_choice",
    "pending_towns": ["加德滿都", "博卡拉", "日喀則"],
    "map_hint": "[藏國]藏國騷亂：[藏國]藏國騷亂：選擇要免費建立紅軍組織的城鎮。 地圖上已用橘色外框標出可選城鎮。請點選橘色城鎮，然後使用左側「在目前城鎮建立組織（效果）」按鈕完成建立。"
  },
  "action": {
    "via": "strategic_map_sidebar_direct_build_button",
    "town": "加德滿都",
    "result": {"ok": true, "eventChoice": true, "index": 0}
  },
  "after": {
    "pending_choice": null,
    "red_orgs": {"北京": 1, "加德滿都": 1},
    "red_discard": ["紅軍棄牌 UI proof"]
  }
}
```
