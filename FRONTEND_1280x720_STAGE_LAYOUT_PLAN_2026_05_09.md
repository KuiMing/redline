# Redline 前端 1280 × 720 固定舞台化改造計畫

> 目的：請將 redline 前端整體 UI 依照背景圖尺寸 1280 × 720 px 重新整理。背景圖 `static/war_background.jpg` 應視為完整設計畫布，所有 UI 元件都必須被限制在這個範圍內。

---

## 1. 核心原則

這個專案的前端應該用「遊戲 UI / 固定畫布」思維處理，不要用一般網頁的響應式重排思維。

正確方向：

- 固定一個 1280 × 720 的設計舞台。
- 背景圖尺寸就是 1280 × 720。
- 所有 UI 元件都放在這個 1280 × 720 範圍內。
- 使用者螢幕比較大或比較小時，只縮放整個舞台。
- 可以出現黑邊 letterbox / pillarbox。
- 不可以因為螢幕比較寬就把 UI 拉寬。
- 不可以因為螢幕比較高就把 UI 拉高。
- 不可以讓元件跑出背景圖範圍。

一句話：

> `#designStage` 永遠是 1280 × 720，外層只負責等比例縮放它。

---

## 2. 主要修改檔案

預期至少會修改以下檔案：

- `static/index.html`
- `static/style.css`
- `static/app.js`

可能需要檢查但不一定要改：

- `static/leaflet_game_map.html`
- `static/leaflet_game_map_fragment.html`
- `static/leaflet_game_map_logic.js`
- `static/map-module.js`

---

## 3. HTML 結構調整

請在 `static/index.html` 裡新增兩層容器：

```html
<body>
  <div id="stageViewport">
    <div id="designStage">
      <!-- 原本所有 UI 元件放在這裡 -->
    </div>
  </div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="/static/app.js"></script>
</body>
```

原本 body 底下的主要 UI 元件都應該移進 `#designStage`：

- `#warTitle`
- `#topBar`
- `#hud`
- `#phaseActionBar`
- `#debugSocketState`
- `#lobby`
- `#factionActionModal`
- `#eraAchievementModal`
- `#eraPinnedNotice`
- `#gameShell`

注意：

- script 可以留在 `#stageViewport` 外面。
- 不要把 UI 元件直接留在 body 底下。
- modal overlay 也要放進 `#designStage`，不能以整個 browser viewport 為定位基準。

---

## 4. CSS：建立固定 1280 × 720 設計舞台

請將背景圖從 `body` 移到 `#designStage`。

建議新增或調整如下：

```css
:root {
  --stage-w: 1280px;
  --stage-h: 720px;
  --stage-scale: 1;
}

html,
body {
  margin: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #05080C;
}

body {
  color: var(--text-main);
  font-family: 'Inter', sans-serif;
}

#stageViewport {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  overflow: hidden;
  background: #05080C;
}

#designStage {
  width: 1280px;
  height: 720px;
  position: relative;
  overflow: hidden;
  transform: scale(var(--stage-scale));
  transform-origin: center center;

  background-image: url('/static/war_background.jpg');
  background-size: 1280px 720px;
  background-position: center center;
  background-repeat: no-repeat;
}
```

必須移除或避免以下做法：

```css
body {
  background-image: url('/static/war_background.jpg');
  background-size: contain;
  background-attachment: fixed;
}
```

背景圖只應存在於 `#designStage`。

---

## 5. JS：依螢幕大小縮放整個舞台

請在 `static/app.js` 中加入舞台縮放邏輯。

建議函式：

```js
function resizeStage() {
  const scale = Math.min(
    window.innerWidth / 1280,
    window.innerHeight / 720
  );

  document.documentElement.style.setProperty('--stage-scale', String(scale));
}

window.addEventListener('resize', resizeStage);
window.addEventListener('DOMContentLoaded', resizeStage);
resizeStage();
```

如果希望大螢幕不要放大，只維持原始 1280 × 720，則改成：

```js
const scale = Math.min(
  1,
  window.innerWidth / 1280,
  window.innerHeight / 720
);
```

本案建議允許放大，因為它比較像遊戲畫面，不是一般文件型網頁。

---

## 6. 將 viewport 綁定改成 stage 綁定

目前 CSS 中有些寫法會直接依賴瀏覽器 viewport，例如：

```css
#warTitle {
  position: fixed;
  font-size: 20vw;
}

#gameShell {
  height: calc(100vh - 48px - 42px - 67px);
  width: 100vw;
}
```

這些都應該改掉。

原則：

- `position: fixed` 改成 `position: absolute`。
- `100vw` / `100vh` 不要用在舞台內部排版。
- 舞台內部全部以 1280 × 720 的 px 座標為準。

建議切法：

