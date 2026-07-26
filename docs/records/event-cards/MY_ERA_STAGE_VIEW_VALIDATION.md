# 「我的時代關卡」遊戲內查看入口驗證

可重跑指令：`uv run --with playwright python scripts/validate_my_era_stage_view.py`

- total: 7 / passed: 7 / failed: 0
- base URL: http://127.0.0.1:8000
- screenshots: /Users/benmini/.openclaw/workspace/redline/docs/records/event-cards/my_era_stage_entry_position.png, /Users/benmini/.openclaw/workspace/redline/docs/records/event-cards/my_era_stage_pending.png, /Users/benmini/.openclaw/workspace/redline/docs/records/event-cards/my_era_stage_active.png

## Results
- ✅ `my_era_stage_button_visible_in_game_tabs` — {"visible": true, "text": "我的時代關卡"}
- ✅ `personal_info_tabs_sit_next_to_log_without_event_card_overlap` — {"logRight": 317.232421875, "factionLeft": 326.232421875, "factionRight": 419.9765625, "eraLeft": 428.9765625, "eraRight": 552.708984375, "eventLeft": 1075.5, "gapAfterLog": 9, "gapBetweenPersonalTabs": 9, "noEventOverlap": true}
- ✅ `adjacent_my_faction_entry_still_works` — {"button_visible": true, "modal_visible": true}
- ✅ `pending_taiwan_stage_shows_complete_text_card` — {"modalVisible": true, "title": "[臺灣]綏靖派反對介入對岸", "status": "尚未達成", "summary": "臺灣對共和國滲透日深 紅軍策動臺灣綏靖派阻礙反共工作", "sections": ["觸發條件", "紅軍壓制", "革命反撲", "效果期限"], "texts": ["[臺灣重建敵後工作]臺灣在牆內擁有至少7個有效組織", "[鼓吹停止挑釁紅軍]將3張內鬥放進臺灣棄牌堆", "[打擊國內綏靖主義]每當臺灣在臺灣城鎮建立至少1個組織時，獲得1點宣傳。持續2回合。", "持續 2 回合"], "imageCount": 0}
- ✅ `close_button_hides_my_era_stage_modal` — {"display": "none"}
- ✅ `active_mongolia_stage_shows_achieved_status_and_remaining_turns` — {"title": "[蒙古]莫日根事件爆發", "status": "條件已達成｜剩餘 1 回合", "activeClass": true, "stateId": "mongolia", "stateActive": true, "remaining": 1}
- ✅ `red_army_gets_clear_no_personal_stage_message` — {"title": "無個人時代關卡", "status": "此陣營沒有專屬時代關卡", "summary": "紅軍沒有個人時代關卡；其他陣營達成關卡後，效果仍會顯示於全桌的時代通知。", "projected": null}
