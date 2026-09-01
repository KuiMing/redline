# 時代關卡觸發規則第一輪修正

已修正

## 1. 移除強制啟動香港時代

原本 `Game.__init__()` 有測試殘留：

```python
# TEMP: force activate hong_kong era for UI test
```

現在已移除。

結果：

- 新局不會自動啟動 `hong_kong`
- 時代關卡必須真的達成觸發條件才會啟動

---

## 2. 補上哈薩克時代關卡

新增到：

- `data/era_structured.v1.1.json`

新增：

- `[哈薩克]伊塔事件`

目前結構化條件為：

- 哈薩克陣營
- 在 `turkestan` 區域至少 7 個組織
- 在 `china` 區域至少 3 個組織

我這邊把原文的「北國」先對應成目前 `board region` 裡可用的 `turkestan`，因為資料裡沒有獨立 `northland region`。這點後續如果你要細分「北國」區域，我們可以再調整 region 資料。

---

## 3. 時代觸發現在會檢查指定陣營 / camp

以前：

- 只要任意玩家在指定區域組織數達標，就可能觸發該時代。

現在：

- 香港時代只會由香港陣營觸發
- 蒙古時代只會由蒙古陣營觸發
- 西藏時代只會由西藏 camp 觸發
- 維吾爾時代只會由維吾爾 camp 觸發
- 滿洲時代只會由滿洲陣營觸發
- 臺灣時代只會由臺灣 camp 觸發
- 反賊時代只會由 rebel camp 觸發
- 哈薩克時代只會由哈薩克陣營觸發

---

## 新增驗證

新增：

- `scripts/validate/validate_era_rules.py`
- `ERA_RULES_VALIDATION.json`
- `ERA_RULES_VALIDATION.md`

驗證結果：

- `ERA_RULES_VALIDATION: 5/5 PASS`

涵蓋：

1. 新局不會強制啟動香港時代
2. 非香港陣營即使在香港區有 10 組織，也不會觸發香港時代
3. 香港陣營在香港區達 10 組織會觸發香港時代
4. 哈薩克時代定義存在
5. 哈薩克時代需哈薩克陣營且滿足雙區域條件才會觸發

---

## 回歸測試

已跑過並通過：

- `python3 scripts/validate/validate_era_rules.py` — PASS
- `python3 scripts/validate/validate_purchase_rules.py` — PASS
- `python3 scripts/validate/validate_support_purchase_deck_runtime.py` — PASS
- `python3 scripts/validate/validate_deck_lifecycle.py` — PASS
- `python3 scripts/validate/validate_card_action_correctness.py` — PASS
- `python3 scripts/validate/validate_movement_rules.py` — PASS
- `python3 scripts/validate/validate_full_gameplay_2p.py` — PASS
- `python3 scripts/validate/validate_full_gameplay_multi.py` — PASS
- `/usr/bin/python3 scripts/validate/validate_setup_rules.py` — PASS
- `git diff --check` — PASS

---

## Commit

已提交：

- `0e85005` — `Fix era trigger rules`

目前本次相關檔案 clean。只剩既有未追蹤截圖：

- `setup_rules_validation.png`

未納入 commit。