```css
#warTitle {
  position: absolute;
  top: 330px;
  left: 640px;
  transform: translate(-50%, -50%);
  font-size: 220px;
}

#topBar {
  position: absolute;
  left: 0;
  top: 0;
  width: 1280px;
  height: 48px;
}

#hud {
  position: absolute;
  left: 0;
  top: 48px;
  width: 1280px;
  height: 42px;
}

#phaseActionBar {
  position: absolute;
  left: 0;
  top: 90px;
  width: 1280px;
  height: 60px;
}

#gameShell {
  position: absolute;
  left: 0;
  top: 150px;
  width: 1280px;
  height: 570px;
}
```

---

## 7. 建議的 1280 × 720 畫面區塊

整體舞台：

| 區塊 | y 範圍 | 高度 |
|---|---:|---:|
| topBar | 0–48 | 48px |
| hud | 48–90 | 42px |
| phaseActionBar | 90–150 | 60px |
| gameShell | 150–720 | 570px |

`gameShell` 內部：

| 區塊 | y 範圍 | 高度 |
|---|---:|---:|
| gameTabs | 0–48 | 48px |
| active view content | 48–570 | 522px |

因此主要內容區可用尺寸是：

```txt
1280 × 522
```

---

## 8. 指揮中心布局建議

目前 `#commandGrid` 使用百分比欄位：

```css
grid-template-columns: 28% 36% 36%;
```

建議改成明確 px，避免不同螢幕比例下跑版。

建議：

```css
#commandView {
  position: relative;
  width: 1280px;
  height: 570px;
  overflow: hidden;
}

#commandGrid {
  position: absolute;
  left: 0;
  top: 48px;
  width: 1280px;
  height: 522px;
  display: grid;
  grid-template-columns: 300px 460px 460px;
  gap: 12px;
  padding: 12px;
  align-items: stretch;
}
```

寬度計算：

```txt
padding 左右：12 + 12 = 24
兩個 gap：12 + 12 = 24
三欄：300 + 460 + 460 = 1220
總計：24 + 24 + 1220 = 1268
剩餘：12px
```

這樣不會超出 1280px。

---

## 9. 卡片尺寸調整建議

目前卡片大約是：

```css
width: 260px;
height: 320px;
```

在 720p 固定舞台中偏大，尤其隨機購買區與手牌區如果要兩欄，會壓迫空間。

建議改成：

```css
#purchaseSection .card,
#purchaseRandom .card,
#hand .card {
  width: 220px;
  min-width: 220px;
  max-width: 220px;
  height: 270px;
  min-height: 270px;
  max-height: 270px;
  flex: 0 0 220px;
}

#hand,
#purchaseRandom,
#purchaseStatic,
.purchase-card-grid {
  grid-template-columns: repeat(2, 220px);
  gap: 12px;
}
```

文字也建議略縮：

```css
.purchase-card-title {
  font-size: 15px;
}

.purchase-card-body {
  font-size: 12px;
  line-height: 1.4;
}

.card-badge {
  font-size: 10px;
  padding: 3px 7px;
}
```

要求：

- 卡片不能超出 panel。
- panel 可以內部 scroll。
- body 不可以 scroll。
- 卡片內容若過長，應在卡片內部或 panel 內部 scroll，不可撐爆整頁。

---

## 10. 戰略地圖頁布局

地圖 iframe 必須被限制在 1280 × 720 舞台內。

建議：

```css
#mapView {
  position: relative;
  width: 1280px;
  height: 570px;
  overflow: hidden;
}

.map-only-panel {
  position: absolute;
  left: 12px;
  top: 60px;
  width: 1256px;
  height: 498px;
  overflow: hidden;
}

#strategicMapFrame {
  width: 100%;
  height: 100%;
  border: 0;
}
```

注意：

- 地圖 iframe 外框不可超出舞台。
- 地圖本身可以 pan / zoom。
- 但 iframe 外層不能造成 body scroll。
- 如果 iframe 內部 HTML 也有 `100vw` / `100vh` 問題，需要一併檢查。

---

## 11. 戰況紀錄頁布局

建議：

```css
#logView {
  position: relative;
  width: 1280px;
  height: 570px;
  overflow: hidden;
}

.log-only-panel {
  position: absolute;
  left: 12px;
  top: 60px;
  width: 1256px;
  height: 498px;
  overflow: hidden;
}

#logViewContent {
  flex: 1;
  overflow-y: auto;
}
```

要求：

- log 很長時，只能在 log panel 內部 scroll。
- 不可以造成整個 browser body scroll。

---

## 12. Modal 與 overlay

Modal 不可以再用整個 browser viewport 當基準。

建議：

```css
.modal-overlay {
  position: absolute;
  left: 0;
  top: 0;
  width: 1280px;
  height: 720px;
}

.modal-glass {
  max-width: 720px;
  max-height: 620px;
  overflow: auto;
}
```

要求：

