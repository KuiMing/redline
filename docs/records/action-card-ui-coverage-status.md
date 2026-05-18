# Action Card UI Coverage Status

更新時間：2026-05-18

## 判讀原則

- 有明確 UI/validator 證據：有專門 UI/E2E validator，或 validator 明確驗畫面/互動。
- 主要為 engine/規則 validator：有驗證腳本，但重點在規則/結果，不足以單獨證明整個 UI 流程完整。
- 需要 UI 互動，但缺少明確 UI validator 證據：卡牌效果明顯需要互動 UI，但目前 repo 中找不到對應專門 UI 驗證。
- 多半只需標準 action/resource UI：這類卡通常只要一般打出按鈕與狀態刷新，不一定需要額外 modal。

## 逐卡盤點

### 乘勝追擊
- 類型：command
- 預期 UI 需求：card_choice
- 目前判定：需要 UI 互動，但缺少明確 UI validator 證據
- 對應 validator：無明確對應
- app.js 訊號：pending_choice_ui_present

### 交通經驗丙
- 類型：transport
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 交通經驗乙
- 類型：transport
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 交通經驗甲
- 類型：transport
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 企業人脈
- 類型：money
- 預期 UI 需求：unknown
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 企畫遊說
- 類型：money
- 預期 UI 需求：unknown
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 內應間諜
- 類型：spy
- 預期 UI 需求：target_player
- 目前判定：需要 UI 互動，但缺少明確 UI validator 證據
- 對應 validator：無明確對應
- app.js 訊號：target_player_flow_present

### 內鬥
- 類型：disruption
- 預期 UI 需求：unknown
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：named_in_app_js

### 凝聚共識
- 類型：command
- 預期 UI 需求：multi_card_choice
- 目前判定：需要 UI 互動，但缺少明確 UI validator 證據
- 對應 validator：無明確對應
- app.js 訊號：pending_choice_ui_present

### 分神
- 類型：disruption
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 合作談判
- 類型：command
- 預期 UI 需求：target_player
- 目前判定：有明確 UI/validator 證據
- 對應 validator：scripts/validate_negotiation_card.py
- app.js 訊號：named_in_app_js, target_player_flow_present

### 地下黨
- 類型：spy
- 預期 UI 需求：card_choice
- 目前判定：需要 UI 互動，但缺少明確 UI validator 證據
- 對應 validator：無明確對應
- app.js 訊號：named_in_app_js, pending_choice_ui_present

### 宣傳家
- 類型：propaganda
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 思想家
- 類型：propaganda
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 思想建設
- 類型：command
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 情報網
- 類型：spy
- 預期 UI 需求：option_choice
- 目前判定：需要 UI 互動，但缺少明確 UI validator 證據
- 對應 validator：無明確對應
- app.js 訊號：pending_choice_ui_present

### 戰略
- 類型：command
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 批判
- 類型：purge
- 預期 UI 需求：unknown
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 批鬥
- 類型：purge
- 預期 UI 需求：unknown
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 擴大戰果
- 類型：command
- 預期 UI 需求：card_choice
- 目前判定：有正式 UI 截圖證據
- 對應證據：docs/records/action-cards/ACTION_CARD_EXPAND_RESULTS_UI_SCREENSHOTS_2026_05_18.md
- app.js 訊號：pending_choice_ui_present

### 模仿戰術
- 類型：command
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 樹立信心
- 類型：command
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 武裝小隊
- 類型：armed
- 預期 UI 需求：target_player
- 目前判定：需要 UI 互動，但缺少明確 UI validator 證據
- 對應 validator：無明確對應
- app.js 訊號：target_player_flow_present

### 武裝者
- 類型：armed
- 預期 UI 需求：target_player
- 目前判定：需要 UI 互動，但缺少明確 UI validator 證據
- 對應 validator：無明確對應
- app.js 訊號：target_player_flow_present

