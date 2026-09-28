# Redline TODO

最後更新：2026-09-28

本文件只保留尚未完成的工作。已完成內容請查閱 Git history、`CHANGELOG.md` 與 `docs/records/`。

## 待辦

### 爆料黑幕：任一取消成立後關閉其他反應視窗

- 情境：至少兩名玩家持有「爆料黑幕」，第三名玩家使用卡牌或能力，並同時觸發兩名玩家的取消反應選擇。
- 預期：任一玩家使用「爆料黑幕」成功取消該卡牌或能力後，系統立即結束同一反應批次。
- 預期：其他仍在等待的「爆料黑幕」選擇視窗立即消失，不得繼續選擇或打出該牌。
- 驗收：驗證兩名反應者的同步狀態、待處理反應清除、取消效果只結算一次，以及換人後視窗不會再次出現。

## 工作規則
- 開始新工作前先讀本文件，並執行 `git status --short --branch` 與 `git log --oneline -5`。
- 同一時間只保留一個 `in_progress`。
- 完成項目後，從本文件移除。
- 歷史證據放在 `docs/records/<topic>/`，不要放在 repository root；維持 repository root 的 record-like 檔案數量為 0。
- 新增 validator 時，確認輸出路徑不是 repository root，且失敗時回傳非零 exit code。
- UI 變更必須使用正式 Browser UI screenshot proof。
- 事件卡與常設牌互動時，遵守 static supply。`宣傳家`、`思想家`、`資助者`、`資本家`、`分神`、`內鬥` 等固定購買牌不可憑空新增。

## 接手注意事項
- 不要重做情報網 target-choice map highlight。事件卡需要目標選擇時，重用既有 pending choice 與 map highlight 架構。
- 事件卡 validator 與 proof records 放在 `docs/records/event-cards/`。
- 處理奧援卡前，先確認卡名與級別。不要用北國奧援 I 級規則推測 II 級。
