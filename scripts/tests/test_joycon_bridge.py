"""Joy-Con bridge：封包解析、NaN/範圍驗證、stale、Host/Origin、只綁 loopback（既有右 Joy-Con 與舊版 payload 回歸）。"""

import socket
import struct
import time

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tools.joycon_bridge import __main__ as bridge_main
from tools.joycon_bridge.bridge import (
    BIND_HOST,
    ControllerRegistry,
    Frame,
    PacketLayout,
    UdpReceiver,
    create_app,
    frame_payload,
    host_allowed,
    origin_allowed,
    parse_packet,
)

RIGHT_NAME = b"Joy-Con 2 (R)"
WS_HEADERS = {"host": "127.0.0.1:8000"}


def packet(x=0.0, y=0.0, b0=0, b1=0, magic=b"S2B1"):
    # FTCW v0.2.0: magic, seq, u32 buttons, lx/ly, rx/ry, sensor tail.
    return (
        magic
        + struct.pack("<I", 1)
        + bytes([b0, b1, 0, 0])
        + struct.pack("<2f", 0.0, 0.0)
        + struct.pack("<2f", x, y)
        + b"\0" * 16
    )


def single_right(data, port=24800, clock=lambda: 100.0):
    """一支已報名的右 Joy-Con（預設固定時鐘：永遠 fresh）。純函式，不開任何網路埠。"""
    reg = ControllerRegistry([port], primary_port=port, clock=clock)
    reg.observe(port, b"S2N1" + RIGHT_NAME)
    reg.observe(port, data)
    return reg


def legacy_payload(reg, headers=WS_HEADERS, allowed=()):
    """舊版頁面（連上後不送任何訊息）收到的第一筆 payload。"""
    client = TestClient(create_app(reg, allowed), base_url="http://127.0.0.1:8000")
    with client.websocket_connect("/ws", headers=headers) as ws:
        return ws.receive_json()


def test_parse_valid_packet_normalizes_ftcw_y_to_screen_coordinates():
    # FTCW reports upward stick motion as positive y. The browser contract uses
    # screen coordinates, where upward is negative and downward is positive.
    assert parse_packet(packet(0.5, -0.25, 0x08, 0x02)) == Frame(0.5, 0.25, 0x08, 0x02)
    assert parse_packet(packet(0.0, 0.75)) == Frame(0.0, -0.75, 0, 0)


@pytest.mark.parametrize("bad", [
    packet(magic=b"XXXX"),
    packet()[:10],
    packet(float("nan"), 0.0),
    packet(0.0, float("inf")),
    packet(1.5, 0.0),
    packet(0.0, -3.0),
    b"",
])
def test_parse_rejects_invalid(bad):
    assert parse_packet(bad) is None


def test_parse_clamps_tiny_overshoot():
    assert parse_packet(packet(1.005, -1.005)).x == 1.0


def test_capture_upstream_uint32_normalizes_to_logical_capture():
    # Upstream switch2mac Switch2Protocol.swift: capture = 0x0000_2000; UDPHub writes the raw UInt32 little-endian.
    # The bridge always treated it as CAPTURE; it now emits the shared logical CAPTURE bit (b1 0x40) instead of the raw
    # b1 0x20 (both old and new browsers decode either as CAPTURE — see controller_core.test.js legacy payload test).
    assert struct.pack("<I", 0x0000_2000) == b"\x00\x20\x00\x00"
    data = (
        b"S2B1"
        + b"\x07\x00\x00\x00"  # u32 seq
        + b"\x00\x20\x00\x00"  # u32 buttons = 0x00002000 (capture only)
        + b"\x00" * 16  # f32 lx, ly, rx, ry = 0
        + b"\x00" * 16  # sensor tail
    )
    assert len(data) == 44
    frame = parse_packet(data)
    assert (frame.b0, frame.b1) == (0x00, 0x40)
    assert frame_payload(frame)["buttons"] == [0x00, 0x40]
    assert legacy_payload(single_right(data))["buttons"] == [0x00, 0x40]


