# 抽牌紀錄觀看者隱私 Browser 驗證

Summary: **8/8 passed**

- 哈薩克本人可看見自己抽到的牌名。
- 紅軍與第三位玩家只看見抽牌張數。
- Proof 中的憑證與識別碼均為 `[REDACTED]`。

## PASS — drawing_player_sees_exact_card_names

```json
{
  "owner_log": "[Turn 1] 哈薩克 因時代關卡效果抽到：追隨者、樂捐者"
}
```

## PASS — red_army_log_sees_count_without_card_names

```json
{
  "red_log": "[Turn 1] 哈薩克 因時代關卡效果抽了 2 張牌"
}
```

## PASS — third_player_log_sees_count_without_card_names

```json
{
  "observer_log": "[Turn 1] 哈薩克 因時代關卡效果抽了 2 張牌"
}
```

## PASS — red_army_peer_notice_does_not_leak_card_names

```json
{
  "notice": "哈薩克 因時代關卡效果抽了 2 張牌"
}
```

## PASS — third_player_peer_notice_does_not_leak_card_names

```json
{
  "notice": "哈薩克 因時代關卡效果抽了 2 張牌"
}
```

## PASS — drawing_players_own_turn_has_no_peer_overlay

```json
{
  "display": "none"
}
```

## PASS — private_hand_projection_matches_log_privacy

```json
{
  "red_view": [
    "未知手牌",
    "未知手牌"
  ],
  "owner_view": [
    "追隨者",
    "樂捐者"
  ],
  "observer_view": [
    "未知手牌",
    "未知手牌"
  ]
}
```

## PASS — browser_console_has_no_errors

```json
[]
```
