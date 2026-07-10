# 規則資料 vs 程式實作 落差盤點（2026-07-10）

## 目的與範圍

使用者指定三個「最重要的規則來源」，要求通盤檢查程式碼是否有缺失，並規劃後續改善項目：

1. `data/factions/all_faction.integrated.v2.json` — 61 個陣營的完整規則資料（能力、限制、根據地、勝利條件、共用組織規則等）。
2. `data/raw/*.csv`（`action_cards.csv` 46 張行動卡、`support_cards.csv` 奧援卡、`event_and_era_cards.csv` 事件卡）。
3. `rules.md` — 精簡版規則總覽。

比對方式：直接讀取資料檔案內容，再用 grep／閱讀對照 `server/game.py`（5270 行，核心遊戲邏輯）、`server/victory.py`（勝利判定）、`server/effect_engine.py`（效果分派）、`server/era_engine.py`、`server/events.py`、`server/event_model.py`，確認每一條規則是否有對應實作、實作是否與文字描述一致。

## 進度狀態

- ✅ 已完成：**B1-a**（`東洋奧援` 中介資料檔損毀 + 連帶曝露的 tier2 誤判 bug）—— 2026-07-10 修正並驗證，詳見下方 B1-a 段落與 `TODO.md`「規則資料 vs 程式實作落差修正」條目。
- ✅ 已完成：**A3**（粵/澳門↔香港共用組織單向生效）—— 2026-07-10 修正並驗證，詳見下方 A3 段落與 `TODO.md`「規則資料 vs 程式實作落差修正」條目。
- ✅ 已完成：**`企業人脈`**（借用範圍誤排除常設購買區，B3）—— 2026-07-10 修正並驗證，詳見上方段落與 `TODO.md`「規則資料 vs 程式實作落差修正」條目。
- ⏳ 待處理：其餘全部項目（A1、A2、A4、B1-b、B1-c、B2 已無落差不需處理、B3 其餘項目、C1-C3）。

本文件本身是**盤點結果 + 後續改善規劃**，不是修正 PR；所有項目都還沒有動程式碼。

---

## 這次盤點方式的一個重要前提發現

程式實際載入的陣營資料檔是 `data/factions/all_faction.integrated.v2.json`（`server/game.py:25` `FACTIONS_PATH`、`server/main.py:361,439`），**不是** `all_faction.json`（無 `.integrated.v2`）也不是 `data/factions/*.v1.1.json` 個別陣營檔。也就是說使用者指定的第一個檔案確實是唯一權威來源，`data/factions/` 底下其餘檔案目前應視為舊版／未使用，之後若要修正陣營規則，只需要改 `all_faction.integrated.v2.json`（而 `server/main.py` 有多處寫死的 payload 預設值如 `payload.get("faction_id", "tibet_dehradun")`，這些只是測試端點的預設 fallback，不影響正式陣營資料來源）。

另外發現一個**不在使用者指定三個來源內、但直接餵給同一套回合流程的第 4 個資料檔**：`data/era_structured.v1.1.json`（`server/game.py:27` `ERA_STRUCTURED_PATH`），對應 `rules.md`「事件階段②檢查時代關卡觸發條件」與陣營 JSON `shared_turn_flow.event_phase` 提到的「時代關卡」。這個檔案目前只有 8 筆（`hong_kong, mongolia, tibet, kazakh, uyghur, manchuria, rebels, taiwan`），是用陣營大類分組、不是每個陣營 id 各一筆。本次盤點**沒有**深入比對這個檔案內容是否完整（超出使用者這次指定的三個來源），只在此記錄它的存在與位置，供之後如果要做「時代關卡」專項盤點時使用。

---

## A. 陣營規則（`all_faction.integrated.v2.json`）落差 —— 本次盤點的重點，發現多項嚴重缺口

### A1.【最高優先】46 / 61 個陣營的勝利條件完全沒有被判定 —— 這些陣營理論上永遠不會自己贏

**現況**：`all_faction.integrated.v2.json` 裡的陣營資料有兩種 schema：
- 15 個陣營（`red_army`、`kazakh`、`hong_kong`、`tibet_dharamsala/dehradun/chogu`、`mongol`、`manchuria`、`taiwan_green/blue`、`uyghur_istanbul/munich/washington/almaty`、`hu`）用結構化的 `win_conditions` 陣列（`type: count_only / count_and_required / taiwan_override / default_survival`）。
- 其餘 46 個「地域／政治類」反賊陣營（`liberals, republican, federalists, minyun, new_left, reform_opening, falun_gong, underground_church, gender_revolution, qiong, yue, aomen, hakka, chaoshan, gui, gan, min, wuyue, xiang, chu, jianghuai, wan, yiluo_yu, youyan, jin, qi, yuba, bashu, ye_lang_qian, dian, dian_zhuang, qin_guanlong, zhaowu_ganqingning, zhuang, yi, bai, hani, dai, miao, tujia, dong, buyei, yao, li, hui, chaoxian` 等）只有一段自由文字 `win_condition_text`（例如 `粵`：「回合結束時在牆內與牆外共擁有至少11個有效組織，其中必須包含廣州、深圳、湛茂。」），**沒有**結構化的 `win_conditions` 陣列。

