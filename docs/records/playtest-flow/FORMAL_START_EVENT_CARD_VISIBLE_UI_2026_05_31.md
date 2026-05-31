# 正式開局事件卡顯示 UI proof — 2026-05-31

## 目的

確認正式 lobby `/start` 開局後，EVENT 階段會立即顯示目前事件卡。

## 流程

- `/create`
- `/join`
- host 選 `red_army`
- ally 選 `taiwan_green` / `臺北`
- 雙方 ready
- host `/start`
- ally 進入正式 browser UI

## 官方 UI 觀察

- URL: `http://127.0.0.1:8000/?game_id=a7b11a8d-cddc-4c97-92f6-5e598c2cf38c&player_id=ab747916-f028-4e9f-9bf5-5b65696e378d`
- turn_phase: `event`
- current_event: `貿易戰加劇`
- event panel display: `block`
- advance button: `開始購買階段`
- event panel text:

```text
目前事件
貿易戰加劇
類型：任務｜狀態：進行中
任務結果：非紅軍任務進行中
任務條件：購買符合條件的卡牌（總費用 4 點以上 / 英美奧援）至少 1 次
進度：0/1
成功獎勵：從棄牌堆選 1 張置於牌庫頂
失敗懲罰：無
```

## 截圖

- `docs/records/playtest-flow/FORMAL_START_EVENT_CARD_VISIBLE_UI_2026_05_31.png`

註：本次使用正式 browser UI 擷取原始截圖；vision analysis 在截圖後失敗，因此以 live DOM/state 搭配原始截圖作為證據。
