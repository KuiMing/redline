# FACTION_INTEGRATION_V2

日期：2026-05-05

## 本輪完成

已將：
- `data/factions/rebel_authoritative_rebuilt.v1.json`
- 與現有 `all_faction.json` 中的非反賊 faction

合併成一份新的統一 faction 總表：

- `data/factions/all_faction.integrated.v2.json`

## 合併規則

- 保留舊 `all_faction.json` 中的 **非反賊 faction**
- 移除舊 `all_faction.json` 中混入的舊 rebel faction 子集
- 改以 `rebel_authoritative_rebuilt.v1.json` 的 **47 個反賊 faction** 取代

## 結果

- 原始 `all_faction.json` faction 總數：31
- 保留的非反賊 faction：14
- 新權威 rebel faction：47
- 新整合總表 faction 總數：61

## 目的

這份 `all_faction.integrated.v2.json` 的作用是：
- 成為下一步 runtime 切換前的統一總表候選
- 避免非反賊與反賊資料分裂維護
- 為 faction selection / base selection / victory / validation 後續切換提供單一來源

## 本輪尚未做

- 尚未修改 runtime 直接改讀 `all_faction.integrated.v2.json`
- 尚未把整合後的新 rebel faction 全部轉回原本 engine 使用的完整 structured ability / win condition schema
- 尚未重跑 opening flow 與全流程驗證