**程式現況**：全專案對 `win_condition` 相關欄位的存取只有一處——`server/victory.py:29`：
```python
conditions = faction.get("win_conditions", [])
```
完全沒有任何程式碼讀取或解析 `win_condition_text`（用 `grep -rn "win_condition" server/*.py` 確認，唯一命中就是這一行）。`_check_player_conditions()` 對這 46 個陣營來說 `conditions` 永遠是空陣列，跑到最後 `if conditions: ...` 的判斷因為空陣列是 falsy 而永遠不成立，函式回傳 `(False, None)`。

**影響**：這 46 個陣營（也就是全部 61 個陣營裡的絕大多數、包含所有地域型反賊玩法）**在遊戲中永遠無法透過自己的勝利條件獲勝**，唯一可能觸發的勝利只剩 `victory.py:11` 的「第20回合後紅軍自動獲勝」保底規則。這是所有落差裡影響最大的一項——不是某張卡或某個能力壞掉，而是超過 3/4 的可玩陣營整個「怎麼贏」都沒有實作。

**額外資料缺口**：`dian_zhuang`（滇（壯）) 的 `win_condition_text` 本身就是佔位字串「待補（使用者提供清單未明列）」——代表就算補完程式，這個陣營的勝利條件文字本身在資料裡都還沒定案，需要先回頭確認規則書／原始清單補上正確文字。

**建議改善方向**：
1. 為 46 個陣營設計並填入結構化 `win_conditions`（比照既有 `count_only` / `count_and_required` schema，把 `win_condition_text` 轉換成資料，而不是在程式裡寫正規表示式解析中文句子——後者維護成本高且容易誤判）。
2. `victory.py._check_player_conditions()` 已經有 `count_only`／`count_and_required` 分支可以直接沿用；需要確認 `scope` 值涵蓋「牆內」「牆外」「牆內與牆外」三種（目前 `_count_scope` 只認得 `牆內` 與 `牆內與牆外`，其餘一律當作「全部城鎮」處理，需要跟資料實際會出現的 scope 字串再核對一次）。
3. `dian_zhuang` 的勝利條件文字需要先跟使用者/規則文本確認正確內容，才能一併轉成資料。
4. 補完後務必寫端到端驗證（模擬讓一個地域型陣營達成自己的勝利條件，斷言遊戲正確判定獲勝），因為這是完全沒有測試覆蓋過的路徑。

---

### A2. 3 個具名能力字串完全沒有被解析，等同悄悄失效

**現況**：`server/game.py:2835` 的 `_resolve_ability_text(text)` 負責把 `abilities_text` 裡的 `【能力名稱】效果文字` 轉成程式可用的能力物件，靠兩個寫死的對照表（`mapping` 在 2839-2852 行、`direct` 在 2857-2866 行）比對能力名稱。如果名稱不在任一個表裡，函式回傳 `None`，該能力就被 `_resolve_faction_abilities()`（2869 行）悄悄丟棄——**沒有任何錯誤或警告**，遊戲會正常啟動，只是這個陣營該有的能力完全不存在。

實際核對全部 61 個陣營的 `abilities_text`，有 3 個能力名稱不在對照表裡：

| 能力 | 受影響陣營 | 效果文字 | 影響 |
|---|---|---|---|
| 【非暴力】 | `minyun`（民運派）、`gender_revolution`（性別革命） | 「禁止持有武裝類卡牌。」 | 這兩個陣營應該不能持有/打出武裝類卡牌，但因為能力沒被解析進 `_player_effective_abilities`，`_player_is_nonviolent()`（`game.py:2899`，實際擋人用資金/打出武裝卡的地方在 `game.py:2965`、`3920`、`4530`）永遠回傳 False，**這兩個陣營完全沒有被擋下打出武裝卡**。注意：其他陣營（如 `tibet_dharamsala`、`uyghur_munich`）的「非暴力」是走結構化 `abilities` 陣列直接定義（效果文字甚至用字不同：「禁止持有或裝備類卡牌」vs 這裡的「禁止持有武裝類卡牌」），那些陣營的限制是有效的；只有透過 `abilities_text` 字串宣告的這兩個陣營漏掉。 |
| 【紅軍派系】 | `reform_opening`（改革開放派） | 「每回合可檢視1次牌庫頂3張牌，將其以任意順序放回牌庫頂，並抽1張牌。」 | 整個能力沒有實作，這個陣營少一個主動能力可用。 |
| 【民族祭儀】 | 12 個陣營：`dian_zhuang, zhuang, yi, bai, hani, dai, miao, tujia, dong, buyei, yao, li`（雲貴少數民族類陣營） | 「在己方行動階段，可將1張手牌放進牌庫底，猜牌庫頂牌購買費用奇偶，並展示牌庫頂牌。若猜中可獲得2點宣傳與2點資金，沒猜中則獲得2點宣傳或2點資金。」 | 12 個陣營共用的核心主動能力完全沒有實作。程式裡已經有非常類似的機制可以參考重用：`賭徒耳語`（`game.py` 約 3232-3236 行附近，猜牌庫頂牌費用奇偶的邏輯）幾乎就是同一套猜奇偶機制，只是獎勵數值與「放1張手牌到牌庫底」的成本不同。 |

