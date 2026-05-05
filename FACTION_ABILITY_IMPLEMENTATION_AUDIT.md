# FACTION_ABILITY_IMPLEMENTATION_AUDIT

日期：2026-05-05

## 結論

目前 faction abilities 可分成三層狀態：

1. **資料層已存在**
   - faction data / UI 顯示已可見
2. **UI 層已顯示**
   - faction / base 選擇面板會列出能力文字
3. **Engine 層尚未全面接線**
   - 大部分 faction ability 尚未在 server 回合引擎中真正觸發生效

因此，現在不能說「各項能力都已實作」。
更準確的說法是：
- **多數能力已經有資料與 UI 顯示**
- **但真正進遊戲自動生效的 engine 實作仍不完整**

---

## 我剛確認到的 engine 實作現況

### 已看到的能力資料模板 / faction ability refs
在 `all_faction.integrated.v2.json` 中，已有 faction 使用這些能力模板：

- `combo_three_unique`
- `first_money_gain2`
- `first_propaganda_draw`
- `guerrilla`
- `on_build_draw_inner`
- `on_build_draw_inner_or_nanyang`

### 但在 server 端的現況
我檢查 `server/*.py` 後，除了：
- `server/main.py` 會為 UI 展開 `ability_templates`
- `server/victory.py` 會處理部分 `win_conditions`

**沒有看到 faction ability 被全面掛進回合引擎的跡象。**

也就是說，像這些能力目前主要是：
- 存在於資料
- 能顯示在 UI
- 但不代表遊戲內真的會自動觸發

---

## 已知已在資料 / UI 出現，但未證明 engine 已實作的代表能力

### 主陣營 /變體
- 香港：攬炒策略
- 香港（香港城）：安全屋
- 臺灣（綠線）：本土社團
- 臺灣（藍線）：民國之心
- 蒙古：盟族學校
- 哈薩克：民族調和（`first_propaganda_draw`）
- 維吾爾（伊斯坦堡）：游擊隊 + 新疆社會管控
- 維吾爾（慕尼黑）：基金會 + 東突厥斯坦政府 + 非暴力 + 新疆社會管控
- 西藏（達蘭薩拉）：共合會 + 達賴救援 + 非暴力
- 西藏（德拉敦 / 哲古宗）：游擊隊 / 印度研究分析室

### 反賊代表模板能力
- 商貿組織
- 展現實力
- 殉道者
- 星星之火
- 立場試探
- 民主陣線
- 華文傳媒
- 民族祭儀
- 青山里

這些目前多數仍停在資料 / UI 層。

---

## 已看到有部分 engine 實作的不是 faction abilities，而是別的東西

### 已較完整的
- action cards effect engine
- victory engine 的部分基礎 `win_conditions`
- movement / build / develop legality
- opening base assignment / base selection state flow

### 未完整的
- faction passive / triggered / setup / restriction abilities
- faction-specific deck modification
- faction-specific resource hooks
- faction-specific discard/tax/reaction hooks

---

## 下一步建議

### P1：把 faction abilities 拆成盤點表
依能力逐條標記：
- `DATA_ONLY`
- `UI_ONLY`
- `PARTIAL_ENGINE`
- `FULLY_IMPLEMENTED`

### P2：優先補主陣營與使用頻率高的能力
建議先補：
1. 香港：攬炒策略 / 安全屋
2. 臺灣綠 / 藍：本土社團 / 民國之心
3. 蒙古：盟族學校
4. 哈薩克：民族調和
5. 維吾爾 / 西藏分支能力
6. 反賊常見模板：商貿組織 / 展現實力 / 殉道者 / 民族祭儀

### P3：再補特殊購買 / 非暴力 / setup 類能力
例如：
- 民運派：民主陣線 / 各界資助 / 非暴力
- 法輪功：資金支付宣傳
- 改革開放派：看牌堆頂 3 張並抽 1
- 自由派：奇偶判定抽牌

---

## 目前可對外說的準確話術

> faction abilities 現在已經大量整理進資料與 UI，
> 但真正進遊戲引擎自動生效的部分還沒有全面完成。
> 下一步應該是做 faction ability engine audit，再逐條接線。
