# Redline TODO

最後更新：2026-09-06

本文件只保留尚未完成的工作。已完成內容請查閱 Git history、`CHANGELOG.md` 與 `docs/records/`。

## 待辦

### P2：Repository 與 validator hygiene
- [todo] 維持 repository root 的 record-like 檔案數量為 0。
- [todo] Validation reports、proof Markdown 與 screenshots 必須放在 `docs/records/<topic>/`。
- [todo] 新增 validator 時，確認輸出路徑不是 repository root，且失敗時回傳非零 exit code。

## 工作規則
- 開始新工作前先讀本文件，並執行 `git status --short --branch` 與 `git log --oneline -5`。
- 同一時間只保留一個 `in_progress`。
- 完成項目後，從本文件移除。
- 歷史證據放在 `docs/records/<topic>/`，不要放在 repository root。
- UI 變更必須使用正式 Browser UI screenshot proof。
- 事件卡與常設牌互動時，遵守 static supply。`宣傳家`、`思想家`、`資助者`、`資本家`、`分神`、`內鬥` 等固定購買牌不可憑空新增。

## 接手注意事項
- 不要重做情報網 target-choice map highlight。事件卡需要目標選擇時，重用既有 pending choice 與 map highlight 架構。
- 事件卡 validator 與 proof records 放在 `docs/records/event-cards/`。
- 處理奧援卡前，先確認卡名與級別。不要用北國奧援 I 級規則推測 II 級。
