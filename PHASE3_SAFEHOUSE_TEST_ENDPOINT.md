# PHASE3_SAFEHOUSE_TEST_ENDPOINT

日期：2026-05-05

## 本輪完成

新增了一個專門給安全屋前端演示用的測試入口：

- `POST /test/setup-hong-kong-safehouse`

## 作用

這個 endpoint 會直接建立一個：
- 香港玩家
- 已在 `ACTION` phase
- 已在 `MAIN` game phase
- 根據地可指定（預設 `香港城`）

的測試局面。

## 目的

讓前端能直接進入：
- 已開局
- 已輪到香港玩家
- 應可顯示安全屋 build support panel

的狀態，避免被正常開局流程擋住。

## 目前結果

- endpoint 已能成功建立測試局面
- 但 browser 實測下，`buildSupportPanel` 仍未顯示
- 這表示前端面板顯示條件或狀態來源還有一處沒接上

## 產物

- 成功建立測試局面的 endpoint
- 截圖：`safehouse_build_support_missing.png`

## 結論

這一輪已把「缺穩定測試入口」這件事補上。
接下來要修的是：
- 為什麼安全屋前端 panel 在符合條件的測試局面中仍未顯示
