# 測試清單：近期前端 / 市場規則改動

## P0：先測這些

### 1. 牌庫模式
- [ ] lobby 可選 `53 張卡牌`
- [ ] lobby 可選 `全部卡牌`
- [ ] `/start` 會把 `market_mode` 帶進 runtime
- [ ] HUD 會顯示目前牌庫模式
- [ ] `sample_53` 與 `all_cards` 的購買牌庫大小不同

### 2. 移除回購買區庫存
- [ ] `宣傳家` 被移除後，可見購買區長度不變
- [ ] `宣傳家` 被移除後，`static_purchase_supply["宣傳家"] + 1`
- [ ] 手牌正確移除
- [ ] 不會多出第 12 格購買區卡

### 3. 720p 舞台 / 多 viewport
- [ ] 1280×720 指揮中心
- [ ] 1280×720 戰略地圖
- [ ] 1280×720 戰況紀錄
- [ ] 1920×1080 縮放結果
- [ ] 1024×768 縮放結果
- [ ] body 無 scroll

### 4. 卡牌 UI 一致性
- [ ] 常設購買區卡片尺寸一致
- [ ] 隨機購買區卡片尺寸一致
- [ ] 手牌卡片尺寸一致
- [ ] 顏色 / badge / count 顯示正常

## P1：流程 smoke test
- [ ] 2P 基本流程
- [ ] 3P 基本流程
- [ ] 4P 基本流程
- [ ] command / map / log tab 切換
- [ ] 結束事件 / 行動 / 回合按鈕仍正常

## P2：專項
- [ ] 時代關卡 modal / pin / HUD
- [ ] support cards
- [ ] faction action modal
- [ ] shared move / dissolve / map interaction
