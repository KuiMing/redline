# Card Effect Audit P1 Findings

## Scope

Compared raw action-card text in `data/raw/action_cards.csv` against `data/action_cards_structured.v1.1.json`, `server/effect_engine.py`, and existing validators.

## Fixed in this pass

### 思想建設

- Raw text: `抽1張牌。本回合己方可建立組織的距離額外增加1格。`
- Previous structured effect: only `extend_build_range`.
- Problem: action mode did not draw 1 card.
- Fix: prepend `{"type":"draw","count":1}` before `extend_build_range`.
- Validator: `validate_card_effect_audit_p1.py`.

### 誘導虛耗

- Raw text: `抽1張牌。打出可移除本牌。若移除本牌，可選擇1位玩家，由該玩家選1張手牌棄掉。`
- Previous structured effect: `optional_trash` + `force_discard`.
- Problem: action mode did not draw 1 card.
- Fix: prepend `{"type":"draw","count":1}` before optional removal / discard effect.
- Validator: `validate_card_effect_audit_p1.py`.

## Remaining high-priority audit findings

These are not fixed in this pass; they need their own RED validators before production changes.

### 合作談判

- Raw text: choose 1 player; you and that player each draw 1; you gain 2 propaganda.
- Current structured/runtime: `shared_draw` draws all players and does not grant 2 propaganda.
- Risk: wrong in 3+ player games and missing resource gain.

### 網羅人才

- Raw text: choose any card from own deck into hand, then shuffle; Red Army may choose from deck or discard.
- Current structured/runtime: `peek_deck` + `topdeck_to_hand`, effectively top-deck draw only.
- Risk: major rule mismatch and missing Red Army variant.

### 模仿戰術

- Raw text: choose 1 player's top deck card, temporarily use it this turn, then return it to owner deck top.
- Current structured/runtime: `peek_deck` no-op + `topdeck_to_hand` from current player's own deck.
- Risk: major ownership/temporary-use mismatch.

### 情報網

- Raw text: choose one of three modes: add internal conflicts to up to 3 players, dissolve an opponent org, or reaction-cancel a card.
- Current structured/runtime: executes `add_internal_conflict` and `cancel_card` together, no dissolve option, no choice UI.
- Risk: multiple mutually exclusive effects executed together.

### 走漏風聲

- Raw text: choose 1 player, discard their deck top; if cost >= 1, add 內鬥 to their discard.
- Current structured/runtime: `peek_deck` no-op + unconditional `add_internal_conflict` to current player.
- Risk: wrong target, missing top-deck discard, missing cost condition.

### 行動預告 / 行動募資

- Raw text: put one card bought this turn on top of deck; gain 1 propaganda/money.
- Current 行動預告 structured/runtime: `topdeck_to_hand` + gain propaganda.
- Current 行動募資: missing from structured action cards entirely.
- Risk: wrong destination and missing card.

### Missing structured cards

Raw action-card table contains cards not present in structured action data:

- 企業人脈
- 產業滲透
- 企畫遊說
- 行動募資

These cannot be executed through the structured action engine until modeled.

## Suggested next fix

Fix `合作談判` next because it is small, deterministic, and affects 3+ player correctness:

1. RED validator: actor gains 2 propaganda; in a 3-player game only actor and one selected/target player draw, third player does not.
2. Implement explicit target handling or deterministic MVP target semantics.
3. Run card validators and full gameplay smoke tests.
