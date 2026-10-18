"""本機 Joy-Con bridge（多支獨立手把）。

向「Finally the Controller Works」（FTCW）的每個 UDP 埠（預設 24800–24803，一個埠一支手把）送 `hello`，
收 `S2N1`（裝置名稱）與 `S2B1`（輸入）封包。每支實體手把有自己的身份（左右＋FTCW 埠＋名稱指紋）、
原始／正規化狀態、最後收到時間、stale 狀態與擁有者（一個瀏覽器 WebSocket 連線＝一位玩家）。
左 Joy-Con 的實體按鍵在這裡正規化成既有右 Joy-Con 的邏輯 layout；瀏覽器只收 `{x, y, buttons:[b0,b1]}` 的共用邏輯位元。
只綁 127.0.0.1；WebSocket 與 /health 會檢查 Host（防 DNS rebinding），WebSocket 另檢查 Origin。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import secrets
import socket
import struct
import threading
import time
import unicodedata
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

BIND_HOST = "127.0.0.1"  # 固定值，刻意不提供設定
DEFAULT_PORT = 8000
DEFAULT_UDP_PORT = 24800
DEFAULT_UDP_PORT_COUNT = 4  # 24800–24803：FTCW 一個埠一支手把
MAX_UDP_PORT_COUNT = 8
SEND_HZ = 30
HELLO_INTERVAL_S = 1.0
STALE_AFTER_S = 1.0
# 主埠從未收到 S2N1 名稱時，等這麼久才採用舊版「右 Joy-Con」預設身份（名稱通常緊接著 hello 到達）。
NAME_GRACE_S = 1.5
# 連上後這麼久都沒送 v2 hello 的 client＝舊版頁面：只拿「唯一一支右 Joy-Con」並收舊版 payload。
LEGACY_CLIENT_GRACE_S = 0.3
ROSTER_INTERVAL_S = 1.0
STICK_DEADZONE = 0.15
NAME_MAX_BYTES = 64
CLIENT_MESSAGE_MAX_BYTES = 512
PROTOCOL_VERSION = 2
LEGACY_LOST_CLOSE_CODE = 4001  # 舊版 client 綁定的手把被同埠另一支裝置取代：關閉讓舊版頁面重連
LOOPBACK_NAMES = {"127.0.0.1", "localhost", "[::1]", "::1"}

# 共用邏輯 layout＝既有右 Joy-Con 的 [b0, b1]（瀏覽器 static/controller_core.js 的 BUTTON_BITS）。
LOGICAL_BITS: dict[str, tuple[int, int]] = {
    "A": (0, 0x08), "B": (0, 0x04), "X": (0, 0x02), "Y": (0, 0x01),
    "SL": (0, 0x20), "SR": (0, 0x10), "R": (0, 0x40), "ZR": (0, 0x80),
    "PLUS": (1, 0x02), "STICK": (1, 0x04), "HOME": (1, 0x10), "CAPTURE": (1, 0x40),
}


@dataclass(frozen=True)
class PhysicalButton:
    """實體鍵：u32 buttons 內第 `byte` 個 byte（封包 offset＝buttons_offset＋byte）的 `mask` → 共用邏輯鍵。"""

    name: str
    byte: int
    mask: int
    logical: str


# 既有右 Joy-Con（邏輯基準）：offset 8／9，原樣對應。
RIGHT_BUTTONS = (
    PhysicalButton("Y", 0, 0x01, "Y"), PhysicalButton("X", 0, 0x02, "X"),
    PhysicalButton("B", 0, 0x04, "B"), PhysicalButton("A", 0, 0x08, "A"),
    PhysicalButton("SR", 0, 0x10, "SR"), PhysicalButton("SL", 0, 0x20, "SL"),
    PhysicalButton("R", 0, 0x40, "R"), PhysicalButton("ZR", 0, 0x80, "ZR"),
    PhysicalButton("PLUS", 1, 0x02, "PLUS"), PhysicalButton("STICK", 1, 0x04, "STICK"),
    PhysicalButton("HOME", 1, 0x10, "HOME"), PhysicalButton("CAPTURE", 1, 0x40, "CAPTURE"),
    # 相容：上游 `capture`（u32 0x2000）在既有 bridge 一直當 CAPTURE（右 Joy-Con 2 沒有這顆鍵；舊版預設身份未確認裝置）。
    PhysicalButton("CAPTURE_COMPAT", 1, 0x20, "CAPTURE"),
)
# 左 Joy-Con：offset 9／10。方向鍵＝右手 X／A／B／Y 的位置；SR／SL 交叉（左 SR＝右 SL、左 SL＝右 SR）；沒有 HOME。
LEFT_BUTTONS = (
    PhysicalButton("UP", 2, 0x02, "X"), PhysicalButton("RIGHT", 2, 0x04, "A"),
    PhysicalButton("DOWN", 2, 0x01, "B"), PhysicalButton("LEFT", 2, 0x08, "Y"),
    PhysicalButton("STICK", 1, 0x08, "STICK"),
    PhysicalButton("L", 2, 0x40, "R"), PhysicalButton("ZL", 2, 0x80, "ZR"),
    PhysicalButton("MINUS", 1, 0x01, "PLUS"),
    PhysicalButton("CAPTURE", 1, 0x20, "CAPTURE"),
    PhysicalButton("SR", 2, 0x10, "SL"), PhysicalButton("SL", 2, 0x20, "SR"),
)
SIDE_BUTTONS = {"left": LEFT_BUTTONS, "right": RIGHT_BUTTONS}


@dataclass(frozen=True)
class PacketLayout:
    """S2B1 封包欄位位置（Finally the Controller Works v0.2.0 的 44-byte wire format）：
    magic | u32 seq | u32 buttons | f32 lx,ly,rx,ry | sensors。右手用 rx/ry，左手用 lx/ly。
    """

    magic: bytes = b"S2B1"
    buttons_offset: int = 8  # u32 buttons（little-endian）起點
    stick_offset: int = 20  # 右搖桿 rx, ry
    left_stick_offset: int = 12  # 左搖桿 lx, ly
    min_length: int = 44

    def stick_for(self, side: str) -> int:
        return self.left_stick_offset if side == "left" else self.stick_offset


@dataclass(frozen=True)
class Frame:
    """共用邏輯 frame：畫面座標（y 向下為正）＋右 Joy-Con layout 的 b0／b1。"""

    x: float
    y: float
    b0: int
    b1: int


@dataclass(frozen=True)
class ClaimResult:
    ok: bool
    controller: str | None
    reason: str | None


@dataclass(frozen=True)
class OwnedFrame:
    controller: str
    side: str
    epoch: int
    frame: Frame


def _axis(value: float) -> float:
    """每軸 deadzone（低於 STICK_DEADZONE 即 0，不重新縮放）後 clamp 到 ±1。"""
    if abs(value) < STICK_DEADZONE:
        return 0.0
    return max(-1.0, min(1.0, value))


def normalize_buttons(side: str, button_bytes: bytes) -> tuple[int, int]:
    """實體按鍵 byte → 共用邏輯 (b0, b1)；未知位元一律丟棄。"""
    out = [0, 0]
    for button in SIDE_BUTTONS[side]:
        if button_bytes[button.byte] & button.mask:
            index, bit = LOGICAL_BITS[button.logical]
            out[index] |= bit
    return out[0], out[1]


def parse_packet(data: bytes, layout: PacketLayout = PacketLayout(), side: str = "right") -> Frame | None:
    """解析 S2B1 並正規化成共用邏輯 Frame；不合法（magic、長度、該側搖桿 NaN/Inf、超出範圍、未知 side）一律 None。"""
    if side not in SIDE_BUTTONS or not isinstance(data, (bytes, bytearray)):
        return None
    span = max(button.byte for button in SIDE_BUTTONS[side]) + 1
    stick = layout.stick_for(side)
    needed = max(layout.min_length, layout.buttons_offset + span, stick + 8)
    if len(data) < needed or bytes(data[: len(layout.magic)]) != layout.magic:
        return None
    x, raw_y = struct.unpack_from("<2f", data, stick)
    if not (math.isfinite(x) and math.isfinite(raw_y)):
        return None
    if abs(x) > 1.01 or abs(raw_y) > 1.01:
        return None
    b0, b1 = normalize_buttons(side, bytes(data[layout.buttons_offset: layout.buttons_offset + span]))
    # FTCW 用控制器座標（向上為正），REDLINE 用畫面座標（向下為正）。
    return Frame(x=_axis(x), y=_axis(-raw_y), b0=b0, b1=b1)


def parse_name_packet(data: bytes) -> str | None:
    """S2N1 裝置名稱：去掉 C 字串結尾 NUL 與前後空白；空白、過長、非 UTF-8 或含控制／格式字元一律 None。"""
    if not isinstance(data, (bytes, bytearray)) or bytes(data[:4]) != b"S2N1":
        return None
    raw = bytes(data[4:]).rstrip(b"\0")
    if not raw or len(raw) > NAME_MAX_BYTES:
        return None
    try:
        name = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None
    if not name or any(unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Co", "Cn") for ch in name):
        return None
    return name


def detect_side(name: str | None) -> str | None:
    """參考 demo 的名稱規則：`(L)`／`LEFT` → left，`(R)`／`RIGHT` → right；兩者皆有或皆無 → None（fail closed）。"""
    if not isinstance(name, str):
        return None
    upper = name.upper()
    left = "(L)" in upper or "LEFT" in upper
    right = "(R)" in upper or "RIGHT" in upper
    if left == right:
        return None
    return "left" if left else "right"


CONTROLLER_ID_RE = re.compile(r"(L|R)([1-9][0-9]{0,4})-([0-9a-f]{8}|legacy)")
LEGACY_FINGERPRINT = "legacy"


def controller_id(side: str, port: int, name: str | None) -> str:
    """穩定身份：左右＋FTCW UDP 埠＋S2N1 名稱指紋。主埠沒有名稱的舊版預設身份，指紋固定為 `legacy`。"""
    fingerprint = LEGACY_FINGERPRINT if name is None else hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
    return f"{'L' if side == 'left' else 'R'}{port}-{fingerprint}"


def is_controller_id(value) -> bool:
    if not isinstance(value, str) or len(value) > 24:
        return False
    match = CONTROLLER_ID_RE.fullmatch(value)
    return bool(match) and int(match.group(2)) <= 65535


@dataclass
class _Controller:
    id: str
    side: str
    port: int
    name: str | None
    side_source: str  # "name"｜"legacy-default"
    owner: str | None = None
    frame: Frame | None = None  # 最新正規化 frame；stale 時清空（不殘留按鍵／搖桿）
    last_seen: float | None = None
    epoch: int = 0  # 每次（重新）開始收到輸入就 +1：瀏覽器據此重新建立 baseline
    packets: int = 0


@dataclass
class _Endpoint:
    port: int
    name: str | None = None
    controller_id: str | None = None
    unnamed_since: float | None = None


@dataclass
class _Session:
    id: str
    mode: str  # pending｜legacy｜v2
    owned: str | None = None
    lost: dict | None = None  # 被動失去手把（replaced／unidentified）


class ControllerRegistry:
    """所有手把、FTCW 端點與瀏覽器連線（玩家）。UDP 執行緒寫、WebSocket 讀；所有存取都在同一把 lock 內。

    擁有規則：每支手把最多一位擁有者、每位玩家最多一支；只有明確 claim（或舊版相容的「唯一一支右 Joy-Con」預設）
    才擁有。手把 stale 時保留擁有者，同一身份恢復時回到同一位玩家；換了埠或同埠換了裝置就是新的、未被擁有的身份。
    玩家連線結束即釋放。
    """

    def __init__(self, ports: Iterable[int] = (DEFAULT_UDP_PORT,), primary_port: int | None = DEFAULT_UDP_PORT,
                 layout: PacketLayout = PacketLayout(), clock=time.monotonic, udp_host: str = "127.0.0.1") -> None:
        self._lock = threading.Lock()
        self._clock = clock
        self._layout = layout
        self._udp_host = udp_host
        self._primary = primary_port
        self._endpoints = {port: _Endpoint(port) for port in ports}
        self._controllers: dict[str, _Controller] = {}
        self._sessions: dict[str, _Session] = {}
        self.packets = 0
        self.rejected = 0
        self.ignored = 0

    # ------------------------------------------------------------ UDP
    def observe(self, port: int, data: bytes) -> None:
        with self._lock:
            endpoint = self._endpoints.get(port)
            if endpoint is None:
                self.rejected += 1
                return
            name = parse_name_packet(data)
            if name is not None:
                self._observe_name(endpoint, name)
            elif isinstance(data, (bytes, bytearray)) and bytes(data[:4]) == self._layout.magic:
                self._observe_input(endpoint, data, self._clock())
            else:
                self.rejected += 1

    def _observe_name(self, endpoint: _Endpoint, name: str) -> None:
        endpoint.name = name
        endpoint.unnamed_since = None
        side = detect_side(name)
        new_id = controller_id(side, endpoint.port, name) if side else None
        if new_id is not None and endpoint.controller_id == new_id:
            return
        if endpoint.controller_id is not None:
            self._retire(endpoint.controller_id, "replaced" if side else "unidentified")
            endpoint.controller_id = None
        if new_id is not None:
            self._controllers[new_id] = _Controller(new_id, side, endpoint.port, name, "name")
            endpoint.controller_id = new_id

    def _observe_input(self, endpoint: _Endpoint, data: bytes, now: float) -> None:
        controller = self._controllers.get(endpoint.controller_id) if endpoint.controller_id else None
        if controller is None:
            # 名稱無法判定左右，或非主埠還沒有名稱：fail closed（不建立身份、不轉送）。
            if endpoint.name is not None or endpoint.port != self._primary:
                self.ignored += 1
                return
            if parse_packet(data, self._layout, "right") is None:
                self.rejected += 1
                return
            if endpoint.unnamed_since is None:
                endpoint.unnamed_since = now
            if now - endpoint.unnamed_since < NAME_GRACE_S:
                self.ignored += 1
                return
            cid = controller_id("right", endpoint.port, None)
            controller = self._controllers[cid] = _Controller(cid, "right", endpoint.port, None, "legacy-default")
            endpoint.controller_id = cid
        frame = parse_packet(data, self._layout, controller.side)
        if frame is None:
            self.rejected += 1
            return
        if not self._active(controller, now):
            controller.epoch += 1
        controller.frame = frame
        controller.last_seen = now
        controller.packets += 1
        self.packets += 1

    def _retire(self, cid: str, reason: str) -> None:
        controller = self._controllers.pop(cid, None)
        if controller and controller.owner and controller.owner in self._sessions:
            session = self._sessions[controller.owner]
            session.owned = None
            session.lost = {"controller": cid, "reason": reason}

    def _active(self, controller: _Controller, now: float) -> bool:
        return controller.last_seen is not None and now - controller.last_seen <= STALE_AFTER_S

    def _refresh(self, now: float) -> None:
        for controller in self._controllers.values():
            if controller.frame is not None and not self._active(controller, now):
                controller.frame = None

    # ------------------------------------------------------------ sessions / claims
    def open_session(self, mode: str = "pending") -> str:
        with self._lock:
            sid = secrets.token_hex(8)
            self._sessions[sid] = _Session(sid, mode)
            return sid

    def session_mode(self, sid: str) -> str | None:
        with self._lock:
            session = self._sessions.get(sid)
            return session.mode if session else None

    def set_session_mode(self, sid: str, mode: str) -> None:
        with self._lock:
            session = self._sessions.get(sid)
            if session is None:
                return
            if mode == "v2" and session.mode != "v2":
                self._release(session)  # v2 頁面只擁有自己明確 claim 的手把
            session.mode = mode

    def close_session(self, sid: str) -> None:
        with self._lock:
            session = self._sessions.pop(sid, None)
            if session:
                self._release(session)

    def _release(self, session: _Session) -> None:
        controller = self._controllers.get(session.owned) if session.owned else None
        if controller and controller.owner == session.id:
            controller.owner = None
        session.owned = None

    def claim(self, sid: str, cid) -> ClaimResult:
        with self._lock:
            now = self._clock()
            self._refresh(now)
            session = self._sessions.get(sid)
            if session is None:
                return ClaimResult(False, None, "no-session")
            if not is_controller_id(cid):
                return ClaimResult(False, session.owned, "invalid-controller")
            controller = self._controllers.get(cid)
            if controller is None:
                return ClaimResult(False, session.owned, "unknown-controller")
            if controller.owner == sid:
                return ClaimResult(True, cid, None)
            if controller.owner is not None:
                return ClaimResult(False, session.owned, "claimed")
            if not self._active(controller, now):
                return ClaimResult(False, session.owned, "not-active")
            self._release(session)  # 切換：先放掉原本的
            controller.owner = sid
            session.owned = cid
            session.lost = None
            return ClaimResult(True, cid, None)

    def claim_default(self, sid: str) -> ClaimResult:
        """舊版相容預設：恰好只有一支手把、它是右 Joy-Con、有訊號且沒人用 → 擁有它。其他情況一律要明確選擇。"""
        with self._lock:
            now = self._clock()
            session = self._sessions.get(sid)
            if session is None:
                return ClaimResult(False, None, "no-session")
            if session.owned:
                return ClaimResult(False, session.owned, "already-owned")
            controllers = list(self._controllers.values())
            if len(controllers) != 1:
                return ClaimResult(False, None, "no-default")
            only = controllers[0]
            if only.side != "right" or only.owner is not None or not self._active(only, now):
                return ClaimResult(False, None, "no-default")
            only.owner = sid
            session.owned = only.id
            session.lost = None
            return ClaimResult(True, only.id, None)

    def release(self, sid: str) -> ClaimResult:
        with self._lock:
            session = self._sessions.get(sid)
            if session is None:
                return ClaimResult(False, None, "no-session")
            self._release(session)
            session.lost = None
            return ClaimResult(True, None, None)

    def session_owns(self, sid: str) -> bool:
        with self._lock:
            session = self._sessions.get(sid)
            return bool(session and session.owned)

    def session_lost(self, sid: str) -> bool:
        with self._lock:
            session = self._sessions.get(sid)
            return bool(session and session.lost)

    def session_frame(self, sid: str) -> OwnedFrame | None:
        """只回傳這位玩家擁有、且目前有訊號的那一支手把的 frame。"""
        with self._lock:
            now = self._clock()
            self._refresh(now)
            session = self._sessions.get(sid)
            controller = self._controllers.get(session.owned) if session and session.owned else None
            if controller is None or controller.owner != sid or controller.frame is None:
                return None
            return OwnedFrame(controller.id, controller.side, controller.epoch, controller.frame)

    def roster(self, sid: str) -> dict:
        """v2 roster：所有手把（其他玩家只標示為 other）與這位玩家擁有的那一支。"""
        with self._lock:
            now = self._clock()
            self._refresh(now)
            session = self._sessions.get(sid)
            items = []
            for controller in sorted(self._controllers.values(), key=lambda c: (c.port, c.id)):
                owner = None if controller.owner is None else ("you" if session and controller.owner == sid else "other")
                items.append({
                    "id": controller.id, "side": controller.side, "name": controller.name,
                    "endpoint": f"{self._udp_host}:{controller.port}", "status": "active" if self._active(controller, now) else "stale",
                    "owner": owner, "sideSource": controller.side_source,
                })
            payload = {"type": "roster", "v": PROTOCOL_VERSION, "owned": session.owned if session else None, "controllers": items}
            if session and session.lost:
                payload["lost"] = dict(session.lost)
            return payload

    # ------------------------------------------------------------ diagnostics
    def snapshot(self) -> dict:
        with self._lock:
            now = self._clock()
            self._refresh(now)
            return {
                cid: {
                    "id": c.id, "side": c.side, "port": c.port, "name": c.name, "side_source": c.side_source,
                    "status": "active" if self._active(c, now) else "stale", "owner": c.owner, "epoch": c.epoch,
                    "frame": c.frame, "packets": c.packets,
                }
                for cid, c in self._controllers.items()
            }

    def stats(self) -> dict:
        with self._lock:
            now = self._clock()
            ages = [now - c.last_seen for c in self._controllers.values() if c.last_seen is not None]
            return {
                "packets": self.packets, "rejected": self.rejected, "ignored": self.ignored,
                "age_s": round(min(ages), 3) if ages else None,
                "controllers": [
                    {"id": c.id, "side": c.side, "status": "active" if self._active(c, now) else "stale", "owned": c.owner is not None}
                    for c in sorted(self._controllers.values(), key=lambda c: (c.port, c.id))
                ],
            }


def frame_payload(frame: Frame) -> dict:
    """舊版 payload（也是 v2 frame 的欄位）：`{x, y, buttons:[b0, b1]}`。"""
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
    """一個 FTCW UDP 埠（一支手把）：每次接收前送 hello，收到的封包交給 registry。socket 只綁 loopback。

    FTCW 的多手把介面以 request/response 方式逐筆回傳 S2N1／S2B1。若只定時送 hello，
    每個埠可能只重複收到裝置名稱，永遠收不到下一筆輸入。
    """

    def __init__(self, registry: ControllerRegistry, udp_port: int, dump: bool = False, udp_host: str = "127.0.0.1") -> None:
        super().__init__(daemon=True, name=f"joycon-udp-{udp_port}")
        self._registry = registry
        self._port = udp_port
        self._target = (udp_host, udp_port)
        self._dump = dump
        self._halt = threading.Event()
        self.local_address: tuple[str, int] | None = None

    def stop(self) -> None:
        self._halt.set()

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((BIND_HOST, 0))
        self.local_address = sock.getsockname()
        sock.settimeout(0.25)
        try:
            while not self._halt.is_set():
                try:
                    sock.sendto(b"hello", self._target)
                except OSError:
                    pass
                try:
                    data, _ = sock.recvfrom(2048)
                except (socket.timeout, OSError):
                    continue
                if self._dump:
                    print(f"[udp {self._port}] {len(data)}B {data.hex()}", flush=True)
                self._registry.observe(self._port, data)
        finally:
            sock.close()


def parse_client_message(text) -> dict | None:
    """v2 client 訊息：≤512 bytes 的 JSON object、v＝2、type ∈ hello／claim／claim-default／release（claim 需帶 controller 鍵）。"""
    if not isinstance(text, str) or len(text.encode("utf-8")) > CLIENT_MESSAGE_MAX_BYTES:
        return None
    try:
        message = json.loads(text)
    except ValueError:
        return None
    if not isinstance(message, dict) or message.get("v") != PROTOCOL_VERSION:
        return None
    if message.get("type") not in ("hello", "claim", "claim-default", "release"):
        return None
    if message["type"] == "claim" and "controller" not in message:
        return None
    return message


def _claim_reply(request: str, result: ClaimResult) -> dict:
    return {"type": "claim-result", "v": PROTOCOL_VERSION, "request": request, "ok": result.ok,
            "controller": result.controller, "reason": result.reason}


def handle_client_message(registry: ControllerRegistry, sid: str, text) -> list[dict]:
    """處理一則 client 訊息，回傳要送回的訊息。hello 讓連線升級為 v2；其他訊息只在 v2 才處理（舊版連線一律忽略）。"""
    message = parse_client_message(text)
    mode = registry.session_mode(sid)
    if message is None:
        return [{"type": "error", "v": PROTOCOL_VERSION, "reason": "bad-message"}] if mode == "v2" else []
    if message["type"] == "hello":
        registry.set_session_mode(sid, "v2")
        return []
    if mode != "v2":
        return []
    if message["type"] == "claim":
        return [_claim_reply("claim", registry.claim(sid, message["controller"]))]
    if message["type"] == "claim-default":
        return [_claim_reply("claim-default", registry.claim_default(sid))]
    return [_claim_reply("release", registry.release(sid))]


def create_app(registry: ControllerRegistry, allowed_origins: Iterable[str] = ()) -> FastAPI:
    allowed = list(allowed_origins)
    app = FastAPI(title="REDLINE Joy-Con bridge")

    @app.get("/health")
    async def health(request: Request):
        if not host_allowed(request.headers.get("host")):
            return JSONResponse({"ok": False}, status_code=403)
        return JSONResponse({"ok": True, **registry.stats()})

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        if not host_allowed(websocket.headers.get("host")) or not origin_allowed(websocket.headers.get("origin"), allowed):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        sid = registry.open_session("pending")
        outbox: list[dict] = []
        done = asyncio.Event()

        async def receive_loop():
            try:
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        return
                    outbox.extend(handle_client_message(registry, sid, message.get("text")))
            except (WebSocketDisconnect, RuntimeError):
                return
            finally:
                done.set()

        receiver = asyncio.create_task(receive_loop())
        loop = asyncio.get_running_loop()
        opened = loop.time()
        roster_sig = None
        roster_at = 0.0
        try:
            while not done.is_set():
                mode = registry.session_mode(sid)
                if mode == "pending" and loop.time() - opened >= LEGACY_CLIENT_GRACE_S:
                    registry.set_session_mode(sid, "legacy")
                    mode = "legacy"
                while outbox:  # 單一 writer：回覆、roster、frame 都在這個迴圈送出
                    await websocket.send_text(json.dumps(outbox.pop(0)))
                if mode == "v2":
                    roster = registry.roster(sid)
                    sig = json.dumps(roster, sort_keys=True)
                    if sig != roster_sig or loop.time() - roster_at >= ROSTER_INTERVAL_S:
                        await websocket.send_text(sig)
                        roster_sig, roster_at = sig, loop.time()
                    owned = registry.session_frame(sid)
                    if owned is not None:
                        await websocket.send_text(json.dumps({
                            "type": "frame", "v": PROTOCOL_VERSION, "controller": owned.controller, "side": owned.side,
                            "epoch": owned.epoch, **frame_payload(owned.frame),
                        }))
                elif mode == "legacy":
                    if registry.session_lost(sid):
                        await websocket.close(code=LEGACY_LOST_CLOSE_CODE)
                        return
                    if not registry.session_owns(sid):
                        registry.claim_default(sid)
                    owned = registry.session_frame(sid)
                    if owned is not None:
                        await websocket.send_text(json.dumps(frame_payload(owned.frame)))
                await asyncio.sleep(1.0 / SEND_HZ)
        except (WebSocketDisconnect, RuntimeError):
            return
        finally:
            receiver.cancel()
            registry.close_session(sid)

    return app
