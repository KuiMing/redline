# REBEL_REBUILD_STATUS

日期：2026-05-04

## 本輪已完成

已根據使用者提供的權威清單，重建一份新的反賊 faction data source：

- `data/factions/rebel_authoritative_rebuilt.v1.json`

## 這份新資料的定位

這是一份 **authoritative rebuilt source**，用來取代目前 `all_faction.json` 中不完整、過時的 rebel faction 子集。

## 已納入的內容

- 政治類陣營
- 地域類陣營（華南 / 華中 / 華北 / 西南 / 西北）
- 少數民族陣營
- bases（保留 literal rule options）
- abilities_text
- special_rules
- win_condition_text

## 目前狀態

### 已完成
- 權威 rebel roster 已整理為一份新資料檔
- 新增 / 缺漏反賊陣營已全部收錄到這份 rebuilt source

### 尚未完成
- 尚未把這份 rebuilt source 接回 runtime `all_faction.json`
- 尚未把新 rebel factions 的 abilities / win conditions 全部轉成 engine-friendly structured schema
- faction selection / base selection / victory engine 仍未正式切換到這份新 rebel source

## 下一步

1. 把 `rebel_authoritative_rebuilt.v1.json` 整合進 runtime faction source
2. 更新 faction selection / category UI，使「反賊」第二層使用這份新清單
3. 重寫對應的 victory / bases / validation 流程
