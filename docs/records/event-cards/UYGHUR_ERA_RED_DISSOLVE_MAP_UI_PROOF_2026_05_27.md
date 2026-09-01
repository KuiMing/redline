# Uyghur Era Red Dissolve Map UI Proof

- Date: 2026-05-27
- Scenario: 維吾爾時代關卡紅軍壓制：紅軍打出武裝者，既有武裝棄牌 pending choice 完成後，追加選擇 1 個紅軍組織 1 格內的維吾爾組織瓦解。
- Screenshot: `docs/records/event-cards/UYGHUR_ERA_RED_DISSOLVE_MAP_UI_2026_05_27.png`
- Validator: `python3 scripts/validate/validate_era_effects_runtime.py => 12/12 passed`

## Flow

- POST /test/setup-uyghur-era-red-dissolve-proof 建立正式 UI proof 場景。
- 紅軍玩家已打出武裝者；維吾爾玩家先透過既有 armed_target_discard 棄 1 張手牌。
- 系統接續建立 era_red_bonus_dissolve_target pending target choice。
- 正式 UI 切到戰略地圖 tab，modal 顯示「維吾爾｜天津」，地圖側欄提示橘色外框標出可選城鎮。

## State evidence

```json
{
  "active_tab": "戰略地圖",
  "pending_choice": {
    "choice_key": "era_red_bonus_dissolve_target",
    "type": "target_choice",
    "targets": [
      {
        "label": "維吾爾｜天津",
        "town": "天津"
      }
    ]
  },
  "players": [
    {
      "name": "維吾爾",
      "faction": "uyghur_istanbul",
      "organizations": {
        "天津": 1
      },
      "discard": [
        "維吾爾棄牌 UI proof"
      ]
    },
    {
      "name": "紅軍",
      "faction": "red_army",
      "organizations": {
        "北京": 1
      },
      "discard": [
        "武裝者"
      ]
    }
  ],
  "map_sidebar_text": "[維吾爾]莎車大屠殺：紅軍選擇 1 個維吾爾組織瓦解；地圖上已用橘色外框標出可選城鎮。"
}
```

## Note

此 proof 重用既有 pending target choice / support-targets map highlight 架構，沒有重做情報網 target choice map highlight。
