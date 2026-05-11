# HU_FACTION_PICKER_UI_CHECK

日期：2026-05-06

## 檢查目標
重新檢查反賊陣營「滬」在 faction picker / UI 的顯示是否正確。

## 檢查方式
- 啟動本機 server
- 進入首頁 UI
- 建立房間並以 host 身分進入
- 選擇：
  - 類別：反賊
  - 派系：滬
  - 根據地：上海
- 擷取 detail panel 與 confirm 狀態
- 輸出截圖與 JSON

## 結果
### UI 文字
- info：`目前陣營：滬｜根據地：上海`
- title：`滬`
- bases：`根據地上海`
- abilities：`能力【商貿組織】當您每回合第1次打出購買費用含資金的牌時，抽1張牌。`
- rules：`規則遊戲過程中可與綠線臺灣共用組織。`
- win：`獲勝條件回合結束時在牆內與牆外共擁有至少13個有效組織，其中必須包含上海。`
- confirm_visible：`true`

### 產物
- `HU_FACTION_PICKER_UI_CHECK.json`
- `HU_FACTION_PICKER_UI_CHECK.md`
- `hu_faction_picker_ui.png`

## 結論
- 滬已出現在反賊 variant picker 中
- 選擇上海後，detail panel 會正確顯示：
  - 根據地
  - 商貿組織能力
  - 與綠線臺灣共用組織規則
  - 勝利條件
- confirm button 可正常顯示
