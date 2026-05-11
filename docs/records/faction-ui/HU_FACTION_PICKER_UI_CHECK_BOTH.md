# HU_FACTION_PICKER_UI_CHECK_BOTH

日期：2026-05-06

## 檢查目標
重新檢查反賊陣營「滬」在 faction picker / UI 的兩個根據地分支：
- 上海
- 紐約

## 結果摘要
### 上海
- info：`目前陣營：滬｜根據地：上海`
- title：`滬`
- bases：`根據地上海`
- abilities：`能力【商貿組織】當您每回合第1次打出購買費用含資金的牌時，抽1張牌。`
- rules：`規則遊戲過程中可與綠線臺灣共用組織。`
- win：`獲勝條件回合結束時在牆內與牆外共擁有至少13個有效組織，其中必須包含上海。`
- confirm_visible：`true`

### 紐約
- info：`目前陣營：滬｜根據地：紐約`
- title：`滬`
- bases：`根據地紐約`
- abilities：`能力【商貿組織】當您每回合第1次打出購買費用含資金的牌時，抽1張牌。`
- rules：`規則遊戲過程中可與綠線臺灣共用組織。`
- win：`獲勝條件回合結束時在牆內與牆外共擁有至少13個有效組織，其中必須包含上海。`
- confirm_visible：`true`

## 產物
- `hu_faction_picker_ui_shanghai.png`
- `hu_faction_picker_ui_newyork.png`
- `HU_FACTION_PICKER_UI_CHECK_BOTH.json`
- `HU_FACTION_PICKER_UI_CHECK_BOTH.md`

## 結論
- 滬的兩個根據地分支都能正確顯示於 faction picker。
- 上海 / 紐約兩條路線的 detail panel 均正確顯示能力、共用組織規則與勝利條件。
