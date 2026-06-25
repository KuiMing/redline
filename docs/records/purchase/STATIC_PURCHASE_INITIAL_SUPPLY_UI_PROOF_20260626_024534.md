# Static Purchase Initial Supply UI Proof

Generated: 2026-06-26 02:45:34

## Scenario

Formal 4-player lobby start:

- red_army / 北京
- hong_kong / 香港城
- tibet_family / 達蘭薩拉 → runtime `tibet_dharamsala`
- uyghur_family / 慕尼黑 → runtime `uyghur_munich`

Setup abilities add 5 total `宣傳家` to player discard piles, so the live static purchase supply should be `15 - 5 = 10`.

## Browser evidence

- URL: `http://127.0.0.1:8765/`
- Room: `f86e9e9b-4afb-43cb-b944-1a58515a6795`
- Header text:

```text
回合 1
事件階段
當前玩家 HK
手牌 5
資金 0
宣傳 0
移動 0
牌庫模式 53 張卡牌
```

## Visible static purchase card counts

- 宣傳家: `剩 10`
- 思想家: `剩 15`
- 資助者: `剩 15`
- 資本家: `剩 15`
- 分神: `剩 30`
- 內鬥: `剩 20`

A browser screenshot was captured in-session after WebSocket render and visually showed the same 常設購買區 counts, including `宣傳家` badge `剩 10`.
