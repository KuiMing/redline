# CARD P0 EFFECT IMPLEMENTATION

日期：2026-05-03

## 本輪已補上的 P0 effect type

已在 `server/effect_engine.py` 補上：

- optional_trash
- build
- move
- conditional_draw
- shared_draw

## 本輪採用的 MVP 語義

### optional_trash
- 目前採用 MVP 行為：若手上仍有牌，棄置（永久移除）最後一張手牌。
- 這是可執行語義，不是最終 UI 決策語義。

### build
- 目前採用 MVP 行為：優先在玩家 base 增建 1 組織；若 base 無組織，則找第一個已擁有組織的城鎮增建。

### move
- 目前採用 MVP 行為：視為增加 move points（`player.moves_left += count`），供地圖 / 行動階段後續消耗。

### conditional_draw
- 目前支援：
  - `played_propaganda_card`
  - `played_money_card`
  - `successful_discard`
  - `canceled_propaganda_card`（條件欄位已預留）

### shared_draw
- 目前行為：所有玩家各抽 `count` 張。

## 另外補的必要基礎

### `Game.play_card()`
- 現在會正確讀取 `Card` 物件的 `name`
- 並會更新：
  - `turn_log.played_money_card`
  - `turn_log.played_propaganda_card`

### `Player.reset_turn()`
- 現在會重置 `build_range_bonus`

## 補完後仍未實作的 effect type

- add_internal_conflict
- cancel_card
- conditional_bonus
- dissolve
- refresh_purchase_area
- trash_from_hand_or_discard

## 本輪快速驗證結果

### 資助者
- 打牌成功
- `optional_trash` + `gain_resource` 已實際生效
- resources 變成：`money=4`, `propaganda=2`

### 點燃熱情
- 先打 1 張 propaganda card 後
- `conditional_draw(played_propaganda_card)` 已生效
- 最後手牌可見多抽 2 張（1 張 draw + 1 張 conditional draw）

### 合作談判
- shared_draw 已生效
- host / guest 都有抽牌

### 組織經驗丙
- build 已生效
- 北京組織：`1 -> 2`

### 宣傳家
- move effect 已生效（目前語義 = 增加 move points）
- `moves_left: 3 -> 4`

## 重要限制

這一輪是 **P0 effect 可執行化**，不是最終規則完稿。
目前語義是為了讓卡牌功能從「資料存在但不可執行」提升到「可跑、可驗、可繼續擴充」。
