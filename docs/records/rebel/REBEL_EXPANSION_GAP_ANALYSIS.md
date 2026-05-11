# REBEL_EXPANSION_GAP_ANALYSIS

日期：2026-05-04

## 使用者提供的反賊權威清單

已另存為：
- `data/factions/rebel_expansion_authoritative.v1.json`

## 結論

目前遊戲中的 `all_faction.json` 與使用者剛提供的反賊權威清單 **不一致**。

也就是說：
- 現有 faction selection / rules / victory / bases / abilities
- 目前還沒有完整對齊到你剛提供的反賊清單

## 目前已存在於遊戲資料中的反賊 faction（舊）
- 滇 / 夜郎・黔 / 苗 / 傣
- 聯邦派 / 新左派 / 晉 / 齊
- 民國派 / 自由派 / 吳越 / 粵
- 回族 / 昭武・甘青寧 / 秦・關隴 / 宛 / 地下教會

## 你新提供、但目前遊戲資料尚未完整納入的反賊 faction（明顯缺口）
### 政治類新增
- 民運派
- 改革開放派
- 法輪功
- 性別革命

### 華南新增 / 差異
- 瓊
- 澳門
- 客家
- 潮汕
- 桂
- 贛
- 閩
- 滬

### 華中新增 / 差異
- 湘
- 楚
- 江淮
- 伊洛・豫

### 華北新增 / 差異
- 幽燕

### 西南新增 / 差異
- 渝巴
- 巴蜀
- 滇（壯）

### 少數民族新增 / 差異
- 壯
- 彝
- 白
- 哈尼
- 土家
- 侗
- 布依
- 瑤
- 黎
- 朝鮮

## 代表什麼

這不是只改 UI 名稱就能完成的事情，而是：

1. faction roster 要更新
2. bases 要更新
3. 特殊能力要更新
4. victory conditions 要更新
5. 可能還要補 shared_org / non-violence / extra starter / map dependency 等規則
6. faction selection 流程也要跟著重建

## 所以下一步

如果要把反賊完全整理進遊戲，最正確的下一步不是直接零碎 patch，
而是：

### 先做「反賊陣營資料重建」

也就是用你剛提供的清單重建一份新的、可執行的 rebel faction data source，然後再逐步接回：
- faction selection
- bases
- abilities
- victory engine
- gameplay validation