**建議改善方向**：
1. 在 `_resolve_ability_text` 的 `direct` 字典補上這 3 個能力的定義（或依效果性質建立新的 `ability_templates` ref，因為「民族祭儀」是 12 個陣營共用的，適合當作模板而非個別陣營硬編碼）。
2. 「非暴力」尤其要小心：目前程式裡已經有一個「非暴力」的名稱與行為（結構化陣營用的「禁止持有或裝備類卡牌」），如果直接把這兩個反賊陣營的「非暴力」也對應到同一個實作，效果範圍會從「武裝類」擴大成「武裝或裝備類」，跟資料文字不完全一致——需要先確認「武裝類」在卡牌分類（`action_cards.csv` 的「種類」欄位，如「武裝」）裡是否是獨立於「裝備」的類別，再決定是要新增一個範圍更窄的限制、還是沿用既有實作（若採用既有實作要在文件/TODO 裡明確記錄這個範圍差異是刻意簡化）。
3. 「民族祭儀」建議直接參考 `賭徒耳語` 的猜奇偶程式碼結構改寫（效果數值不同：猜中拿宣傳+資金各2點、沒猜中二選一拿2點宣傳或2點資金，且成本是「放1張手牌到牌庫底」而非賭徒耳語原本的成本，需要核對清楚兩者是否共用同一張源卡或各自獨立）。

---

### A3. [已修正 2026-07-10] `hong_kong` ↔ `yue`(粵) / `aomen`(澳門) 的共用組織規則只有單向生效

**現況**：`server/game.py:3409` 的 `_factions_sharing_with(faction_id)` 決定某陣營可以把哪些其他陣營的組織算進自己的「共用組織」數量。它先讀結構化欄位 `shared_organizations_with`（目前只有 `taiwan_green`、`taiwan_blue`、`hu` 三個陣營有填這個結構化欄位），再用**寫死的中文子字串比對** `special_rules` 陣列裡的文字：

```python
for text in faction.get('special_rules', []) or []:
    if '共用組織' in text:
        if '粵、澳門' in text:
            shared.update(['yue', 'aomen'])
        if '藍線臺灣' in text:
            shared.update(['taiwan_blue'])
        if '綠線臺灣' in text:
            shared.update(['taiwan_green'])
```

實際核對所有帶「共用組織」字樣的 `special_rules`：

| 陣營 | special_rules 文字 | 是否被上面 3 個 pattern 命中 |
|---|---|---|
| `hong_kong` | 「可與粵、澳門反賊共用組織。」 | ✅ 命中『粵、澳門』 |
| `republican` | 「遊戲過程中可與藍線臺灣共用組織。」 | ✅ 命中『藍線臺灣』 |
| `underground_church` / `gender_revolution` / `hakka` / `chaoshan` / `min` / `wuyue` / `hu` | 「遊戲過程中可與綠線臺灣共用組織。」 | ✅ 命中『綠線臺灣』 |
| `dian` | 「遊戲過程中可與藍線臺灣共用組織。」 | ✅ 命中『藍線臺灣』 |
| **`yue`（粵）** | 「遊戲過程中可與香港共用組織。」 | ❌ **沒有任何 pattern 包含『香港』，完全沒被命中** |
| **`aomen`（澳門）** | 「遊戲過程中可與香港共用組織。」 | ❌ **同上，沒被命中** |

**影響**：`hong_kong` 這邊看得到 `yue`／`aomen` 的組織算共用（因為 `hong_kong` 自己的文字命中了『粵、澳門』），但反過來從 `yue`／`aomen` 玩家視角呼叫 `_factions_sharing_with('yue')` / `_factions_sharing_with('aomen')` 時，`shared` 會是空集合——也就是說**這組共用組織關係只有單向生效**：`hong_kong` 玩家的瓦解/移動/建立判斷會把 `yue`/`aomen` 的組織當自己人，但 `yue`/`aomen` 玩家自己卻無法把 `hong_kong` 的組織當共用對象使用。從三方各自的 `special_rules` 文字（`hong_kong`、`yue`、`aomen` 三邊都各自宣告了同一組共用關係）來看，這應該是設計上要雙向對稱的關係，目前的字串比對寫法漏掉了其中一個方向。

**建議改善方向**：這個寫死子字串比對的方式本身就很脆弱（任何 `special_rules` 文字措辭一改就會漏判，正如這次找到的例子），建議：
1. 短期修法：在 pattern 清單裡補上 `'香港' in text → shared.update(['hong_kong'])`。
2. 中期建議：把「共用組織」關係整併成資料層的結構化欄位（比照 `taiwan_green`/`taiwan_blue`/`hu` 已經在用的 `shared_organizations_with` 陣列），逐一幫其餘用文字宣告共用關係的陣營（`hong_kong`, `republican`, `underground_church`, `gender_revolution`, `hakka`, `chaoshan`, `min`, `wuyue`, `yue`, `aomen`, `dian`）都補上結構化欄位，之後 `_factions_sharing_with` 可以只讀結構化欄位、不用再猜字串，一次消除同類型的問題（也方便未來新增陣營時不會又漏掉）。