def test_physical_capture_key_c_uint32_reaches_browser_as_b1_0x40():
    # Live bridge subscriber, right Joy-Con 2 only (2026-10-10): the physical Capture press arrived as buttons:[0, 64].
    # Upstream switch2mac Switch2Protocol.swift: c = 0x0000_4000. The right Joy-Con is the logical baseline, so the
    # bit is forwarded unchanged; the browser (static/controller_core.js) decodes b1 0x40 as CAPTURE.
    assert struct.pack("<I", 0x0000_4000) == b"\x00\x40\x00\x00"
    data = b"S2B1" + b"\x08\x00\x00\x00" + b"\x00\x40\x00\x00" + b"\x00" * 32
    assert len(data) == 44
    frame = parse_packet(data)
    assert (frame.b0, frame.b1) == (0x00, 0x40)
    assert legacy_payload(single_right(data))["buttons"] == [0x00, 0x40]


def test_custom_layout_offsets():
    layout = PacketLayout(buttons_offset=6, stick_offset=8, min_length=16)
    data = b"S2B1" + bytes([1, 2, 0x40, 0x04]) + struct.pack("<2f", 0.1, 0.2)
    frame = parse_packet(data, layout)
    assert (frame.b0, frame.b1) == (0x40, 0x04)


def test_state_goes_stale_and_payload_shape():
    now = [100.0]
    reg = ControllerRegistry([24800], primary_port=24800, clock=lambda: now[0])
    session = reg.open_session("legacy")
    assert reg.session_frame(session) is None
    reg.observe(24800, b"S2N1" + RIGHT_NAME)
    reg.observe(24800, packet(0.3, -0.4, 8, 0))
    assert reg.claim_default(session).ok
    assert frame_payload(reg.session_frame(session).frame) == {"x": pytest.approx(0.3), "y": pytest.approx(0.4), "buttons": [8, 0]}
    now[0] += 5
    assert reg.session_frame(session) is None
    assert reg.stats()["packets"] == 1


@pytest.mark.parametrize("host,ok", [
    ("127.0.0.1:8000", True), ("localhost:8000", True), ("localhost", True), ("[::1]:8000", True),
    ("evil.example:8000", False), ("192.168.1.5:8000", False), ("", False), (None, False),
    ("127.0.0.1.evil.com", False),
])
def test_host_allowed(host, ok):
    assert host_allowed(host) is ok


@pytest.mark.parametrize("origin,allowed,ok", [
    (None, (), True),
    ("http://localhost:8100", (), True),
    ("http://127.0.0.1:8100", (), True),
    ("http://192.168.1.5:8100", (), False),
    ("http://192.168.1.5:8100", ("http://192.168.1.5:8100/",), True),
    ("https://evil.example", (), False),
    ("null", (), False),
    ("file://x", (), False),
])
def test_origin_allowed(origin, allowed, ok):
    assert origin_allowed(origin, allowed) is ok


def test_ws_streams_frames_and_enforces_host_origin():
    reg = single_right(packet(0.3, -0.4, 4, 0))
    lan = {**WS_HEADERS, "origin": "http://192.168.1.5:8100"}
    assert legacy_payload(reg, lan, ["http://192.168.1.5:8100"]) == {"x": pytest.approx(0.3), "y": pytest.approx(0.4), "buttons": [4, 0]}
    client = TestClient(create_app(reg, ["http://192.168.1.5:8100"]), base_url="http://127.0.0.1:8000")
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers={**WS_HEADERS, "origin": "http://evil.example"}):
            pass
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers={"host": "evil.example"}):
            pass


def test_health_endpoint():
    client = TestClient(create_app(ControllerRegistry([24800])), base_url="http://127.0.0.1:8000")
    assert client.get("/health", headers=WS_HEADERS).json()["ok"] is True


def test_bind_host_is_loopback_only():
    assert BIND_HOST == "127.0.0.1"
    assert "--host" not in bridge_main.build_parser().format_help()


def test_udp_receiver_sends_hello_and_ingests_packets():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    server.settimeout(3)
    port = server.getsockname()[1]
    reg = ControllerRegistry([port], primary_port=port)
    receiver = UdpReceiver(reg, port)
    receiver.start()
    try:
        started = time.monotonic()
        data, addr = server.recvfrom(64)
        assert data == b"hello"
        server.sendto(b"junk", addr)
        data, addr = server.recvfrom(64)
        assert data == b"hello"
        server.sendto(b"S2N1" + RIGHT_NAME, addr)
        data, addr = server.recvfrom(64)
        assert data == b"hello"
        assert time.monotonic() - started < 0.5
        server.sendto(packet(0.5, 0.0, 0x08), addr)
        session = reg.open_session("legacy")
        for _ in range(60):
            if reg.claim_default(session).ok or reg.session_frame(session):
                break
            time.sleep(0.05)
        assert reg.session_frame(session).frame.b0 == 0x08
        assert reg.stats()["rejected"] == 1
    finally:
        receiver.stop()
        receiver.join(2)
        server.close()


