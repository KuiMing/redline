# Action Card Regression Status

更新時間：2026-05-12

## 目的

這份文件是目前 Redline action card 規則收斂的權威清單，用來避免之後重複誤判：

- 某張卡其實已在歷史上處理過，卻被誤當成未處理
- 某張卡已經有 direct-`Game` regression，但沒有被明確記錄
- 某張卡只在 validator 或其他卡的測試裡被間接碰到，卻被誤算成已完整覆蓋

判定原則：

- **Regression 已覆蓋**：在 `scripts/tests/test_action_card_regressions.py` 有明確、可讀的直接測試
- **歷史已處理**：曾在先前工作中完成規則/validator/UI 驗證，但目前不一定有明確落在該 regression 檔
- **待補強**：尚未有足夠明確的直接 regression，或之後若需要更高保真度可再補

## A. 已在 `scripts/tests/test_action_card_regressions.py` 明確覆蓋

- 網羅人才
- 誘導虛耗
- 模仿戰術
- 情報網
- 離間
- 行動預告
- 行動募資
- 合作談判
- 地下黨
- 派遣間諜
- 內應間諜
- 武裝者
- 武裝小隊
- 武裝集團
- 輿論丕變
- 批判
- 批鬥
- 點燃熱情
- 樹立信心
- 凝聚共識
- 擴大戰果
- 企業人脈
- 產業滲透
- 爆料黑幕
- 高效行動
- 乘勝追擊
- 企畫遊說
- 思想建設
- 思想家
- 宣傳家
- 資本家
- 資助者
- 分神
- 領導
- 謀劃
- 戰略
- 交通經驗丙
- 交通經驗乙
- 交通經驗甲
- 組織經驗丙
- 組織經驗乙
- 組織經驗甲

## B. 歷史已處理，但不應只靠 regression 檔判定

- 走漏風聲
  - 已完成 `leak_top_deck` 專用 effect
  - 已處理 target player 指定
  - 已驗證資源模式不觸發行動效果
  - 已驗證若牌費用 >= 1，會把 `內鬥` 放進目標玩家棄牌堆
  - 已驗證 `內鬥` 必須從常設購買區供應扣減，不可憑空生成
  - 已做過 UI 目標選擇 modal 與 E2E 驗證
  - 因此之後**不可再把走漏風聲當成未處理卡候選**

## C. 間接被碰到，但不應單獨算成 action card 主測項

- 內鬥
  - 常出現在情報網、離間、走漏風聲等效果驗證裡
  - 但它不是目前這輪 action-card 收斂裡的主要「下一張待修卡」判定對象

## D. 目前狀態

以 2026-05-12 這一輪整理為準：

- 目前主要 action card regression 已補齊
- 之後若再挑「下一張 card」時，必須先同時檢查：
  - 本文件
  - `scripts/tests/test_action_card_regressions.py`
  - 相關 validator / 歷史紀錄

不得只因為某張卡沒有出現在單一測試檔中，就直接判定它「尚未處理」

## E. 後續建議

如果未來還要擴充，可以沿這份文件往下分欄：

- Engine regression
- UI validator
- E2E validator
- 已知 MVP/characterization only

但在目前階段，先維持這份單一權威清單即可。