- 陣營能力 modal 出現在 1280 × 720 舞台中央。
- 時代關卡 modal 出現在 1280 × 720 舞台中央。
- overlay 只覆蓋背景圖範圍。
- overlay 不應蓋到外層黑邊。
- pinned notice 不可超出舞台右上角。

---

## 13. Lobby 畫面

Lobby 也必須在 `#designStage` 內。

要求：

- lobby 不可超出 1280 × 720。
- 陣營選擇列表如果很長，列表本身 scroll。
- body 不可 scroll。
- lobby 的定位使用 absolute 或 stage 內 grid / flex，不依賴 body viewport。

---

## 14. 禁止事項

請不要用以下方式解決：

- 不要把 body 設成可 scroll 來容納超出的 UI。
- 不要讓背景圖留在 body。
- 不要在舞台內部大量使用 `100vw` / `100vh`。
- 不要用一般 responsive breakpoint 重排三欄布局。
- 不要讓 1920 × 1080 時 UI 自行變寬。
- 不要讓 1024 × 768 時 UI 被壓縮重排。
- 不要只修單一畫面，必須 lobby / command / map / log / modal 都一起驗證。

---

## 15. 驗收標準

完成後請至少驗證以下螢幕尺寸：

- 1280 × 720
- 1920 × 1080
- 1366 × 768
- 1024 × 768
- 1440 × 900

期待結果：

- `#designStage` 永遠是 1280 × 720。
- 畫面依外層 viewport 等比例縮放。
- 可以有黑邊。
- 不可以變形。
- 不可以重排。
- 不可以有 body scroll。
- UI 元件不可超出背景圖範圍。

---

## 16. 必測畫面

### 16.1 Lobby

確認：

- 背景完整顯示。
- lobby 位於背景圖範圍內。
- 無 body scroll。
- 陣營選擇列表不撐爆畫面。

### 16.2 指揮中心

確認：

- topBar / HUD / phaseActionBar / tabs / 三欄 panel 全部在畫面內。
- panel 內部可以 scroll。
- body 不可以 scroll。
- 卡片不被 panel 外框切掉。
- 卡片 hover / selected 狀態正常。

### 16.3 戰略地圖

確認：

- 地圖 iframe 完整在舞台內。
- 地圖不壓到 topBar / HUD / phaseActionBar / tabs。
- 地圖 pan / zoom 正常。
- iframe 外沒有多餘白邊。

### 16.4 戰況紀錄

確認：

- log panel 在舞台內。
- log 內容長時只在 panel 內 scroll。
- 不造成整頁 overflow。

### 16.5 Modal

確認：

- 陣營能力 modal 在 1280 × 720 中央。
- 時代關卡 modal 在 1280 × 720 中央。
- pinned notice 不超出右上角。
- modal overlay 不覆蓋外層黑邊。

---

## 17. 交付項目

請交付：

1. 修改後的檔案
   - `static/index.html`
   - `static/style.css`
   - `static/app.js`
   - 如有必要，包含相關 map iframe 檔案

2. 截圖
   - 1280 × 720 lobby
   - 1280 × 720 指揮中心
   - 1280 × 720 戰略地圖
   - 1280 × 720 戰況紀錄
   - 1920 × 1080 縮放結果
   - 1024 × 768 縮放結果

3. 驗證說明
   - body 是否無 scroll
   - `#designStage` 是否固定 1280 × 720
   - 背景圖是否只存在於 `#designStage`
   - modal 是否限制在 `#designStage` 裡
   - card 是否已調整為 720p 可容納尺寸

---

## 18. 建議實作順序

1. 先調整 `index.html`，加入 `#stageViewport` 與 `#designStage`。
2. 將所有 UI 元件移進 `#designStage`。
3. 將背景圖從 body 移到 `#designStage`。
4. 在 `app.js` 加入 `resizeStage()`。
5. 將 topBar / hud / phaseActionBar / gameShell 改成 stage 內 absolute 定位。
6. 將 commandGrid 改成固定 px 欄位。
7. 調整卡片尺寸到 220 × 270。
8. 修 mapView / logView 尺寸。
9. 修 modal overlay 定位。
10. 逐一測 lobby / command / map / log / modal。
11. 用多種 viewport 尺寸截圖驗證。

---

## 19. 最終發包摘要

請把 redline 前端 UI 改成固定 1280 × 720 設計舞台。背景圖 `war_background.jpg` 就是完整舞台尺寸。所有 UI 元件必須放在 `#designStage` 內，以 px 絕對定位或固定 grid 定位，禁止依賴 body 的 `100vw` / `100vh` 做內部排版。外層只負責依螢幕尺寸等比例縮放整個 `#designStage`，允許黑邊，不允許變形或重排。完成後請用 1280 × 720、1920 × 1080、1024 × 768 截圖驗證無 body scroll、無元件超出背景範圍。