### 武裝集團
- 類型：armed
- 預期 UI 需求：target_player
- 目前判定：需要 UI 互動，但缺少明確 UI validator 證據
- 對應 validator：無明確對應
- app.js 訊號：target_player_flow_present

### 派遣間諜
- 類型：spy
- 預期 UI 需求：target_player
- 目前判定：需要 UI 互動，但缺少明確 UI validator 證據
- 對應 validator：無明確對應
- app.js 訊號：target_player_flow_present

### 爆料黑幕
- 類型：propaganda_special
- 預期 UI 需求：unknown
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 產業滲透
- 類型：money
- 預期 UI 需求：unknown
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 組織經驗丙
- 類型：organization
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 組織經驗乙
- 類型：organization
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 組織經驗甲
- 類型：organization
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 網羅人才
- 類型：command
- 預期 UI 需求：card_choice
- 目前判定：需要 UI 互動，但缺少明確 UI validator 證據
- 對應 validator：無明確對應
- app.js 訊號：pending_choice_ui_present

### 行動募資
- 類型：money
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 行動預告
- 類型：propaganda_special
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 誘導虛耗
- 類型：command
- 預期 UI 需求：target_player
- 目前判定：需要 UI 互動，但缺少明確 UI validator 證據
- 對應 validator：無明確對應
- app.js 訊號：target_player_flow_present

### 謀劃
- 類型：command
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 資助者
- 類型：money
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 資本家
- 類型：money
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 走漏風聲
- 類型：spy
- 預期 UI 需求：target_player
- 目前判定：需要 UI 互動，但缺少明確 UI validator 證據
- 對應 validator：無明確對應
- app.js 訊號：named_in_app_js, target_player_flow_present

### 輿論丕變
- 類型：propaganda_special
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 離間
- 類型：spy
- 預期 UI 需求：unknown
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 領導
- 類型：command
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

### 高效行動
- 類型：command
- 預期 UI 需求：multi_card_choice
- 目前判定：需要 UI 互動，但缺少明確 UI validator 證據
- 對應 validator：無明確對應
- app.js 訊號：pending_choice_ui_present

### 點燃熱情
- 類型：command
- 預期 UI 需求：standard_action_only
- 目前判定：多半只需標準 action/resource UI；未見專屬 UI validator
- 對應 validator：無明確對應
- app.js 訊號：未見卡名級別專屬訊號

## 結論

- 可明確說 UI 做過且有證據的卡：無
- 有 validator，但仍偏 engine/規則層的卡：無
- 最值得優先補 UI coverage 的卡：乘勝追擊、內應間諜、凝聚共識、合作談判、地下黨、情報網、擴大戰果、武裝小隊、武裝者、武裝集團、派遣間諜、網羅人才、誘導虛耗、走漏風聲、高效行動
- 多半不需要專屬 modal、但也沒有專門 UI validator 的卡：交通經驗丙、交通經驗乙、交通經驗甲、企業人脈、企畫遊說、內鬥、分神、宣傳家、思想家、思想建設、戰略、批判、批鬥、模仿戰術、樹立信心、爆料黑幕、產業滲透、組織經驗丙、組織經驗乙、組織經驗甲、行動募資、行動預告、謀劃、資助者、資本家、輿論丕變、離間、領導、點燃熱情

## 總結回答

目前**不能說所有 action cards 相對應 UI 都已經做完**。

可以比較有把握地說：
- `走漏風聲`：UI 流程有明確證據（modal / target UI / E2E）
- `合作談判`：至少有專門 validator，且 app.js 有 target-player 流程訊號

但像 `情報網`、`網羅人才`、`地下黨`、`擴大戰果`、`乘勝追擊`、`高效行動`、`凝聚共識` 這些涉及 choice/pending-choice 的卡，雖然 engine/regression 已有相當多覆蓋，repo 內仍缺少足夠明確的 UI validator 證據，不能直接宣稱 UI 已完整收尾。
