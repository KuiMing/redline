# Remaining Six Event Cards Raw Alignment Audit — 2026-05-24

Status: passed

Scope: raw 13 張事件卡中尚未逐張重審的 6 張。

Conclusion: 6 張 raw text 與 structured data 目前對齊；本次補 runtime validator 覆蓋缺口，未改 UI。

## 全國人大召開

- Raw 任務條件：[反抗必隨壓迫而起]使用或觸發至少1次陣營特殊能力
- Raw 成功獎勵：[覺醒之士投身我方]抽1張牌
- Raw 失敗懲罰：[鐵拳之下同志潰散]被紅軍無視距離瓦解1個牆內組織
- Structured trigger：`{'type': 'use_faction_ability', 'count': 1}`
- Structured success：`{'type': 'draw', 'count': 1}`
- Structured failure：`{'type': 'red_dissolve', 'count': 1, 'scope': '牆內'}`
- Finding：raw/structured 對齊；已新增 validator 覆蓋陣營能力成功抽牌與失敗紅軍只可瓦解牆內組織。

## 香港抗暴之戰

- Raw 任務條件：[運用資金支援前線]打出至少1張購買費用有資金的卡牌
- Raw 成功獎勵：[風雨同路手足同情]獲得2張宣傳家
- Raw 失敗懲罰：[兄弟爬山各自努力]己方選1張手牌棄掉
- Structured trigger：`{'type': 'play_card_with_money', 'count': 1}`
- Structured success：`{'type': 'gain_card', 'card': '宣傳家', 'count': 2}`
- Structured failure：`{'type': 'discard_self', 'count': 1}`
- Finding：raw/structured 對齊；既有 validator 已覆蓋資金卡成功、宣傳家 static supply、失敗自選棄手牌。

## 重大災難

- Raw 任務條件：[寧鳴而死不默而生]打出至少1張購買費用有宣傳的卡牌
- Raw 成功獎勵：[悲憤無畏的吹哨人]獲得1張宣傳家
- Raw 失敗懲罰：[大難當前無暇他顧]己方選1張手牌棄掉
- Structured trigger：`{'type': 'play_card_with_propaganda', 'count': 1}`
- Structured success：`{'type': 'gain_card', 'card': '宣傳家', 'count': 1}`
- Structured failure：`{'type': 'discard_self', 'count': 1}`
- Finding：raw/structured 對齊；既有 validator 已覆蓋宣傳卡成功取得宣傳家。

## 藏印邊境軍事對峙

- Raw 任務條件：[趁機加速組織工作]在牆內建立至少1個組織
- Raw 成功獎勵：[裡應外合趁虛而入]進行2次組織遷移
- Raw 失敗懲罰：無
- Structured trigger：`{'type': 'build_organization', 'count': 1, 'scope': '牆內'}`
- Structured success：`{'type': 'move', 'count': 2}`
- Structured failure：`{'type': 'none'}`
- Finding：raw/structured 對齊；已新增 validator 覆蓋牆內建組織成功後獲得 2 次移動。

## 東突厥集中營

- Raw 任務條件：[保衛出逃的見證者]打出至少1張購買費用有宣傳的卡牌
- Raw 成功獎勵：[發生在我身上的事]獲得1張宣傳家
- Raw 失敗懲罰：[出逃者遭紅軍謀害]被紅軍隨機棄掉1張手牌
- Structured trigger：`{'type': 'play_card_with_propaganda', 'count': 1}`
- Structured success：`{'type': 'gain_card', 'card': '宣傳家', 'count': 1}`
- Structured failure：`{'type': 'discard_random', 'count': 1}`
- Finding：raw/structured 對齊；已新增 validator 覆蓋宣傳卡成功取得宣傳家與失敗隨機棄手牌。

## 北京政爭

- Raw 任務條件：[試圖伸出友誼之手]藉由卡牌效果或能力從牌庫抽取至少1張牌
- Raw 成功獎勵：[暗送秋波互為照應]抽1張牌
- Raw 失敗懲罰：無
- Structured trigger：`{'type': 'draw', 'count': 1}`
- Structured success：`{'type': 'draw', 'count': 1}`
- Structured failure：`{'type': 'none'}`
- Finding：raw/structured 對齊；既有 validator 已覆蓋抽牌 trigger 成功與成功獎勵抽牌。

## Validator coverage added/confirmed

- `test_remaining_six_event_structured_matches_raw_rules`：一次鎖定 6 張 raw/structured 對齊。
- `test_national_people_congress_faction_ability_success_draws`：全國人大成功路徑。
- `test_national_people_congress_failure_red_dissolves_wall_org_only`：全國人大失敗紅軍牆內瓦解。
- `test_tibet_border_build_wall_org_grants_two_moves`：藏印邊境成功給 2 move。
- `test_east_turkestan_success_and_failure_paths`：東突厥成功/失敗。