**修正記錄（2026-07-10）**：已採用短期修法，在 `_factions_sharing_with` 補上 `'香港' in text → shared.update(['hong_kong'])`。驗證：`python3 scripts/validate_yue_aomen_hongkong_shared_org.py`（5/5 passed，涵蓋兩個新修正方向、兩個既有方向回歸測試、一個無關陣營 sanity check）；proof：`docs/records/faction-ui/YUE_AOMEN_HONGKONG_SHARED_ORG_FIX_VALIDATION_20260710.{json,md}`；`TODO.md` 已同步新增對應 `[done]` 條目。中期建議（把全部共用組織關係轉成結構化欄位）尚未執行，維持待處理。

---

### A4. `rules.md`「共同勝利：達成2/3條件」在目前資料下缺乏明確對應

**現況**：`victory.py:59-63` 實作了「條件數 × 2 / 3（無條件進位為至少1個）」的共同勝利門檻，對應 `rules.md` 第138-140行「達成 2/3 條件 → 視為共同勝利」。但目前 61 個陣營裡，有結構化 `win_conditions` 的 15 個陣營，每個陣營實際上只有 1（極少數 2，如 `red_army` 的 `default_survival` + `taiwan_override`，但這兩者其實是互斥的「OR」關係、不是可疊加湊比例的條件）張條件；其餘 46 個陣營目前完全沒有結構化條件（見 A1）。也就是說，在目前資料下，「2/3 條件」這個門檛公式實際上永遠等同「達成當下唯一的那 1 個條件」，跟「多條件裡湊滿 2/3」的原始語意對不太上。

**建議改善方向**：這比較像是規則設計本身待釐清、而非單純的程式 bug——需要跟使用者/規則文本確認：「2/3 條件」是否原本就是設計給「未來可能每個陣營有多個可疊加條件」的彈性框架（目前資料還沒有這種陣營，所以看不出效果）？還是規則書這段文字其實對應到別的東西（例如反共陣營全體裡有 2/3 玩家達成條件才算共同勝利，而不是單一玩家的條件裡湊 2/3）？建議列為「待確認規則語意」項目，先不動程式，等確認後再決定要不要調整 `_check_player_conditions` 的門檛公式。

---

## B. 卡牌規則（`data/raw/*.csv`）落差

> 這部分由兩個並行的程式碼審查代理（general-purpose agent）分別針對 `action_cards.csv`（46 張行動卡）與 `support_cards.csv` + `event_and_era_cards.csv`（奧援卡／事件卡／時代關卡）做逐卡比對，方法是在 `server/game.py` 的 `play_card()` 分派邏輯、`server/effect_engine.py` 的 etype 分派、以及事件/時代結構化資料裡找每張卡對應的實作並核對效果文字是否一致。

### B1. 奧援卡（`support_cards.csv`）—— 已完成比對

**資料鏈路澄清**：奧援卡的「區域主導者優待」實際比對邏輯不是直接讀 CSV，而是讀一份由腳本產生的中介資料 `data/cards/support_taxonomy.v1.1.json`（產生器：`scripts/build_support_card_taxonomy.py`，來源：`data/cards/support_cards.v1.1.json`），再由 `server/game.py:2902-2949` 的 `_support_taxonomy_entry` / `_support_card_tier` 讀取判斷等級，效果分派在 `server/game.py:2072-2124` 的 `_resolve_support_card_effect`。

**發現的落差：**

- **[已修正 2026-07-10] (B1-a)『東洋奧援』的中介資料 `data/cards/support_taxonomy.v1.1.json` 本身已損毀/過期，與它自己的產生腳本重新產生的結果不一致**：目前檔案裡「東洋奧援」的其中一個地區變體只保留了「本地區（東洋）」的 III 級條件、缺少 II 級條件；另一個變體只保留「臺灣、南洋」這組地區搭配，CSV 規定的第二組地區搭配「北國、英美」完全遺失。實際影響：玩家若同時主導北國＋英美（但不主導東洋/臺灣/南洋），應該要能達到 II 級（「在牆內於己方組織1格內建立1個組織」）卻會被卡在 I 級（僅獲得2點宣傳）。用現有產生器腳本重新根據 `support_cards.v1.1.json` 跑一次可以重現正確的4地區結構，證實這是資料檔損毀／未同步，不是刻意設計。**建議改善**：重新執行 `scripts/build_support_card_taxonomy.py` 產生正確的 `support_taxonomy.v1.1.json` 並 commit，同時建議之後把「產生器輸出是否與來源資料同步」做成一個可重複執行的驗證腳本（避免下次來源資料更新又忘記重新產生）。

  **修正記錄（2026-07-10）**：已重新執行 `scripts/build_support_card_taxonomy.py` 重新產生 `data/cards/support_taxonomy.v1.1.json`（補回「北國、英美」配對）。修正資料後，另外發現並一併修正了一個原本被資料損毀遮蔽、從未在正常遊戲中觸發過的程式碼 bug：`server/game.py:_resolve_support_card_effect` 對 `東洋奧援` tier2 有一段 `region_index == 0` 特例，會誤回傳跟 tier3 相同的「無視距離建立」效果，而不是 tier2 該有的「1格內建立」；因為資料損毀時 index0 幾乎不可能真的走到 tier2 分支，所以這段錯誤程式碼直到資料修正後才會被觸發（此時 index0 變成「臺灣、南洋」配對）。已移除該特例分支，統一回傳 `interactive_build_near_inner`。驗證：`python3 scripts/validate_east_asia_support_taxonomy_fix.py`（4/4 passed）；proof：`docs/records/support-cards/EAST_ASIA_SUPPORT_TAXONOMY_FIX_VALIDATION_20260710.{json,md}`；`TODO.md` 已同步新增對應 `[done]` 條目。

