# Records

這裡放任務導向的驗證紀錄、提交範圍與視覺證據。

## 命名建議

- 每個任務一個資料夾：`docs/records/<topic>/`
- 驗證報告：`*_VALIDATION.md`
- 機器可讀結果：`*_VALIDATION.json`
- 截圖證據：使用能描述 UI 狀態的檔名，例如 `leak_card_target_modal.png`
- 提交範圍：`*_COMMIT_SCOPE.md`

## 已整理資料夾

- `leak-card/`：走漏風聲規則與 UI 指定目標驗證。
- `purchase/`：購買區、購買牌堆補牌與對齊驗證。
- `layout-ui/`：手牌、底部黑區、主分頁與 HUD layout 驗證。
- `card-ui/`：卡牌呈現、卡片 HUD 與卡牌 UI battle-shot。
- `support-cards/`：奧援牌與區域支援牌 UI / runtime 驗證。
- `faction-ui/`：陣營選擇、臺灣/香港/蒙古/新疆/西藏等陣營 UI 截圖。
- `rebel/`：反抗者擴充、重建狀態與相關 UI 截圖。
- `shared-actions/`：共享組織、共享拆除與共用互動驗證。
- `safehouse/`：安全屋地圖 highlight / zoom 驗證截圖。
- `lobby/`：多人 lobby、ready sync 與房間 UI 截圖。
- `map-ui/`：Leaflet / strategic map UI 截圖。
- `setup-ui/`：初始基地選擇與 setup 規則 UI 截圖。
- `design/`：設計規格與參考資料。
- `debug-screenshots/`：重跑、console、除錯用畫面證據。
- `misc/`：尚未能明確歸類但需要保留的紀錄。

## 不放這裡的東西

- 正式遊戲資料：放 `data/`。
- 正式前端資產與程式：放 `static/`。
- 可重跑的驗證/產生腳本：放 `scripts/`。
- 暫存 log、cache、無任務脈絡的 root-level screenshot：不要提交。
