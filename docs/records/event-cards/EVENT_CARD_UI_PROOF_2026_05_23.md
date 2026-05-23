# Event Card UI Proof — 2026-05-23

Scenario endpoint: `POST /test/setup-event-card-proof` with `event_name=香港抗暴之戰`.

Live UI proof screenshot:

- `EVENT_CARD_HONG_KONG_UI_2026_05_23.png`

Verified visible state:

- Current event: `香港抗暴之戰`
- Type/status: `任務｜進行中`
- Condition: `打出購買費用含資金的卡牌至少 1 次`
- Progress: `0/1`
- Success reward: `獲得 2 張宣傳家`
- Failure penalty: `己方選 1 張手牌棄掉`
- Surrounding UI: `回合 1`、`事件階段`、`當前玩家 viewer`、`牌庫模式 全部卡牌`、`結束事件階段` button visible.

Browser console state check from original UI:

```text
document.getElementById('eventCardContent').innerText
香港抗暴之戰
類型：任務｜狀態：進行中
任務條件：打出購買費用含資金的卡牌至少 1 次
進度：0/1
成功獎勵：獲得 2 張宣傳家
失敗懲罰：己方選 1 張手牌棄掉
```