- **(B1-b)『南洋奧援』I 級「抽1張牌，再從所有手牌中棄掉1張牌」的棄牌沒有給玩家選擇權，效果等同沒抽沒棄**：實作是直接 `player.hand.pop()`，而抽到的牌是被 append 到手牌尾端，所以 `pop()` 彈出的正好就是剛抽到的那張牌——等於「抽1張又立刻棄掉同一張」，淨效果是 no-op，跟卡面文字暗示的「玩家可以從所有手牌中任選1張棄掉」（也就是抽到的新牌可能被留下、棄掉舊手牌）不符。**建議改善**：改成先抽牌加入手牌，再讓玩家（或依現有其他棄牌選擇的既有 UI 模式）從全部手牌中任選1張棄掉，而不是寫死彈出最後一張。

- **(B1-c) 設計語意待確認（跨7張區域門檻奧援卡）**：`_support_card_tier`（`game.py:2928-2949`）目前對「一組2個地區」的 II 級門檻是要求「同時主導這2個地區」（AND），但 CSV 欄位命名（第二個「區域主導者優待」欄位讀起來像是「另一種也能達到同樣II級效果的替代地區組合」）以及「一組2個地區共用同一段 II 級效果文字」的資料結構，讀起來更像是「主導其中任一個地區即可」（OR）。現有的 `docs/records/support-cards/SUPPORT_CARD_EFFECTS_RUNTIME_VALIDATION.json` 驗證紀錄目前只測過「同時主導兩地區」的情境，沒有測過「只主導其中一個地區」的情境，無法排除 AND 是刻意設計。**建議**：這條在真的動程式前，需要先跟使用者/規則文本確認 AND vs OR 的正確語意，影響全部7張區域門檻奧援卡（英美、東洋、南洋、歐洲、北國、臺灣、天方奧援）。

其餘奧援卡（英美奧援、印度奧援、天方奧援、歐洲奧援）三個等級效果經比對皆與 CSV 文字一致（OK），`北國奧援`、`紅軍奧援` 因已在 TODO.md 追蹤故本次略過深入比對。

### B2. 事件卡與時代關卡（`event_and_era_cards.csv`）—— 已完成比對，未發現落差

事件卡（13 種，含卡牌張數=2 的重複事件）與時代關卡（8 個陣營大類）經比對，觸發條件追蹤（`_track_event_progress` 等，`game.py:389-435`）、結算邏輯（`_settle_current_event`，`game.py:806-830`）、效果套用（`_apply_event_effect`，`game.py:652-830+`）與 `data/events_structured.v1.1.json`／`data/era_structured.v1.1.json` 逐一核對後皆為 **OK**，包含幾個原本容易出錯的細節都有正確處理：`貿易戰加劇`的「購買英美奧援 *或* 費用≥4」正確用 OR 邏輯（`_event_purchase_trigger_matches`）；`北京政爭`的「藉由卡牌效果或能力」抽牌正確排除一般回合補牌（`source not in {'refill','era'}`）；`上海合作組織`的「北國」地區別名、`一帶一路`系列的無視距離建立都對應正確。時代關卡8個大類（香港/蒙古/藏國/哈薩克/維吾爾/滿洲/反賊/臺灣）觸發門檻與效果分派也都對應到程式碼（`game.py:1394-1912`、`4687-5117`），抽查哈薩克的雙條件 AND 判定正確。這部分沒有需要規劃改善的項目。

### B3. 行動卡（`action_cards.csv`，46 張）—— 已完成比對

**架構**：46 張裡有 44 張走通用分派——`data/action_cards_structured.v1.1.json` 把每張卡的效果編碼成一串 typed steps，`server/action_engine.py:ActionCardEngine.execute()` 依序透過 `server/effect_engine.py:EffectEngine.execute()`（依 `etype` 分派）執行；`追隨者`／`樂捐者`是起始牌、`無效果`，本來就不需要任何實作，正確對應。大部分卡牌（`宣傳家`、`思想家`、`資助者`、`資本家`、`分神`、`交通經驗`系列、`領導/謀劃/戰略`、`合作談判`、`高效行動`、`乘勝追擊`、`網羅人才`、`凝聚共識`、`思想建設`、`內應間諜`、`走漏風聲`、`地下黨`、`組織經驗丙/乙`、`批判`、`批鬥`、`武裝者/小隊/集團`、`爆料黑幕`、`輿論丕變`、`產業滲透`、`企畫遊說`）比對後都是 **OK**，效果數值、觸發條件、有條件的「移除本牌才生效」gating（透過 `optional_trash` pending choice + `game.py:_resume_after_optional_trash`）都跟 CSV 文字一致。`模仿戰術`、`誘導虛耗`、`點燃熱情`、`離間` 因已在 TODO.md 追蹤，本次略過深入比對。

以下是**新發現、目前 TODO.md 沒有追蹤**的落差：