def test_cli_defaults_keep_loopback():
    args = bridge_main.build_parser().parse_args([])
    assert args.bind_host == "127.0.0.1"
    assert args.udp_host == "127.0.0.1"


@pytest.fixture
def captured_main(monkeypatch):
    seen = {"receivers": [], "run": None, "registry": None}

    class FakeReceiver:
        def __init__(self, registry, port, dump=False, udp_host="127.0.0.1"):
            seen["receivers"].append((port, udp_host))
            seen["registry"] = registry

        def start(self): pass
        def stop(self): pass

    def fake_run(app, **kwargs):
        seen["run"] = kwargs
        seen["app"] = app

    monkeypatch.setattr(bridge_main, "UdpReceiver", FakeReceiver)
    monkeypatch.setattr(bridge_main.uvicorn, "run", fake_run)
    monkeypatch.delenv(bridge_main.ORIGINS_ENV, raising=False)
    return seen


def test_main_defaults_bind_and_udp_loopback(captured_main):
    bridge_main.main(["--udp-port-count", "2"])
    assert captured_main["run"]["host"] == "127.0.0.1"
    assert captured_main["receivers"] == [(24800, "127.0.0.1"), (24801, "127.0.0.1")]


def test_main_passes_bind_host_and_udp_host(captured_main):
    bridge_main.main(["--bind-host", "0.0.0.0", "--udp-host", "host.docker.internal", "--port", "8123", "--udp-port-count", "2"])
    assert captured_main["run"]["host"] == "0.0.0.0"
    assert captured_main["run"]["port"] == 8123
    assert captured_main["receivers"] == [(24800, "host.docker.internal"), (24801, "host.docker.internal")]
    assert captured_main["registry"]._udp_host == "host.docker.internal"


def test_allowed_origins_merge_env_and_cli(monkeypatch):
    monkeypatch.setenv(bridge_main.ORIGINS_ENV, " http://a.example:8100, ,http://b.example:8100 ")
    args = bridge_main.build_parser().parse_args(["--allow-origin", "http://b.example:8100", "--allow-origin", "http://c.example"])
    assert bridge_main.allowed_origins(args) == ["http://a.example:8100", "http://b.example:8100", "http://c.example"]


def test_main_env_origin_reaches_websocket_check(captured_main, monkeypatch):
    monkeypatch.setenv(bridge_main.ORIGINS_ENV, "http://192.168.1.5:8100")
    bridge_main.main([])
    client = TestClient(captured_main["app"], base_url="http://127.0.0.1:8000")
    with client.websocket_connect("/ws", headers={**WS_HEADERS, "origin": "http://192.168.1.5:8100"}):
        pass
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers={**WS_HEADERS, "origin": "http://evil.example"}):
            pass


def test_udp_receiver_targets_configured_host_not_loopback(monkeypatch):
    sent = []

    class FakeSock:
        def bind(self, addr): sent.append(("bind", addr))
        def getsockname(self): return ("0.0.0.0", 1)
        def settimeout(self, t): pass
        def sendto(self, data, target):
            sent.append(("sendto", target))
            receiver.stop()
        def recvfrom(self, n): raise socket.timeout()
        def close(self): pass

    monkeypatch.setattr(socket, "socket", lambda *a, **k: FakeSock())
    receiver = UdpReceiver(ControllerRegistry([24800]), 24800, udp_host="host.docker.internal")
    receiver.run()
    assert ("sendto", ("host.docker.internal", 24800)) in sent
    assert ("bind", ("0.0.0.0", 0)) in sent  # 非 loopback 目標：必須能收到來自 host 的回覆


def test_roster_endpoint_reports_configured_udp_host():
    reg = ControllerRegistry([24800], primary_port=24800, udp_host="host.docker.internal")
    assert reg._udp_host == "host.docker.internal"
