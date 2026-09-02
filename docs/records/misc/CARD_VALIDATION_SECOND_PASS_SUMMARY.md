# CARD VALIDATION SECOND PASS SUMMARY

日期：2026-05-03

## 本輪修正

- 修正 `scripts/validate/validate_all_action_cards.py` 中對出牌索引的錯誤假設。
- 先前腳本直接打最後一張牌，導致像 `高效行動` 這種會在手牌中插入額外測試牌的情況，驗證結果失真。
- 現在改成：按卡名精準找到待測卡，再呼叫 `play_card(index)`。

## 第二輪驗證結果

- 40/40 張 action card `play_success`
- 40/40 張 action card `card_left_hand`
- 第一輪標記的 `高效行動` 問題，確認是驗證腳本問題，不是卡牌執行邏輯 bug。

## 目前可聲稱的範圍

在目前 **MVP 規則語義** 下：

> 40 張 action card 已全部通過第二輪基礎可執行驗證。

這句話的邊界是：
- 是「可執行驗證」
- 不是最終規則完稿驗收
- 若之後對 build / move / dissolve / cancel 等語義做更細規則化，仍需再做規則級回歸驗證

## 下一步

1. 整理逐張卡牌驗證報表為通過清單
2. 補做主頁/多人情境下的卡牌 UI 驗證
3. 開始清理測試期遺留的暫時語義與強制 era 狀態
