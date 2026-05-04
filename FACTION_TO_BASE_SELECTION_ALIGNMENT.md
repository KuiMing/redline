# FACTION_TO_BASE_SELECTION_ALIGNMENT

日期：2026-05-04

## 本輪修正

根據規則與使用者回饋：
- 維吾爾 / 西藏不應在「選陣營」頁面展開城市版本
- 伊斯坦堡 / 慕尼黑 / 華盛頓 / 阿拉木圖應屬於根據地選擇階段

## 已實作

### faction selection 第一層
現在只顯示主陣營 categories：
- 紅軍
- 臺灣
- 香港
- 維吾爾
- 西藏
- 滿洲
- 蒙古
- 哈薩克
- 反賊

### 維吾爾 / 西藏
- 第一層選到維吾爾後，server 記錄為 `uyghur_family`
- 第一層選到西藏後，server 記錄為 `tibet_family`
- 之後在 `BASE_SELECTION` 階段，才顯示：
  - 維吾爾 → 伊斯坦堡 / 慕尼黑 / 華盛頓 / 阿拉木圖
  - 西藏 → 達蘭薩拉 / 德拉敦 / 哲古宗

### server/game.py
- 新增 family faction placeholder：
  - `uyghur_family`
  - `tibet_family`
- `set_base_choice()` 現在在 family 選定具體根據地後，會把 faction id 轉成真正 variant：
  - `uyghur_family` + 慕尼黑 → `uyghur_munich`
  - `tibet_family` + 德拉敦 → `tibet_dehradun`

## 結果

玩家感知上的流程現在更符合規則：
- 先選主陣營
- 再依需要進根據地選擇
- 城市版本不再出現在陣營選擇頁
