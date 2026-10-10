"""Joy-Con bridge：封包解析、NaN/範圍驗證、stale、Host/Origin、只綁 loopback。"""

import socket
import struct
import time

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tools.joycon_bridge import __main__ as bridge_main
from tools.joycon_bridge.bridge import (
    BIND_HOST,
    ControllerState,
    Frame,
    PacketLayout,
    UdpReceiver,
    create_app,
    frame_payload,
    host_allowed,
    origin_allowed,
    parse_packet,
)


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


def test_parse_valid_packet():
    assert parse_packet(packet(0.5, -0.25, 0x08, 0x02)) == Frame(0.5, -0.25, 0x08, 0x02)


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


def test_capture_upstream_uint32_reaches_browser_as_b1_0x20():
    # Upstream switch2mac Switch2Protocol.swift: capture = 0x0000_2000; UDPHub writes the raw UInt32 little-endian.
    # Expected bytes are literals from that definition, not derived from BUTTON_BITS.
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
    assert (frame.b0, frame.b1) == (0x00, 0x20)
    assert frame_payload(frame)["buttons"] == [0x00, 0x20]
    state = ControllerState()
    state.update(frame)
    client = TestClient(create_app(state), base_url="http://127.0.0.1:8000")
    with client.websocket_connect("/ws", headers={"host": "127.0.0.1:8000"}) as ws:
        assert ws.receive_json()["buttons"] == [0x00, 0x20]


def test_custom_layout_offsets():
    layout = PacketLayout(buttons_offset=6, stick_offset=8, min_length=16)
    data = b"S2B1" + bytes([1, 2, 0x40, 0x04]) + struct.pack("<2f", 0.1, 0.2)
    frame = parse_packet(data, layout)
    assert (frame.b0, frame.b1) == (0x40, 0x04)


def test_state_goes_stale_and_payload_shape():
    now = [100.0]
    state = ControllerState(clock=lambda: now[0])
    assert state.fresh_frame() is None
    state.update(Frame(0.1, 0.2, 8, 0))
    assert frame_payload(state.fresh_frame()) == {"x": 0.1, "y": 0.2, "buttons": [8, 0]}
    now[0] += 5
    assert state.fresh_frame() is None
    assert state.stats()["packets"] == 1


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
    state = ControllerState()
    state.update(Frame(0.3, -0.4, 4, 0))
    client = TestClient(create_app(state, ["http://192.168.1.5:8100"]), base_url="http://127.0.0.1:8000")
    with client.websocket_connect("/ws", headers={"host": "127.0.0.1:8000", "origin": "http://192.168.1.5:8100"}) as ws:
        assert ws.receive_json() == {"x": pytest.approx(0.3), "y": pytest.approx(-0.4), "buttons": [4, 0]}
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers={"host": "127.0.0.1:8000", "origin": "http://evil.example"}):
            pass
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers={"host": "evil.example"}):
            pass


def test_health_endpoint():
    assert TestClient(create_app(ControllerState())).get("/health").json()["ok"] is True


def test_bind_host_is_loopback_only():
    assert BIND_HOST == "127.0.0.1"
    assert "--host" not in bridge_main.build_parser().format_help()


def test_udp_receiver_sends_hello_and_ingests_packets():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    server.settimeout(3)
    state = ControllerState()
    receiver = UdpReceiver(state, server.getsockname()[1], PacketLayout())
    receiver.start()
    try:
        data, addr = server.recvfrom(64)
        assert data == b"hello"
        server.sendto(b"junk", addr)
        server.sendto(packet(0.5, 0.0, 0x08), addr)
        for _ in range(60):
            if state.fresh_frame():
                break
            time.sleep(0.05)
        assert state.fresh_frame().b0 == 0x08
        assert state.stats()["rejected"] == 1
    finally:
        receiver.stop()
        receiver.join(2)
        server.close()
