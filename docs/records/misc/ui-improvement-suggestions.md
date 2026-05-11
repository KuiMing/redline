# 戰術戰鬥指揮中心 UI 改善建議

## 背景問題總結

目前畫面最明顯的問題是：**背景圖看起來被切到了，沒有涵蓋到最上面的區域**。

這會讓畫面被視覺上切成兩個部分：

- 上方：像是純黑的系統 UI / debug 面板
- 下方：才有戰術地圖背景與遊戲氛圍

結果是整個「戰情中心」的沉浸感被削弱，UI 和背景不像同一個完整的視覺系統。

---

## 1. 背景圖應該覆蓋整個畫面

### 問題

目前背景圖主要出現在中下方，最上面的標題列、狀態列、階段提示區幾乎沒有吃到背景圖，導致畫面上半部和下半部斷裂。

### 改善方向

背景圖應該從 viewport 最上方開始鋪滿整個畫面，再透過深色遮罩維持文字可讀性。

建議 CSS：

```css
.page {
  min-height: 100vh;
  background-image: url("...");
  background-size: cover;
  background-position: center top;
  background-repeat: no-repeat;
}
```

如果目前使用的是 `background-position: center`，建議改成：

```css
background-position: center top;
```

這樣可以避免背景圖重要的上半部被裁掉。

---

## 2. 用全頁暗色 Overlay，而不是讓上方變成純黑

### 問題

如果上方 UI 為了可讀性直接蓋成純黑，會讓背景和 UI 分離。比較好的做法是讓背景仍然存在，只是用 overlay 壓暗。

### 改善方向

使用全頁漸層或半透明遮罩：

```css
.page {
  min-height: 100vh;
  background:
    linear-gradient(
      rgba(5, 8, 15, 0.78),
      rgba(5, 8, 15, 0.88)
    ),
    url("...");
  background-size: cover;
  background-position: center top;
  background-repeat: no-repeat;
}
```

也可以讓上方稍微更暗、下方保留更多背景細節：

```css
.page {
  background:
    linear-gradient(
      to bottom,
      rgba(3, 6, 12, 0.92) 0%,
      rgba(3, 6, 12, 0.72) 32%,
      rgba(3, 6, 12, 0.86) 100%
    ),
    url("...");
  background-size: cover;
  background-position: center top;
}
```

---

## 3. 頂部狀態列不要像 Debug 文字

### 問題

目前這一排資訊：

```text
回合 1 | 階段 行動 | 當前玩家 viewer | 手牌 5 | 黃金 4 | 宣傳 3 | 移動 3 | viewer: 1 | red: 1 |
```

資訊本身有用，但呈現方式太像工程 debug console，和下面卡牌的遊戲 UI 質感不一致。

### 改善方向

改成 HUD badge / stat chips，例如：

```text
[回合 1] [行動階段] [viewer] [手牌 5] [黃金 4] [宣傳 3] [移動 3]
```

視覺方向：

- 每個狀態是一個小膠囊 badge
- 使用半透明深色底
- 邊框使用微弱藍光或白色透明線
- 重要資源可以加 icon 或顏色區分

範例 CSS：

```css
.status-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 16px;
  background: rgba(8, 12, 20, 0.58);
  border-bottom: 1px solid rgba(130, 170, 255, 0.16);
  backdrop-filter: blur(8px);
}

.status-chip {
  padding: 4px 10px;
  border: 1px solid rgba(160, 190, 255, 0.22);
  border-radius: 999px;
  background: rgba(20, 28, 44, 0.72);
  color: rgba(235, 242, 255, 0.92);
  font-size: 12px;
  line-height: 1.4;
}
```

---

## 4. 卡牌與背景的對比需要更穩定

### 問題

背景是紅黑地圖，本身有很多細節。卡牌又是半透明深色，部分紅色線條會穿過卡牌背後，造成文字閱讀壓力。

### 改善方向

卡牌可以保留玻璃感，但底色應該再實一點，並加上 blur：