- **`樹立信心`：條件判定看錯欄位，跟已追蹤的 `點燃熱情` 是同一種 root cause，但這張卡本身沒被列進 TODO.md**。`conditional_draw` 的 `played_money_card` 判定條件（`game.py:4001-4002`）目前是檢查該回合打出的牌「種類（`card_type`）是否等於 `money`」，而不是檢查「購買費用是否包含資金成分」。例如 `謀劃`／`高效行動`／`誘導虛耗` 種類是「指揮」但購買費用含資金，玩家打出這些牌後應該要能讓 `樹立信心` 額外抽牌，實際上不會觸發。

- **`派遣間諜`：犧牲己方組織與尋找對手目標的順序顛倒，可能導致「犧牲了組織卻沒瓦解到敵方」**。程式（`effect_engine.py:543-572`）先選一個「在敵方組織範圍內」的己方城鎮當犧牲品並**立刻**從 `player.organizations` 扣掉／移除，然後才用 `_find_target_town_within_steps_of_player` 重新搜尋敵方目標——但這個搜尋函式是根據玩家**剩下的**組織重新算範圍。如果被犧牲的那個組織剛好是唯一符合條件（在敵方組織1格內）的組織，犧牲之後搜尋不到目標，函式靜默失敗——組織已經被犧牲掉了，但完全沒有瓦解到任何敵方組織。規則文字要求的是「以瓦解**該（犧牲的）**組織1格內的敵方組織為代價」，範圍應該用犧牲前那個組織的位置去找，不是犧牲後重算。

- **`情報網`：非反應時機下，選項C（取消對方能力）仍然可以被選、但選了沒有任何效果**。`choose_one`（`effect_engine.py:399-419`）不管是不是在別人的反應時機被打出，永遠把三個選項都列出來，包含選項C「其他玩家行動時打出，取消1張對方所打出行動卡之能力」。如果玩家在自己回合正常打出這張卡並選了C，會呼叫 `cancel_card` 但因為不在真正的反應情境裡，只會記一筆「canceled unknown card」的日誌、沒有任何實際效果——玩家會以為選項有效但其實是空轉。真正的反應流程（`game.py:3860`）其實有正確跳過 `choose_one`、直接走 `cancel_card`，所以這個問題只發生在「正常回合內打出情報網」的路徑。應該要在非反應情境下直接不提供/停用選項C。

- **`組織經驗甲`：問題比 TODO.md 現有記錄的還深，缺了兩整段規則子句**。TODO.md 目前只記錄「缺少確認是否要多花4點以上卡牌」的 UI 流程問題；但實際上 `data/action_cards_structured.v1.1.json` 裡這張卡的結構化效果就只有 `[{"type":"build","range":"ignore_distance"}]` 一步，代表整段規則完全沒有程式對應：(1)「每從手上棄掉1張購買費用4點以上的牌，可重複上述動作1次」——完全沒有任何重複建立的迴圈/邏輯存在；(2)「無法無視距離建立牆內組織者，本牌於牆內建立組織距離為1格」——這是給「本來就不能無視距離建立」的陣營（例如 A2 提到的 `uyghur_munich` 的『新疆社會管控』限制）的例外規則，但 `_card_build_town_choices`（`game.py:1034`）目前只有 `ignore_distance`（全部城鎮皆可）跟一般固定範圍 BFS 兩種分支，沒有針對這張卡特別處理「距離改為1格」的例外。建議把 TODO.md 對應項目的範圍描述更新為涵蓋這兩段，而不只是確認流程。

- **`行動預告` / `行動募資`：本回合買了2張以上的牌時，玩家沒有選擇要把哪張放回牌庫頂，永遠自動選最近買的那張**。兩張卡共用同一個 `topdeck_purchased_this_turn` 實作（`effect_engine.py:422-430`），直接從 `turn_log['purchased_cards_this_turn']` 挑「最近一張還在棄牌堆的牌」，沒有讓玩家選。因為 `buy_card`（`game.py:4519`）本身沒有限制每回合只能買1張，所以「本回合買了2張以上」是完全合法會發生的情況，此時卡面文字「將本回合購得的**1張**牌置於牌庫頂」隱含的玩家選擇被跳過了。

- **[已修正 2026-07-10]『企業人脈』：可借用的牌被限制在隨機購買區，排除了常設購買區的6張牌**。`use_purchase_area_card`（`effect_engine.py:433-465`）的 `prefer_random_market:true` 讓查詢範圍從 `static_count`（常設購買區張數）之後開始算，也就是排除了 `宣傳家/思想家/資助者/資本家/分神/內鬥` 這6張常設購買區的牌。但 CSV 卡面文字是「將購買區面朝上的**任1張**牌暫時移出購買區」，沒有限定只能是隨機購買區，讀起來常設購買區的牌也應該可以被借用。

  **修正記錄（2026-07-10）**：已把 `data/action_cards_structured.v1.1.json` 裡 `企業人脈` 的 `prefer_random_market` 從 `true` 改成 `false`，可借用範圍改為涵蓋整個購買區。驗證：`python3 scripts/validate_business_network_static_purchase_area.py`（1/1 case、6 項 check 全過）；proof：`docs/records/action-cards/BUSINESS_NETWORK_STATIC_PURCHASE_AREA_FIX_VALIDATION_20260710.{json,md}`；`TODO.md` 已同步新增對應 `[done]` 條目。

