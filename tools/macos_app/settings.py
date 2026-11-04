"""跨「遊戲連接埠改變」保留的玩家設定。

localStorage 綁 origin（含連接埠）。App 的優先埠被佔用而改用其他埠時，WebView 會看到一份空的
localStorage。pywebview 的 Cocoa 後端固定用 WKWebsiteDataStore.defaultDataStore()，會忽略
storage_path，也沒有其他方式讓不同埠共用儲存，所以由 launcher 明確搬移設定：

- 啟動後第一次載入：把 settings.json 的值寫回目前 origin（檔案較新，蓋過舊埠留下的值）。
- 之後定期把目前的值存回 settings.json。關閉 App 前約 2 秒內的變更可能來不及存。

只搬移下列明確列出的設定。刻意不搬移 redline.sessions.v1、redline.hotseat.v1
（含重連憑證與席位）與 redline.device_id.v1：房間只存在記憶體中，App 關閉就消失，這些值
重開後沒有用途，也不該寫進設定檔。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger("redline.app")

SETTINGS_VERSION = 1
PRESERVED_KEYS = (
    "redline.music.volume.v1",  # static/game_music.js
    "redline.controller.v1",  # static/controller_ui.js
    "redline.display.v1",  # static/living_room_core.js
)
CONTROLLER_KEY = "redline.controller.v1"
MAX_VALUE_LENGTH = 2048


def sanitize(raw) -> dict[str, str]:
    """只留下允許清單內、長度合理的字串值；其他一律丟棄。"""
    if not isinstance(raw, dict):
        return {}
    return {key: raw[key] for key in PRESERVED_KEYS if isinstance(raw.get(key), str) and len(raw[key]) <= MAX_VALUE_LENGTH}


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, str]:
        """損毀或不認識的版本一律視為沒有設定：設定遺失不該讓 App 無法啟動。"""
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            log.warning("ignoring unreadable settings file")
            return {}
        if not isinstance(payload, dict) or payload.get("version") != SETTINGS_VERSION:
            log.warning("ignoring settings file with unknown version")
            return {}
        return sanitize(payload.get("settings"))

    def save(self, settings) -> bool:
        """有變更才寫入（原子取代）。回傳是否寫入。"""
        clean = sanitize(settings)
        if clean == self.load() and self.path.exists():
            return False
        temp = self.path.with_name(self.path.name + ".tmp")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"version": SETTINGS_VERSION, "settings": clean}, handle, ensure_ascii=False)
        temp.replace(self.path)
        return True


def bootstrap_js(settings: dict[str, str], bridge_url: str | None, default_bridge_url: str) -> str:
    """寫回設定並讓頁面改連實際的 bridge；有變更就重新載入（UI 只在載入時讀設定）。

    回傳 'reload' 或 'ready'。第二次執行時值已一致，不會無限重新載入。
    """
    return (
        "(function(){var s=%s,u=%s,d=%s,c=%s,changed=false,k;"
        "for(k in s){if(localStorage.getItem(k)!==s[k]){localStorage.setItem(k,s[k]);changed=true}}"
        "if(u){var v=null;try{v=JSON.parse(localStorage.getItem(c))}catch(e){}"
        "if(((v&&v.url)||d)!==u){v=v&&typeof v==='object'?v:{enabled:false};v.url=u;"
        "localStorage.setItem(c,JSON.stringify(v));changed=true}}"
        "if(changed){setTimeout(function(){location.reload()},0);return 'reload'}"
        "return 'ready'})()"
    ) % (json.dumps(sanitize(settings)), json.dumps(bridge_url), json.dumps(default_bridge_url), json.dumps(CONTROLLER_KEY))


def snapshot_js(expected_origin: str) -> str:
    """回傳允許清單內設定的 JSON；不在遊戲頁面時回傳 null，呼叫端不會寫入。"""
    return (
        "(function(){if(location.origin!==%s)return null;var o={},a=%s,i,v;"
        "for(i=0;i<a.length;i++){v=localStorage.getItem(a[i]);if(v!==null)o[a[i]]=v}"
        "return JSON.stringify(o)})()"
    ) % (json.dumps(expected_origin), json.dumps(list(PRESERVED_KEYS)))
