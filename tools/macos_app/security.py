"""只用於 packaged App 的 Host／Origin 防護（純 ASGI，不影響 Docker 或 `uv run`）。

遊戲 API 沒有登入機制，瀏覽器裡的任意網站都能嘗試連 127.0.0.1：

- DNS rebinding：惡意網域解析到 127.0.0.1 → Host 不在允許清單 → 拒絕。
- 跨站請求／WebSocket：瀏覽器一定會帶 Origin，且網頁無法偽造 → 不在允許清單 → 拒絕。

沒有 Origin 的本機非瀏覽器 client 照常放行；App 自己的 WebView 帶的是同源 Origin。
明確開放區網（loopback_only=False）時，Host 可以是任何 IP 位址字面值，但不接受網域名稱：
DNS rebinding 的頁面 Host 與 Origin 都是攻擊者的網域，兩者「同源」，只比同源擋不住；而網頁無法讓
瀏覽器在 Host 送出它沒有載入的 IP 字面值。

記錄只寫拒絕原因，不寫路徑或 header 原文：路徑含房間與玩家 id，header 內容由對方控制。
"""

from __future__ import annotations

import ipaddress
import logging

log = logging.getLogger("uvicorn.error")

LOOPBACK_NAMES = ("127.0.0.1", "localhost")
FORBIDDEN_BODY = b"Forbidden"


def allowed_hosts(port: int) -> frozenset[str]:
    return frozenset(f"{name}:{port}" for name in LOOPBACK_NAMES)


def is_lan_host_allowed(host: str, port: int) -> bool:
    """連接埠必須完全相符；主機必須是 loopback 名稱、IPv4 字面值或加方括號的 IPv6 字面值。"""
    suffix = f":{port}"
    if not host.endswith(suffix):
        return False
    name = host[: -len(suffix)]
    if name in LOOPBACK_NAMES:
        return True
    bracketed = name.startswith("[") and name.endswith("]")
    literal = name[1:-1] if bracketed else name
    if "%" in literal:  # IPv6 zone id 不是合法的 URL 主機
        return False
    try:
        address = ipaddress.ip_address(literal)
    except ValueError:
        return False
    if address.version != (6 if bracketed else 4):
        return False
    return not (address.is_unspecified or address.is_multicast)


def rejection_reason(hosts: list[str], origins: list[str], port: int, loopback_only: bool = True) -> str | None:
    """回傳拒絕原因；可放行時回傳 None。比對一律是完整字串，不做解析，避免解析差異被利用。"""
    if len(hosts) != 1 or len(origins) > 1:
        return "missing or duplicate Host/Origin header"
    host = hosts[0].strip().lower()
    if loopback_only:
        if host not in allowed_hosts(port):
            return "Host not allowed"
    elif not is_lan_host_allowed(host, port):
        return "Host not allowed"
    if origins and origins[0].strip().lower() != f"http://{host}":
        return "Origin not allowed"
    return None


class HostOriginGuard:
    def __init__(self, app, port: int, loopback_only: bool = True) -> None:
        self.app = app
        self.port = port
        self.loopback_only = loopback_only

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        hosts: list[str] = []
        origins: list[str] = []
        for name, value in scope.get("headers", []):
            if name == b"host":
                hosts.append(value.decode("latin-1"))
            elif name == b"origin":
                origins.append(value.decode("latin-1"))
        reason = rejection_reason(hosts, origins, self.port, self.loopback_only)
        if reason is None:
            await self.app(scope, receive, send)
            return
        log.warning("rejected %s request: %s", scope["type"], reason)
        if scope["type"] == "websocket":
            await receive()  # websocket.connect；未 accept 就 close，client 會收到 HTTP 403。
            await send({"type": "websocket.close", "code": 1008})
            return
        headers = [(b"content-type", b"text/plain"), (b"content-length", str(len(FORBIDDEN_BODY)).encode())]
        await send({"type": "http.response.start", "status": 403, "headers": headers})
        await send({"type": "http.response.body", "body": FORBIDDEN_BODY})
