# FACTION_ACTION_GUESS_MODAL_UI

日期：2026-05-06

## 本輪完成

已為澳門的 `賭徒耳語` 補上玩家可操作的猜奇偶 UI。

## UI 形式

採用：
- 畫面中央半透明深色模態視窗
- 背景模糊遮罩
- 類似霧面玻璃的浮層效果

## 修改內容

### static/index.html
新增：
- `#factionActionPanel`
- `#factionActionModal`
- `#factionActionModalTitle`
- `#factionActionModalDesc`
- `#factionActionModalChoices`
- `#guessOddBtn`
- `#guessEvenBtn`
- `#closeFactionActionModal`

### static/style.css
新增：
- `modal-overlay`
- `modal-glass`
- `modal-title-text`
- `modal-body-text`
- `modal-choice-row`
- `modal-choice-btn`
- `modal-cancel-btn`

效果：
- 中央浮層
- 半透明深色背景
- backdrop blur
- 霧面玻璃感

### static/app.js
新增：
- `activeFactionActionModal`
- `closeFactionActionModal()`
- `openGamblerGuessModal()`
- `renderFactionActionPanel(state)`

行為：
- 澳門玩家在 `ACTION` phase 且輪到自己時
- command 面板會出現：`發動 賭徒耳語`
- 點下後打開中央模態視窗
- 玩家可選：
  - `猜奇數`
  - `猜偶數`
- 會送出：
  - `sendAction('faction_action', { name: '賭徒耳語', guess: 'odd' | 'even' })`

### server/game.py / server/main.py
- `faction_action` 現在支援 `guess`
- `賭徒耳語` 不再固定猜奇數，改為使用玩家選擇的奇偶

## 驗證
- 以澳門玩家測試局面進入 `ACTION` phase
- 點 `發動 賭徒耳語`
- 中央 modal 成功顯示
- 截圖：`aomen_guess_modal_ui.png`