其餘標記為 OK 的卡牌裡有兩個值得記錄的「殊途同歸」實作細節（不是 bug，但供之後維護者理解程式脈絡用）：`凝聚共識`「棄掉的牌均非起始牌才加成」的判斷是直接寫在 `game.py:1554-1565` 內聯處理，繞過了 JSON 裡宣告但實際不會被執行到的 `conditional_bonus` 步驟；`武裝集團`「成功棄牌才抽牌」的判斷是在 `game.py:1394-1403` 用 `draw_on_success` 另外處理，同樣繞過了 JSON 宣告但無法被走到的 `conditional_draw` 步驟。這兩處目前行為是對的，只是 JSON 資料裡留著一段死代碼式的宣告容易誤導之後的維護者，可以考慮之後清理掉那兩段不會被執行到的 JSON 片段，但不急迫。

---

## C. `rules.md` 核心機制落差

### C1. 「放入分神或內鬥」段落的「可將內鬥改為雙倍分神」轉換規則完全沒有實作

**現況**：`rules.md:165-167`：
```
## 放入分神或內鬥
可將內鬥改為雙倍分神
```
全專案搜尋「雙倍分神」「distraction」相關轉換邏輯，`server/game.py` 裡所有「分神」「內鬥」的出現位置（約 38-39 行的供應數量常數、332 行的日誌文字、708/1933/2561/3143/3301 行的發牌/建立邏輯）都只是「把 N 張內鬥／分神加進某人牌庫或棄牌堆」，**沒有任何地方允許玩家選擇「把應該放入的1張內鬥改成放入2張分神」**。

**建議改善方向**：先確認這條規則實際的觸發時機（是任何要求「放入內鬥」的效果都可以選擇改放雙倍分神？還是僅限特定情境，例如內鬥供應量（`INTERNAL_CONFLICT` 常數 20 張，`game.py:39`）用完時的替代規則？）。確認後在所有「放入內鬥」的效果執行點（至少涵蓋 `add_internal_conflict` 這個 etype、以及 `game.py` 裡直接呼叫 `_gain_event_card(player, '內鬥', count)` 或建立 `Card('內鬥', ...)` 的地方）統一補上「玩家可選擇改為雙倍分神」的選項。

### C2. 事件牌庫建立規則「可抽除至多5張歲月靜好調整難度」是否有對應設定入口，需要確認

**現況**：`rules.md:71-75`：
```
取出事件卡，混洗後抽出20張，牌面朝下，作為事件牌庫。
※反共陣營如欲增加遊戲難度，混洗前可抽除若干張「歲月靜好」，至多抽除5張。
```
這是一個「遊戲開局設定選項」（optional house rule 難度調整），需要確認 `server/game.py`／`server/main.py` 建立事件牌庫的地方（可從 `event_and_era_cards.csv` 找「歲月靜好」的張數欄位、再找 game.py 讀取這份 CSV 建立事件牌庫的程式碼）目前是否只用「固定抽20張、不移除歲月靜好」的單一模式，還是真的有提供這個可選的難度調整入口（例如建房間時的一個 UI 選項或後端參數）。如果目前完全沒有這個選項，屬於「規則書裡列為可選規則，但沒有任何管道讓玩家實際使用」的落差，需要決定是否要補上（新增房間設定選項）或明確在文件/UI 標注「暫不支援，固定不抽除」。

### C3. 起始購買區組成規則（步驟⑧）建議做一次資料校驗，而非邏輯校驗

**現況**：`rules.md:79-87` 對購買區牌庫的組成有精確規格：「間諜/組織/整肅類行動卡全部 + 隨機18張奧援卡 + 隨機35張其它非起始一般行動卡」洗混，再翻5張作隨機購買區；牌庫用盡時「從剩餘行動卡中任取一疊補上」。`server/game.py:953` 的 `_initial_purchase_deck()` 已經是專門處理這段邏輯的函式，且 984-990 行也已經處理了「牌庫與棄牌堆都空的時候重新建立購買牌庫」，架構上看起來是對應到規則的。這裡不是懷疑「沒實作」，而是建議之後排改善優先序時，安排一次針對 `_initial_purchase_deck()` 的資料校驗型驗證（例如寫一個腳本組出牌庫後斷言：常設購買區恰好是那 6 張固定卡且不進牌庫、間諜/組織/整肅類全部進牌庫、奧援卡固定18張、其它一般行動卡固定35張），把規則書的精確數字轉成可重複執行的回歸測試，避免未來調整 CSV 資料或程式時不小心破壞這個比例卻沒人發現。

---

## 已知、與這次盤點重疊的既有 TODO.md 項目（避免重複規劃）