```css
.card {
  background: rgba(20, 24, 32, 0.88);
  border: 1px solid rgba(255, 255, 255, 0.10);
  backdrop-filter: blur(8px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.32);
}
```

如果文字仍然不夠清楚，可以把卡牌背景提高到：

```css
background: rgba(18, 22, 30, 0.94);
```

---

## 5. 卡牌資訊層級可以更清楚

### 問題

每張卡牌同時包含很多資訊：

- 卡牌名稱
- 類型
- 等級 / 資源
- 描述文字
- 效果文字
- 標籤
- 按鈕
- 剩餘數量

但目前視覺層級不夠明確，玩家第一眼不容易知道要先看哪裡。

### 改善方向

建議強化以下層級：

1. **卡牌名稱**：字級放大、亮度提高
2. **剩餘數量**：做成右上角 badge
3. **卡牌類型 / 稀有度**：放在固定位置的小標籤
4. **主要操作按鈕**：比資源標籤更突出
5. **不可用卡牌**：降低透明度或加 disabled 狀態

---

## 6. Tab 和內容區的關係可以更明確

### 問題

「指揮中心 / 戰略地圖 / 戰況紀錄」三個 tab 功能清楚，但和下面卡牌內容區的視覺關聯偏弱。

### 改善方向

- Active tab 可以更亮，或加 glow
- Tab 下方可以接一條分隔線
- 內容區可以有明確 panel 邊界
- 區塊標題如「常設購買區 / 隨機購買區 / 手牌」可以提高亮度與對比

範例：

```css
.tabs {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(120, 160, 255, 0.16);
}

.tab.active {
  color: #ffffff;
  background: rgba(56, 104, 180, 0.42);
  border-color: rgba(130, 180, 255, 0.72);
  box-shadow: 0 0 16px rgba(80, 140, 255, 0.24);
}
```

---

## 7. 「結束行動階段」按鈕可以和階段提示放在同一個 Action Bar

### 問題

右上角橘色按鈕很醒目，這是好的，因為它是主要操作。但它和「目前：行動｜下一步：結束行動階段」文字距離有點遠，關聯性不夠強。

### 改善方向

把階段提示和按鈕放在同一條 action bar：

```text
目前階段：行動
下一步：結束行動階段                         [結束行動階段]
```

範例 CSS：

```css
.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  background: rgba(8, 12, 20, 0.52);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(8px);
}

.primary-action {
  padding: 10px 18px;
  border-radius: 10px;
  background: linear-gradient(180deg, #f6a623, #c8730d);
  color: #fff;
  font-weight: 700;
  box-shadow: 0 8px 22px rgba(232, 132, 20, 0.35);
}
```

---

## 8. 主內容左右邊界可以再放鬆

### 問題

卡牌區左右邊界偏緊，整體有一點內容塞滿螢幕的感覺。

### 改善方向

增加主內容 padding：

```css
.main {
  padding: 24px 32px;
}
```

或限制最大寬度並置中：

```css
.container {
  width: min(100%, 1280px);
  margin: 0 auto;
  padding: 0 24px;
}
```

---

## 建議優先修改順序

如果只先做三件事，建議照這個順序：

1. **讓背景圖鋪滿整個 viewport**
   - 使用 `background-size: cover`
   - 使用 `background-position: center top`
   - 確保最上方也有背景圖

2. **加上全頁深色 overlay**
   - 不要讓頂部變成純黑區塊
   - 讓背景和 UI 保持同一個視覺系統
   - 用 overlay 控制文字可讀性

3. **把頂部狀態列改成 HUD badge**
   - 移除 debug console 感
   - 提升遊戲介面質感
   - 讓資訊更容易掃讀

---

## 核心結論

這個畫面的主要問題不是單純「背景圖被切到」，而是：

> 背景、遮罩、頂部 UI、卡牌區沒有被當成同一套視覺系統處理。

最好的改善方式是讓背景從最上方開始覆蓋整個畫面，然後用漸層 overlay 和半透明 HUD 元件來控制可讀性。這樣既能保留戰術地圖的氛圍，也能讓 UI 看起來更完整、更像正式遊戲介面。
