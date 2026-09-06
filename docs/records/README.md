# docs/records 導覽

這份文件是給接手這個專案的工程師或 Agent 看的：`docs/records/` 底下的驗證紀錄怎麼找、
怎麼讀、新紀錄該放哪裡。一般玩家或部署者請直接看根目錄的 [`README.md`](../../README.md)。

## 接手前先看哪裡

如果你是下一個接手的人，先讀這幾個地方：

1. `README.md`
   - 看專案結構、紀錄檔規則、目前紀錄放哪裡。
2. `docs/records/<topic>/`
   - 看你現在要接的任務主題，例如 `purchase/`、`safehouse/`、`shared-actions/`、`support-cards/`、`leak-card/`。
3. 對應驗證腳本 `scripts/validate/validate_*.py`
   - 確認該 topic 的紀錄是不是由腳本直接產出，避免人工搬運造成路徑漂移。

## 怎麼看目前做到哪

優先看「最新狀態 / 驗證摘要」類文件：

- `docs/records/purchase/PURCHASE_ALIGNMENT_STATUS_2026_05_10.md`
- `docs/records/leak-card/LEAK_CARD_COMMIT_SCOPE.md`
- `docs/records/shared-actions/HU_SHARED_AND_WIN_VALIDATION.md`
- `docs/records/shared-actions/NEGOTIATION_CARD_VALIDATION.md`
- `docs/records/shared-actions/SHARED_VICTORY_PHASE8_VALIDATION.md`
- `docs/records/shared-actions/VICTORY_RULES_VALIDATION.md`
- `docs/records/card-ui/CARD_UI_VALIDATION_RESULTS.md`
- 各 topic 下面最新的 `*_VALIDATION.md`
- 各 topic 下面的 `*_COMMIT_SCOPE.md`

判讀原則：

- `*_STATUS_*.md`：看目前修到哪、怎麼驗、結論是什麼。
- `*_VALIDATION.md`：看人工可讀摘要。
- `*_VALIDATION.json`：看機器可讀細節與量測值。
- `*_COMMIT_SCOPE.md`：看某次整理 / commit 想包含哪些檔。

## 如果要看更久之前的東西

請照這個順序追：

1. 先看對應 `docs/records/<topic>/`
   - 確認主題資料夾與最新驗證紀錄。
2. 再看該 topic 內的檔案
   - 優先看 `*_STATUS_*.md`、`*_COMMIT_SCOPE.md`、`*_VALIDATION.md`。
3. 如果要追輸出來源或重跑方式，再看對應 `scripts/validate/validate_*.py`
4. 如果還不夠，再看 git 歷史
   - `git log -- docs/records/<topic>/`
   - `git log -- README.md`
   - `git show <commit>`

## 已整理的 records 主題

目前 `docs/records/` 已依主題整理，常見 topic 包含：

- `leak-card/`：走漏風聲規則與 UI 指定目標驗證。
- `purchase/`：購買區、購買牌堆補牌、地下黨、常設 supply / remove-return 驗證。
- `layout-ui/`：手牌、底部黑區、主分頁與 HUD layout 驗證。
- `card-ui/`：卡牌呈現、卡片 HUD、行動卡流程驗證與 card UI battle-shot。
- `support-cards/`：奧援牌與區域支援牌 UI / runtime 驗證。
- `faction-ui/`：陣營選擇、臺灣/香港/蒙古/新疆/西藏等陣營 UI 截圖。
- `rebel/`：反抗者擴充、重建狀態與相關 UI 截圖。
- `shared-actions/`：共享組織、共享拆除、合作談判、共享勝利與勝利條件驗證。
- `safehouse/`：安全屋地圖 highlight / zoom / build range 驗證截圖。
- `lobby/`：多人 lobby、ready sync 與房間 UI 截圖。
- `map-ui/`：Leaflet / strategic map UI 截圖。
- `setup-ui/`：初始基地選擇與 setup 規則 UI 截圖。
- `design/`：設計規格與參考資料。
- `debug-screenshots/`：重跑、console、除錯用畫面證據。
- `misc/`：尚未能明確歸類但需要保留的紀錄。

## 記錄檔整理規則

驗證與截圖檔案請優先放進 `docs/records/<topic>/`：

- 驗證報告：`docs/records/<topic>/*_VALIDATION.md`
- 機器可讀結果：`docs/records/<topic>/*_VALIDATION.json`
- 視覺證據截圖：`docs/records/<topic>/*.png`
- 提交/整理說明：`docs/records/<topic>/*_COMMIT_SCOPE.md`
- 狀態摘要：`docs/records/<topic>/*_STATUS_*.md`

臨時執行輸出不應提交：

- `server.log`
- `__pycache__/`
- Playwright 或手動除錯的中間截圖
- 沒有對應任務說明的 preview / battle-shot 圖片

## 近期已整理進 docs/records 的主題

- `docs/records/leak-card/`
- `docs/records/purchase/`
- `docs/records/safehouse/`
- `docs/records/setup-ui/`
- `docs/records/shared-actions/`
- `docs/records/support-cards/`

例如這批與購買區 / remove-return 相關的驗證，現在由下列腳本直接輸出到 `docs/records/purchase/`：

- `scripts/validate/validate_market_mode_and_removed_supply.py`
- `scripts/validate/validate_purchase_section_alignment.py`
- `scripts/validate/validate_underground_party.py`

共享勝利 / 合作談判 / 勝利條件相關驗證，現在直接輸出到 `docs/records/shared-actions/`：

- `scripts/validate/validate_negotiation_card.py`
- `scripts/validate/validate_hu_shared_and_win.py`
- `scripts/validate/validate_shared_victory_phase8.py`
- `scripts/validate/validate_victory_rules.py`

完整遊戲流程與 era 規則驗證，現在直接輸出到 `docs/records/misc/`：

- `scripts/validate/validate_full_gameplay_2p.py`
- `scripts/validate/validate_full_gameplay_multi.py`
- `scripts/validate/validate_era_rules.py`

卡牌 UI / 類型流程驗證，現在直接輸出到 `docs/records/card-ui/`：

- `scripts/validate/validate_ui_card_flows.py`

重跑驗證時，對應腳本應優先把輸出直接寫進各自的 `docs/records/<topic>/`；repo 根目錄目前不應再承接這些 validation report。
