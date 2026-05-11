# BASE_AUDIT

日期：2026-05-03

## 結論先講

目前資料夾內**確實有根據地 / 初始根據地的正式說明**，主要來源是：

1. `rules.md`
2. `data/factions/all_faction.json`
3. `data/factions/*.v1.1.json`

但是目前 `server/game.py` 的 `_seed_starting_positions()` **沒有依照這些資料正式建立根據地**，而是測試期的硬塞邏輯。

---

## 一、規則文本中的根據地說明

### `rules.md`
有明確段落：

- `步驟⑤ 建立根據地`
- 根據地的組織棋在遊戲過程中不得離開根據地底座
- 反共陣營玩家依照所持陣營卡之「可選用根據地」選項建立根據地
- 最後再由紅軍建立根據地

這表示根據地不是隨機補位，也不是隨便指定。

---

## 二、Faction 資料中的 `bases` 欄位

`data/factions/all_faction.json` 中 31 個 faction 全都有 `bases` 欄位。

### A. 單一固定根據地（可直接視為唯一根據地）
- red_army → 北京
- ye_lang_qian → 貴陽
- kazakh → 阿拉木圖
- tibet_dharamsala → 達蘭薩拉
- tibet_dehradun → 德拉敦
- tibet_chogu → 哲古宗
- taiwan_green → 臺北
- taiwan_blue → 臺北
- uyghur_istanbul → 伊斯坦堡
- uyghur_munich → 慕尼黑
- uyghur_washington → 華盛頓
- uyghur_almaty → 阿拉木圖

### B. 多個候選根據地（看起來是「可選其一」）
- dian → 昆明 / 美斯樂
- miao → 貴陽 / 長沙 / 河南 / 志明市 / 芒塞 / 舊金山 / 洛杉磯
- dai → 德宏 / 西雙版納 / 賀猛 / 曼谷
- mongol → 烏蘭巴托 / 東京 / 紐約
- manchuria → 東京 / 舊金山 / 海參崴
- jin → 太原 / 任意英美城鎮
- qi → 青島 / 濟南 / 任意東洋 / 任意英美城鎮
- republican → 任意牆內 / 任意南洋 / 任意英美城鎮
- wuyue → 杭州 / 溫州 / 任意東洋 / 任意南洋 / 任意英美城鎮
- yue → 廣州 / 任意南洋 / 任意英美城鎮
- hui → 西寧 / 銀川 / 蘭州 / 昆明 / 利雅德 / 任意南洋城鎮
- zhaowu_ganqingning → 蘭州 / 利雅德 / 任意英美城鎮
- qin_guanlong → 西安 / 任意英美城鎮
- wan → 南陽 / 任意英美城鎮

### C. 明顯彈性 / 特殊根據地規則
- hong_kong → 香港城 / 臺北 / 倫敦 / 卡加利 / 多倫多
  - special rule: 事件後可遷移根據地
- federalists → 任意牆內 / 任意英美城鎮
  - tags: `flex_base`
- new_left → 任意牆內 / 任意南洋城鎮
  - tags: `flex_base`
- liberals → 任意牆內城鎮
- underground_church → 任意牆內城鎮

---

## 三、程式現況與規則衝突點

### 目前實作位置
- `server/game.py`
- `_seed_starting_positions()`

### 現況問題
這段目前做的是：
- 依 faction id 查 `preferred`
- 不足時用 `fallback_cycle` 補位
- 給每個玩家 **兩個起始城鎮**
- `p.base = assigned[0]`

### 與規則的衝突
1. 規則上根據地應依 faction 說明建立，不應 fallback 任意補位
2. 你指出每個陣營開局根據地只能選 1 個；目前卻直接發 2 個起始城鎮
3. `bases` 的語義目前沒有正式進入 server setup 流程
4. 特殊 `flex_base` / 遷移型 faction 目前完全沒被正式處理

---

## 四、目前最可信的判定

### 可以確定的
- 專案資料內**有正式根據地說明**
- faction 資料內**有 bases 欄位**
- 現在 server setup **沒有照 bases 正式執行**

### 仍需釐清的
- `bases` 陣列對每個 faction 的精確語義：
  - 唯一固定？
  - 多選一？
  - 特殊遷移候選？
  - 泛型（任意牆內 / 任意南洋）是否需要額外選擇 UI？

---

## 五、下一步建議

1. 先把 31 個 faction 的 `bases` 分成：
   - 固定唯一
   - 候選多選一
   - 彈性 / 特殊規則
2. 再重寫 `server/game.py` 的開局根據地建立流程
3. 移除 `_seed_starting_positions()` 的硬塞邏輯
4. 若 `bases` 含「任意牆內 / 任意英美城鎮」這種泛型值，則需補選擇機制或測試專用預設規則
