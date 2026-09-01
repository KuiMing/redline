# 區網連線資訊顯示 驗證

可重跑指令：`uv run --with playwright python scripts/validate/validate_lan_info_display.py`

- total: 6 / passed: 6 / failed: 0
- screenshots: docs/records/playtest-flow/lan_info_display.png, docs/records/playtest-flow/lan_info_domain_without_internal_port.png

## Results
- ✅ `server_info_returns_lan_ip_and_port` — {"info": {"base_url": "http://192.168.10.192:8765", "lan_ip": "192.168.10.192", "port": 8765}}
- ✅ `lobby_shows_lan_url` — {"lan_url": "http://192.168.10.192:8765", "expected": "http://192.168.10.192:8765"}
- ✅ `copy_button_reports_copied` — {"status": "連線網址已複製，分享給其他玩家後，記得也給他們房間代碼。"}
- ✅ `server_info_domain_omits_internal_port` — {"info": {"base_url": "https://redline.example.com", "lan_ip": "redline.example.com", "port": null}, "expected": "https://redline.example.com"}
- ✅ `lobby_shows_domain_without_internal_port` — {"lan_url": "https://redline.example.com", "expected": "https://redline.example.com"}
- ✅ `browser_console_has_no_errors` — {"errors": []}
