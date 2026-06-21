# Playtest Targeted Browser Regression

- passed: True
- summary: 8/8 checks passed
- console_error_count: 0

## Checks
- [x] 常設購買區供應依 CSV 初始值，購買後卡片仍在且 UI 使用 live supply
- [x] 宣傳家行動不出現誘導虛耗，回歸供應、建立組織、給 1 移動
- [x] 奧援卡 ACTION 階段可行動；資源模式不給資源；行動模式才觸發效果
- [x] 乘勝追擊行動後開啟從己方棄牌堆選擇 3 點以下牌加入手牌
- [x] 隨機購買區購買北國奧援後原 slot 立即移除/補牌
- [x] 東突厥集中營非紅軍任務失敗後隨機棄非紅軍手牌
- [x] 紅軍能力執行完後面板/視窗收起不擋購買區
- [x] 後期回合沒有 pending_choice / 前端 gating 阻斷開始購買階段（完整 UI playthrough 證據）

## Screenshots
- /Users/benmini/.openclaw/workspace/redline/docs/records/playtest-feedback/targeted-browser-20260621_140716/01_static_supply_after_buy.png
- /Users/benmini/.openclaw/workspace/redline/docs/records/playtest-feedback/targeted-browser-20260621_140716/02_propagandist_action.png
- /Users/benmini/.openclaw/workspace/redline/docs/records/playtest-feedback/targeted-browser-20260621_140716/03_support_resource_noop.png
- /Users/benmini/.openclaw/workspace/redline/docs/records/playtest-feedback/targeted-browser-20260621_140716/04_support_action_effect.png
- /Users/benmini/.openclaw/workspace/redline/docs/records/playtest-feedback/targeted-browser-20260621_140716/05_press_advantage_choice.png
- /Users/benmini/.openclaw/workspace/redline/docs/records/playtest-feedback/targeted-browser-20260621_140716/06_random_support_purchase_refill.png
- /Users/benmini/.openclaw/workspace/redline/docs/records/playtest-feedback/targeted-browser-20260621_140716/07_east_turkestan_failure_discard.png
- /Users/benmini/.openclaw/workspace/redline/docs/records/playtest-feedback/targeted-browser-20260621_140716/08_red_army_ability_collapsed.png
