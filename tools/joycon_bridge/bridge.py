"""本機 Joy-Con bridge。

向「Finally the Controller Works」的 UDP 24800 送 `hello`，收 `S2B1` 封包，
解出右搖桿 x/y 與按鍵，再以 WebSocket 傳給瀏覽器中的 REDLINE（`{x, y, buttons:[b0,b1]}`）。
只綁 127.0.0.1；WebSocket 會檢查 Host（防 DNS rebinding）與 Origin。
"""

from __future__ import annotations

import asyncio
import json
import math
import socket
import struct
import threading
import time
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlsplit

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

BIND_HOST = "127.0.0.1"  # 固定值，刻意不提供設定
DEFAULT_PORT = 8000
DEFAULT_UDP_PORT = 24800
SEND_HZ = 30
HELLO_INTERVAL_S = 1.0
STALE_AFTER_S = 1.0
LOOPBACK_NAMES = {"127.0.0.1", "localhost", "[::1]", "::1"}


@dataclass(frozen=True)
class PacketLayout:
    """S2B1 封包欄位位置。

    注意：offset 是依需求描述假設的預設值，尚未用實機封包驗證；
    用 `--dump-packets` 觀察實際封包，必要時以 CLI 覆寫。
    """

    magic: bytes = b"S2B1"
    buttons_offset: int = 4  # b0, b1 連續兩個 byte
    stick_offset: int = 8  # little-endian float32 x, y
    min_length: int = 16


@dataclass(frozen=True)
class Frame:
    x: float
    y: float
    b0: int
    b1: int


def parse_packet(data: bytes, layout: PacketLayout = PacketLayout()) -> Frame | None:
    """解析並驗證封包；任何不合法（magic、長度、NaN/Inf、超出範圍）一律回傳 None。"""
    if not isinstance(data, (bytes, bytearray)):
        return None
    needed = max(layout.min_length, layout.buttons_offset + 2, layout.stick_offset + 8)
    if len(data) < needed or bytes(data[: len(layout.magic)]) != layout.magic:
        return None
    b0 = data[layout.buttons_offset]
    b1 = data[layout.buttons_offset + 1]
    x, y = struct.unpack_from("<2f", data, layout.stick_offset)
    if not (math.isfinite(x) and math.isfinite(y)):
        return None
    if abs(x) > 1.01 or abs(y) > 1.01:
        return None
    return Frame(x=max(-1.0, min(1.0, x)), y=max(-1.0, min(1.0, y)), b0=b0, b1=b1)


class ControllerState:
    """UDP 執行緒寫、WebSocket 讀；所有存取都在同一把 lock 內。"""

    def __init__(self, clock=time.monotonic) -> None:
        self._lock = threading.Lock()
        self._clock = clock
        self._frame: Frame | None = None
        self._updated_at: float | None = None
        self.packets = 0
        self.rejected = 0

    def update(self, frame: Frame) -> None:
        with self._lock:
            self._frame = frame
            self._updated_at = self._clock()
            self.packets += 1

    def reject(self) -> None:
        with self._lock:
            self.rejected += 1

    def fresh_frame(self, stale_after: float = STALE_AFTER_S) -> Frame | None:
        """資料過期（UDP 來源停止）時回傳 None，讓瀏覽器端依 frame 中斷判定 stale。"""
        with self._lock:
            if self._frame is None or self._updated_at is None:
                return None
            if self._clock() - self._updated_at > stale_after:
                return None
            return self._frame

    def stats(self) -> dict:
        with self._lock:
            age = None if self._updated_at is None else round(self._clock() - self._updated_at, 3)
            return {"packets": self.packets, "rejected": self.rejected, "age_s": age}


def frame_payload(frame: Frame) -> dict:
    return {"x": frame.x, "y": frame.y, "buttons": [frame.b0, frame.b1]}


def host_allowed(host_header: str | None) -> bool:
    """Host 必須是 loopback 名稱（可帶 port）。"""
    if not host_header:
        return False
    host = host_header.strip().lower()
    if host.startswith("["):
        name = host.split("]", 1)[0] + "]"
    else:
        name = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    return name in LOOPBACK_NAMES


def origin_allowed(origin: str | None, allowed: Iterable[str] = ()) -> bool:
    """沒有 Origin（非瀏覽器客戶端）放行；瀏覽器需為 loopback 或明確列入 allowed。"""
    if origin is None:
        return True
    parts = urlsplit(origin)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    normalized = f"{parts.scheme}://{parts.netloc}".lower()
    if normalized in {a.rstrip("/").lower() for a in allowed}:
        return True
    return parts.hostname.lower() in {"127.0.0.1", "localhost", "::1"}


class UdpReceiver(threading.Thread):
    def __init__(self, state: ControllerState, udp_port: int, layout: PacketLayout, dump: bool = False,
                 udp_host: str = "127.0.0.1") -> None:
        super().__init__(daemon=True, name="joycon-udp")
        self._state = state
        self._target = (udp_host, udp_port)
        self._layout = layout
        self._dump = dump
        self._halt = threading.Event()

    def stop(self) -> None:
        self._halt.set()

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.25)
        last_hello = 0.0
        try:
            while not self._halt.is_set():
                now = time.monotonic()
                if now - last_hello >= HELLO_INTERVAL_S:
                    try:
                        sock.sendto(b"hello", self._target)
                    except OSError:
                        pass
                    last_hello = now
                try:
                    data, _ = sock.recvfrom(2048)
                except (socket.timeout, OSError):
                    continue
                if self._dump:
                    print(f"[udp] {len(data)}B {data.hex()}", flush=True)
                frame = parse_packet(data, self._layout)
                if frame is None:
                    self._state.reject()
                else:
                    self._state.update(frame)
        finally:
            sock.close()


def create_app(state: ControllerState, allowed_origins: Iterable[str] = ()) -> FastAPI:
    allowed = list(allowed_origins)
    app = FastAPI(title="REDLINE Joy-Con bridge")

    @app.get("/health")
    async def health():
        return JSONResponse({"ok": True, **state.stats()})

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        if not host_allowed(websocket.headers.get("host")) or not origin_allowed(websocket.headers.get("origin"), allowed):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        try:
            while True:
                frame = state.fresh_frame()
                if frame is not None:
                    await websocket.send_text(json.dumps(frame_payload(frame)))
                await asyncio.sleep(1.0 / SEND_HZ)
        except (WebSocketDisconnect, RuntimeError):
            return

    return app