以下項目在 `TODO.md` 的「P1：LAN / end-to-end playtest feedback」區塊已經追蹤，本次盤點沒有重新深入，也不重複規劃：
- `誘導虛耗` 可移除對象範圍過大。
- `模仿戰術` 沒有跳出選擇視窗。
- `離間` 把內鬥放進紅軍自己牌堆。
- `組織經驗甲` 缺少額外花費的確認流程（**本次盤點發現範圍比 TODO 現有描述更深，見 B3**：除了確認流程，「棄4點以上卡牌可重複建立」與「無法無視距離建立的陣營改為距離1格」這兩段規則子句也完全沒有實作，建議更新 TODO 項目描述涵蓋這兩段）。
- `點燃熱情` 條件成立時應抽2張、實際只抽1張。
- `紅軍奧援` 由非紅軍玩家打出後沒有回到紅軍棄牌堆。
- `北國奧援` 兩段式瓦解流程中途關閉視窗會卡住。
- 移動翻牆成本與陣營適用城鎮判定（東沙→觀塘案例）。
- 本土社團觸發後多抽的牌被後續補牌流程蓋掉。
- 第20回合沒有直接宣告勝利者（注意：這一項跟本文件 A1/A3 是**相關但不同層次**的問題——TODO 裡的是「已經滿足紅軍保底勝利條件時，UI/流程沒有正確進入 finished 狀態並宣告」的**流程執行**問題；本文件 A1 是「46個陣營自己的勝利條件在資料/程式層面根本沒被實作」的**規則覆蓋率**問題，兩者都要修，且 A1 的影響範圍更大）。

---

## 建議的後續改善優先順序

### 第一梯隊——影響規則覆蓋率／可能整體破壞遊戲勝負判定，建議優先處理

1. **A1（46 個陣營勝利條件完全未實作）**——影響最大，超過 3/4 的可玩陣營目前無法自己獲勝。需要先做資料設計（把 `win_condition_text` 轉成結構化 `win_conditions`，含確認 `dian_zhuang` 的佔位文字），再擴充 `victory.py`（含核對 `_count_scope` 的 scope 字串涵蓋度），最後補端到端驗證。工作量偏大，建議拆成「資料轉換」與「程式擴充＋驗證」兩個子任務分開排期。
2. ~~**B1-a（`東洋奧援` 中介資料檔損毀）**~~ ——**已於 2026-07-10 修正**，詳見上方 B1-a 段落的「修正記錄」與 `TODO.md`。

### 第二梯隊——明確的規則實作缺口，修法清楚

3. **A2（3 個能力字串未解析，影響 15 個陣營）**——在既有對照表補項目；「非暴力」需先確認武裝/裝備分類範圍再決定要不要沿用既有實作，「民族祭儀」可參考 `賭徒耳語` 改寫。
4. ~~**A3（粵/澳門↔香港共用組織單向生效）**~~ ——**已於 2026-07-10 修正**（短期字串 pattern 修法），詳見上方 A3 段落的「修正記錄」與 `TODO.md`；中期把全部共用組織關係轉成結構化欄位的建議仍待處理。
5. **B3 中的 `派遣間諜`（犧牲組織後才找目標，可能白白損失組織卻沒瓦解到敵方）**——邏輯順序調整，屬於正確性 bug，建議提前處理。
6. **B3 中的 `樹立信心`（條件判定看種類而非購買費用組成，跟已追蹤的 `點燃熱情` 同根因）**——建議和 `點燃熱情` 一起修，兩者共用同一段判定邏輯調整。
7. **B3 中的 `組織經驗甲`（TODO.md 現有描述需擴大範圍，兩段規則子句完全未實作）**——請一併更新 TODO.md 描述再排入既有 P1 流程處理。
8. **B1-b（`南洋奧援` I 級棄牌等於沒抽沒棄）**——邏輯明確，改成真正給玩家選擇棄哪張。
9. **B3 中的 `情報網`（非反應時機下選項C選了沒效果）**——應在非反應情境停用/隱藏選項C。

### 第三梯隊——UI/選擇權相關的小落差，可與既有 P1 UI 修正一起排

10. **B3 中的 `行動預告` / `行動募資`（本回合買超過1張時沒有選擇權，自動選最近一張）**——需要補一個「選擇要頂牌哪一張」的選擇流程，跟既有 P1 裡其他「缺少確認/選擇視窗」類項目性質相近，可一起規劃 UI。
11. ~~**B3 中的 `企業人脈`（借用範圍誤排除常設購買區）**~~ ——**已於 2026-07-10 修正**，詳見上方段落的「修正記錄」與 `TODO.md`。

### 第四梯隊——需要先確認規則語意，或優先度較低的保養性質項目

12. **B1-c（跨7張區域門檻奧援卡的 AND/OR 語意待確認）**——需要先跟使用者/規則文本確認，才能決定是否要改 `_support_card_tier`，影響面較廣（英美/東洋/南洋/歐洲/北國/臺灣/天方奧援）所以建議提早確認、但不代表要提早動工。
13. **C1（雙倍分神轉換規則未實作）**——需要先確認觸發時機，再排入。
14. **C2（歲月靜好難度調整選項）**、**C3（購買區組成資料校驗）**、**rules.md「2/3共同勝利」語意釐清**、**JSON 裡 `凝聚共識`/`武裝集團` 的死代碼 `conditional_bonus`/`conditional_draw` 宣告清理**——優先度最低，屬於錦上添花／保養性質，可排在最後。

事件卡與時代關卡（B2）比對後沒有發現落差，不需要排入改善清單。

每項改善完成後，比照這個專案既有慣例（見 `TODO.md` 現有條目風格）：寫 root cause、修正摘要、驗證指令與 proof 路徑，更新對應的追蹤清單。
