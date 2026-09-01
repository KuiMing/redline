# 時代關卡「無法無視距離建立牆內組織」＋ 時代關卡達成浮窗重新開啟（Validation）

Generated at: `2026-08-09T22:55:31`

Summary: 7 passed / 0 failed / 7 total.

可重跑指令（需先啟動伺服器於 127.0.0.1:8000）：
`python3 scripts/validate/validate_era_restrict_ignore_distance.py`

## rebels_era_ideologue_limited_to_one_step_inside_wall — passed

- era: [反賊]公知世代的終結
- origin: 上海
- near_inner: ['上海', '南京', '杭州']
- ui_candidate_count: 38
- ui_inner: ['南京', '杭州']
- ui_outer_count: 36
- screenshot: `docs/records/era-restrict-ignore-distance/ideologue-rebels-era-active.png`

## rebels_era_with_build_range_bonus_extends_to_two_steps — passed

- era: [反賊]公知世代的終結
- origin: 上海
- near_inner: ['上海', '南京', '杭州']
- ui_candidate_count: 43
- ui_inner: ['南京', '南昌', '合肥', '徐州', '杭州', '溫州', '青島']
- ui_outer_count: 36
- screenshot: `docs/records/era-restrict-ignore-distance/ideologue-rebels-era-bonus.png`

## no_era_control_still_ignores_distance — passed

- era: None
- origin: 上海
- near_inner: ['上海', '南京', '杭州']
- ui_candidate_count: 77
- ui_inner: ['三亞', '南京', '南寧', '南昌', '南陽', '合肥', '天津', '太原', '奇臺', '廈門', '廣州', '延安', '徐州', '德宏', '成都', '敦煌', '昆明', '昌吉', '杭州', '桂林', '梅州', '武漢', '海口', '深圳', '湛茂', '溫州', '潮州', '澳門', '濟南', '石家莊', '福州', '蘭州', '西安', '西寧', '西雙版納', '貴陽', '鄭州', '重慶', '銀川', '長沙', '青島']
- ui_outer_count: 36
- screenshot: `docs/records/era-restrict-ignore-distance/ideologue-no-era-control.png`

## kazakh_era_applies_the_same_restriction — passed

- era: [哈薩克]伊塔事件
- origin: 烏魯木齊
- near_inner: ['吐魯番', '奇臺', '巴音郭楞', '昌吉', '烏魯木齊']
- ui_candidate_count: 49
- ui_inner: ['奇臺', '昌吉']
- ui_outer_count: 47
- screenshot: `docs/records/era-restrict-ignore-distance/ideologue-kazakh-era-active.png`

## other_camp_unaffected_while_rebels_era_active — passed

- era: [反賊]公知世代的終結
- origin: 烏魯木齊
- near_inner: ['吐魯番', '奇臺', '巴音郭楞', '昌吉', '烏魯木齊']
- ui_candidate_count: 59
- ui_inner: ['伊寧', '克拉瑪依', '博爾塔拉', '可可托海', '哈密', '塔城', '奇臺', '奎屯', '敦煌', '昌吉', '格爾木', '阿勒泰']
- ui_outer_count: 47
- screenshot: `docs/records/era-restrict-ignore-distance/ideologue-other-camp-unaffected.png`

## east_asia_support_tier3_downgraded_by_era — passed


## era_achievement_modal_button_top_right_and_reopenable_by_every_player — passed

- 縮小鍵在浮窗內的相對位置: {'leftFrac': 0.853026055408971, 'topFrac': 0.02417186909866477, 'text': '縮到右上角'}
- screenshot(minimize_button): `docs/records/era-restrict-ignore-distance/era-modal-minimize-button-top-right.png`
- screenshot(minimized): `docs/records/era-restrict-ignore-distance/era-modal-minimized-pin.png`
- screenshot(reopened_trigger_player): `docs/records/era-restrict-ignore-distance/era-modal-reopened-by-trigger-player.png`
- screenshot(reopened_second_player): `docs/records/era-restrict-ignore-distance/era-modal-reopened-by-second-player.png`
