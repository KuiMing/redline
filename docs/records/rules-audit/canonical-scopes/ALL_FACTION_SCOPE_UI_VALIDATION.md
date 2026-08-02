# 全陣營時代／勝利scope正式UI驗證

- 結果：**31/31 passed**

## Scenarios

- 蒙古：4個蒙古統治但牆外城鎮不觸發；4個牆內觸發。
- 香港：14個牆外不勝；14個牆內勝利。
- 紅軍：臺灣14個組織只有在臺灣玩家參戰時才勝利。

## Checks

- PASS `mongolia_outside_server_counts`
- PASS `mongolia_outside_count_conservation`
- PASS `mongolia_outside_era_result`
- PASS `mongolia_outside_victory_result`
- PASS `mongolia_outside_formal_status_split`
- PASS `mongolia_inside_server_counts`
- PASS `mongolia_inside_count_conservation`
- PASS `mongolia_inside_era_result`
- PASS `mongolia_inside_victory_result`
- PASS `mongolia_inside_formal_status_split`
- PASS `hong_kong_outside_victory_server_counts`
- PASS `hong_kong_outside_victory_count_conservation`
- PASS `hong_kong_outside_victory_era_result`
- PASS `hong_kong_outside_victory_victory_result`
- PASS `hong_kong_outside_victory_formal_status_split`
- PASS `hong_kong_inside_victory_server_counts`
- PASS `hong_kong_inside_victory_count_conservation`
- PASS `hong_kong_inside_victory_era_result`
- PASS `hong_kong_inside_victory_victory_result`
- PASS `hong_kong_inside_victory_formal_victory_modal`
- PASS `red_taiwan_without_taiwan_server_counts`
- PASS `red_taiwan_without_taiwan_count_conservation`
- PASS `red_taiwan_without_taiwan_era_result`
- PASS `red_taiwan_without_taiwan_victory_result`
- PASS `red_taiwan_without_taiwan_formal_status_split`
- PASS `red_taiwan_with_taiwan_server_counts`
- PASS `red_taiwan_with_taiwan_count_conservation`
- PASS `red_taiwan_with_taiwan_era_result`
- PASS `red_taiwan_with_taiwan_victory_result`
- PASS `red_taiwan_with_taiwan_formal_victory_modal`
- PASS `browser_console_has_no_errors`

## Screenshots

- `docs/records/rules-audit/canonical-scopes/mongolia_outside.png`
- `docs/records/rules-audit/canonical-scopes/mongolia_inside.png`
- `docs/records/rules-audit/canonical-scopes/hong_kong_inside_victory.png`
- `docs/records/rules-audit/canonical-scopes/red_taiwan_with_taiwan.png`
