"""獨立左右 Joy-Con：實體→邏輯正規化、每支手把的身份／狀態／stale／重連、玩家 claim 與 v2 WebSocket 協定。

規格對照表在 fixtures/joycon_dual_layout.json（逐字取自規格，不由實作推導）。
不碰實體 Joy-Con、不碰 FTCW 的 24800–24803（純函式測試的埠號只是標籤；UDP 測試只用臨時埠）、不碰 8000 的 bridge
（TestClient 不開網路埠）。
"""

import json
import socket
import struct
import time
from pathlib import Path

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tools.joycon_bridge import __main__ as bridge_main
from tools.joycon_bridge import bridge as B

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "joycon_dual_layout.json").read_text(encoding="utf-8"))
INPUTS = FIXTURE["inputs"]
LOGICAL = {name: (index, int(mask, 16)) for name, (index, mask) in FIXTURE["logical_bits"].items()}
WS_HEADERS = {"host": "127.0.0.1:8000"}
LEFT_NAME = "Joy-Con 2 (L)"
RIGHT_NAME = "Joy-Con 2 (R)"


def s2b1(byte_values=None, lx=0.0, ly=0.0, rx=0.0, ry=0.0, seq=1):
    """FTCW v0.2.0 44-byte S2B1：magic | u32 seq | u32 buttons | f32 lx, ly, rx, ry | sensors。byte_values＝{封包 offset: 位元}。"""
    data = bytearray(b"S2B1" + struct.pack("<I", seq) + b"\0" * 4 + struct.pack("<4f", lx, ly, rx, ry) + b"\0" * 16)
    for offset, value in (byte_values or {}).items():
        data[offset] |= value
    assert len(data) == 44
    return bytes(data)


def s2n1(name):
    return b"S2N1" + (name.encode("utf-8") if isinstance(name, str) else name)


def mask(entry):
    return int(entry["mask"], 16)


def expected_bytes(*names):
    out = [0, 0]
    for name in names:
        index, bit = LOGICAL[name]
        out[index] |= bit
    return tuple(out)


def frame_bytes(frame):
    return (frame.b0, frame.b1)


def make_registry(ports=(24800, 24801, 24802, 24803), primary=24800, start=100.0):
    now = [start]
    return B.ControllerRegistry(ports, primary_port=primary, clock=lambda: now[0]), now


def add(reg, port, name, data=None):
    """S2N1 名稱＋（選用）一筆 S2B1；回傳該手把的 controller id。"""
    reg.observe(port, s2n1(name))
    if data is not None:
        reg.observe(port, data)
    return B.controller_id(B.detect_side(name), port, name)


# ---------------------------------------------------------------- physical → logical


@pytest.mark.parametrize("entry", INPUTS, ids=lambda e: f"{e['side']}-{e['physical']}")
def test_each_physical_input_normalizes_to_the_spec_logical_bytes(entry):
    frame = B.parse_packet(s2b1({entry["packet_offset"]: mask(entry)}), side=entry["side"])
    assert frame is not None
    assert frame_bytes(frame) == expected_bytes(entry["logical"])
    assert (frame.x, frame.y) == (0.0, 0.0)


def test_logical_layout_is_the_existing_right_joycon_layout():
    assert {name: tuple(bits) for name, bits in B.LOGICAL_BITS.items()} == LOGICAL


def test_every_left_input_matches_its_right_equivalent():
    right = {e["physical"]: e for e in INPUTS if e["side"] == "right"}
    lefts = [e for e in INPUTS if e["side"] == "left"]
    assert len(lefts) == 11
    for entry in lefts:
        twin = right[entry["right_equivalent"]]
        left_frame = B.parse_packet(s2b1({entry["packet_offset"]: mask(entry)}), side="left")
        right_frame = B.parse_packet(s2b1({twin["packet_offset"]: mask(twin)}), side="right")
        assert frame_bytes(left_frame) == frame_bytes(right_frame), entry["physical"]


def test_each_side_reads_only_its_own_button_bytes():
    every_left = B.parse_packet(s2b1({9: 0xFF, 10: 0xFF}), side="left")
    assert frame_bytes(every_left) == expected_bytes("X", "A", "B", "Y", "STICK", "R", "ZR", "PLUS", "CAPTURE", "SL", "SR")
    # 左手的 offset 8（右手 A/B/X/Y…）與右手的 offset 10（左手方向鍵…）都不屬於自己，不會被誤讀。
    assert B.parse_packet(s2b1({8: 0xFF}), side="left") == B.Frame(0.0, 0.0, 0, 0)
    assert B.parse_packet(s2b1({10: 0xFF, 11: 0xFF}), side="right") == B.Frame(0.0, 0.0, 0, 0)
    assert B.parse_packet(s2b1({8: 0x08}), side="unknown") is None


def test_capture_and_home_never_mix():
    assert expected_bytes("CAPTURE") == (0x00, 0x40) and expected_bytes("HOME") == (0x00, 0x10)
    assert frame_bytes(B.parse_packet(s2b1({9: 0x20}), side="left")) == (0x00, 0x40)   # 左 Capture → Capture
    assert frame_bytes(B.parse_packet(s2b1({9: 0x40}), side="right")) == (0x00, 0x40)  # 右 Capture → Capture
    assert frame_bytes(B.parse_packet(s2b1({9: 0x10}), side="right")) == (0x00, 0x10)  # 右 HOME → HOME（保留）
    # 左手沒有任何實體輸入會變成 HOME：所有位元全按也沒有；右 HOME 的位置（offset 9 0x10）在左手沒有意義。
    assert not B.parse_packet(s2b1({8: 0xFF, 9: 0xFF, 10: 0xFF, 11: 0xFF}), side="left").b1 & 0x10
    assert B.parse_packet(s2b1({9: 0x10}), side="left") == B.Frame(0.0, 0.0, 0, 0)


def test_left_sr_is_right_sl_and_left_sl_is_right_sr():
    assert frame_bytes(B.parse_packet(s2b1({10: 0x10}), side="left")) == (0x20, 0x00)  # 左 SR → 右 SL（聚焦選單）
    assert frame_bytes(B.parse_packet(s2b1({10: 0x20}), side="left")) == (0x10, 0x00)  # 左 SL → 右 SR（上一個區段）


def test_left_stick_offsets_y_axis_and_deadzone():
    data = bytearray(s2b1(rx=-0.9, ry=-0.9))  # 右搖桿欄位放干擾值
    struct.pack_into("<f", data, 12, 0.5)      # 左搖桿 x：offset 12
    struct.pack_into("<f", data, 16, 0.75)     # 左搖桿 y：offset 16，FTCW 向上為正
    frame = B.parse_packet(bytes(data), side="left")
    assert frame.x == pytest.approx(0.5) and frame.y == pytest.approx(-0.75)  # 畫面座標：向上為負
    assert B.parse_packet(s2b1(ly=-0.6), side="left").y == pytest.approx(0.6)
    assert FIXTURE["sticks"]["left"]["deadzone"] == B.STICK_DEADZONE == 0.15
    small = B.parse_packet(s2b1(lx=0.14, ly=-0.149), side="left")
    assert (small.x, small.y) == (0.0, 0.0)
    kept = B.parse_packet(s2b1(lx=0.16, ly=0.2), side="left")
    assert kept.x == pytest.approx(0.16) and kept.y == pytest.approx(-0.2)  # deadzone 之上原值保留（不重新縮放）
    assert B.parse_packet(s2b1(rx=0.9, ry=0.9), side="left") == B.Frame(0.0, 0.0, 0, 0)
    assert B.parse_packet(s2b1(lx=float("nan")), side="left") is None
    assert B.parse_packet(s2b1(ly=1.5), side="left") is None
    # 每一側只驗證自己的搖桿：左搖桿欄位不合法不影響右手。
    assert B.parse_packet(s2b1(lx=float("nan"), rx=0.5), side="right").x == pytest.approx(0.5)


def test_right_stick_keeps_existing_offsets_and_orientation():
    frame = B.parse_packet(s2b1(lx=0.9, ly=0.9, rx=0.5, ry=-0.25), side="right")
    assert frame.x == pytest.approx(0.5) and frame.y == pytest.approx(0.25)
    assert B.parse_packet(s2b1(rx=0.1, ry=-0.1), side="right") == B.Frame(0.0, 0.0, 0, 0)


# ---------------------------------------------------------------- metadata / identity


@pytest.mark.parametrize("name,side", [
    ("Joy-Con 2 (L)", "left"), ("Joy-Con 2 (R)", "right"), ("joy-con (l)", "left"), ("LEFT JOY-CON", "left"),
    ("Right Joy-Con 2", "right"), ("Pro Controller", None), ("Joy-Con (L) / (R)", None), ("LEFT RIGHT", None), ("", None), (None, None),
])
def test_side_detection_uses_the_guarded_name_rule(name, side):
    assert B.detect_side(name) == side


def test_name_packets_are_guarded():
    assert B.parse_name_packet(s2n1(LEFT_NAME)) == LEFT_NAME
    assert B.parse_name_packet(s2n1(b"Joy-Con 2 (R)\x00\x00")) == RIGHT_NAME
    assert B.parse_name_packet(s2n1("  Joy-Con 2 (L)  ")) == LEFT_NAME
    for bad in (b"S2N1", s2n1(b"\x00\x00"), s2n1(b"Joy\x01Con (L)"), s2n1("x" * 65), s2n1(b"\xff\xfe(L)"),
                s2n1("Joy​Con (L)"), b"S2B1Joy-Con (L)", b"", None):
        assert B.parse_name_packet(bad) is None, bad


@pytest.mark.parametrize("value,ok", [
    ("R24800-legacy", True), ("L24801-0a1b2c3d", True), ("left", False), ("right", False), ("L", False), ("R24800", False),
    ("R0-legacy", False), ("R65536-legacy", False), ("R024800-legacy", False), ("X24800-legacy", False), ("L24801-0A1B2C3D", False),
    ("L24801-0a1b2c3", False), ("L24801-0a1b2c3d ", False), ("R24800-legacy\n", False), (24800, False), (None, False),
])
def test_controller_ids_are_strict(value, ok):
    assert B.is_controller_id(value) is ok


def test_identity_combines_side_ftcw_endpoint_and_name_fingerprint():
    assert B.controller_id("right", 24800, None) == "R24800-legacy"
    a = B.controller_id("left", 24801, LEFT_NAME)
    assert B.is_controller_id(a) and a.startswith("L24801-")
    assert a == B.controller_id("left", 24801, LEFT_NAME)  # 穩定
    assert a != B.controller_id("left", 24802, LEFT_NAME)  # 不同 FTCW 埠
    assert a != B.controller_id("left", 24801, "Other Joy-Con (L)")  # 同埠不同裝置名稱
    reg, _ = make_registry()
    ids = {add(reg, 24801, LEFT_NAME), add(reg, 24802, LEFT_NAME), add(reg, 24800, RIGHT_NAME)}
    snap = reg.snapshot()
    assert set(snap) == ids and len(ids) == 3
    assert {(c["side"], c["port"], c["name"], c["side_source"]) for c in snap.values()} == {
        ("left", 24801, LEFT_NAME, "name"), ("left", 24802, LEFT_NAME, "name"), ("right", 24800, RIGHT_NAME, "name")}


# ---------------------------------------------------------------- independent state


def test_two_same_side_joycons_never_overwrite_each_other():
    reg, now = make_registry()
    a = add(reg, 24801, LEFT_NAME, s2b1({10: 0x04}, lx=0.5))  # → 邏輯 A，向右
    b = add(reg, 24802, LEFT_NAME, s2b1({10: 0x01}, ly=0.8))  # ↓ 邏輯 B，向上
    assert a != b
    snap = reg.snapshot()
    assert frame_bytes(snap[a]["frame"]) == (0x08, 0x00) and snap[a]["frame"].x == pytest.approx(0.5)
    assert frame_bytes(snap[b]["frame"]) == (0x04, 0x00) and snap[b]["frame"].y == pytest.approx(-0.8)
    s1, s2 = reg.open_session("v2"), reg.open_session("v2")
    assert reg.claim(s1, a).ok and reg.claim(s2, b).ok
    reg.observe(24802, s2b1({10: 0x08}))  # 第二支換成 ←（邏輯 Y）
    assert reg.session_frame(s1).controller == a and frame_bytes(reg.session_frame(s1).frame) == (0x08, 0x00)
    assert reg.session_frame(s2).controller == b and frame_bytes(reg.session_frame(s2).frame) == (0x01, 0x00)


def test_simultaneous_left_and_right_input_keeps_independent_identity_and_state():
    reg, now = make_registry()
    r = add(reg, 24800, RIGHT_NAME)
    l = add(reg, 24801, LEFT_NAME)
    for _ in range(5):  # 交錯同時輸入
        reg.observe(24800, s2b1({8: 0x08}, rx=0.6))
        reg.observe(24801, s2b1({10: 0x20}, ly=-0.7))
        now[0] += 0.01
    snap = reg.snapshot()
    assert snap[r]["side"] == "right" and frame_bytes(snap[r]["frame"]) == (0x08, 0x00) and snap[r]["frame"].x == pytest.approx(0.6)
    assert snap[l]["side"] == "left" and frame_bytes(snap[l]["frame"]) == (0x10, 0x00) and snap[l]["frame"].y == pytest.approx(0.7)
    assert snap[r]["packets"] == snap[l]["packets"] == 5 and snap[r]["epoch"] == snap[l]["epoch"] == 1
    s1, s2 = reg.open_session("v2"), reg.open_session("v2")
    assert reg.claim(s1, r).ok and reg.claim(s2, l).ok
    assert (reg.session_frame(s1).side, reg.session_frame(s2).side) == ("right", "left")
    roster = reg.roster(s1)
    assert roster["owned"] == r
    assert {c["id"]: c["owner"] for c in roster["controllers"]} == {r: "you", l: "other"}


def test_stale_clears_only_that_controller_and_keeps_its_owner():
    reg, now = make_registry()
    r = add(reg, 24800, RIGHT_NAME, s2b1({8: 0x08}, rx=0.8))
    l = add(reg, 24801, LEFT_NAME, s2b1({10: 0xC0}, lx=-0.9))  # 按住 L＋ZL、搖桿推到底
    s1, s2 = reg.open_session("v2"), reg.open_session("v2")
    assert reg.claim(s1, r).ok and reg.claim(s2, l).ok
    now[0] += 0.6
    reg.observe(24800, s2b1({8: 0x08}, rx=0.8))  # 右手持續送
    now[0] += 0.6                                 # 左手 1.2 秒沒有封包
    snap = reg.snapshot()
    assert snap[l]["status"] == "stale" and snap[l]["frame"] is None  # 不殘留按鍵或搖桿
    assert snap[l]["owner"] == s2 and reg.session_frame(s2) is None
    assert snap[r]["status"] == "active" and frame_bytes(reg.session_frame(s1).frame) == (0x08, 0x00)
    assert {c["id"]: c["status"] for c in reg.roster(s2)["controllers"]} == {r: "active", l: "stale"}
    assert reg.roster(s2)["owned"] == l


def test_reconnect_with_the_same_identity_keeps_the_owner_and_starts_a_new_epoch():
    reg, now = make_registry()
    l = add(reg, 24801, LEFT_NAME, s2b1({10: 0xC0}, lx=-0.9))
    s = reg.open_session("v2")
    assert reg.claim(s, l).ok
    epoch = reg.session_frame(s).epoch
    now[0] += 3.0
    assert reg.session_frame(s) is None
    reg.observe(24801, s2n1(LEFT_NAME))     # FTCW 重新報名（同名同埠）
    reg.observe(24801, s2b1({10: 0x01}))    # 只按 ↓
    owned = reg.session_frame(s)
    assert owned.controller == l and owned.epoch == epoch + 1
    assert frame_bytes(owned.frame) == (0x04, 0x00) and owned.frame.x == 0.0  # 只有新狀態，沒有斷線前的按鍵／搖桿
    assert reg.snapshot()[l]["owner"] == s


def test_reconnect_on_another_port_is_a_new_unclaimed_controller():
    reg, now = make_registry()
    old = add(reg, 24801, LEFT_NAME, s2b1())
    s = reg.open_session("v2")
    assert reg.claim(s, old).ok
    now[0] += 3.0
    new = add(reg, 24802, LEFT_NAME, s2b1({10: 0x04}))
    assert new != old
    snap = reg.snapshot()
    assert snap[new]["owner"] is None and snap[old]["owner"] == s
    assert reg.session_frame(s) is None  # 不會自動接到新埠那一支
    other = reg.open_session("v2")
    assert reg.claim(other, new).ok


def test_a_different_device_on_the_same_endpoint_retires_the_old_identity():
    reg, now = make_registry()
    l = add(reg, 24801, LEFT_NAME, s2b1({10: 0x04}))
    s = reg.open_session("v2")
    assert reg.claim(s, l).ok
    r = add(reg, 24801, RIGHT_NAME, s2b1({8: 0x01}))  # 同一個 FTCW 埠換成右手
    snap = reg.snapshot()
    assert l not in snap and snap[r]["owner"] is None and frame_bytes(snap[r]["frame"]) == (0x01, 0x00)
    roster = reg.roster(s)
    assert roster["owned"] is None and roster["lost"] == {"controller": l, "reason": "replaced"}
    assert reg.claim(s, r).ok and "lost" not in reg.roster(s)
    renamed = add(reg, 24801, "Another Joy-Con (R)", s2b1())  # 同側不同名稱＝不同裝置
    assert renamed != r and r not in reg.snapshot() and reg.roster(s)["lost"] == {"controller": r, "reason": "replaced"}
    reg.observe(24801, s2n1("Pro Controller"))  # 名稱無法判定左右 → 該埠 fail closed
    reg.observe(24801, s2b1({8: 0x08}))
    assert reg.snapshot() == {}


def test_unnamed_and_ambiguous_endpoints_fail_closed():
    reg, now = make_registry(primary=24800)
    reg.observe(24801, s2b1({8: 0x08}))            # 非主埠、沒有 S2N1
    now[0] += 5.0
    reg.observe(24801, s2b1({8: 0x08}))
    reg.observe(24802, s2n1("Pro Controller"))     # 名稱無法判定左右
    reg.observe(24802, s2b1({8: 0x08}))
    reg.observe(24799, s2n1(RIGHT_NAME))           # 不是設定的 FTCW 埠
    reg.observe(24799, s2b1({8: 0x08}))
    assert reg.snapshot() == {}
    s = reg.open_session("legacy")
    assert not reg.claim_default(s).ok and reg.session_frame(s) is None


def test_primary_port_without_a_name_gets_an_explicit_legacy_identity_after_a_grace():
    reg, now = make_registry(primary=24800)
    reg.observe(24800, s2b1({8: 0x08}))
    now[0] += B.NAME_GRACE_S - 0.05
    reg.observe(24800, s2b1({8: 0x08}))
    assert reg.snapshot() == {}  # 等 S2N1 的寬限期內不建立身份、不轉送
    now[0] += 0.1
    reg.observe(24800, s2b1({9: 0x20}))  # 上游 capture（0x2000）在舊版預設身份仍是 CAPTURE
    snap = reg.snapshot()
    assert list(snap) == ["R24800-legacy"]
    assert snap["R24800-legacy"]["side"] == "right" and snap["R24800-legacy"]["side_source"] == "legacy-default"
    assert frame_bytes(snap["R24800-legacy"]["frame"]) == (0x00, 0x40)
    s = reg.open_session("legacy")
    assert reg.claim_default(s).ok and reg.session_frame(s).controller == "R24800-legacy"
    named = add(reg, 24800, RIGHT_NAME, s2b1({8: 0x08}))  # 名稱晚到：身份改變，不沿用舊版預設身份的擁有者
    assert named != "R24800-legacy" and reg.snapshot()[named]["owner"] is None
    assert reg.roster(s)["lost"] == {"controller": "R24800-legacy", "reason": "replaced"}


# ---------------------------------------------------------------- claim / selection


def test_claims_fail_closed():
    reg, now = make_registry()
    r = add(reg, 24800, RIGHT_NAME, s2b1())
    l = add(reg, 24801, LEFT_NAME, s2b1())
    s1, s2 = reg.open_session("v2"), reg.open_session("v2")
    for bad in ("left", "right", None, 123, "", "R24800", "R24800-legacy\n", "x" * 100, {"id": r}):
        result = reg.claim(s1, bad)
        assert (result.ok, result.reason) == (False, "invalid-controller"), bad
    assert reg.claim(s1, "L24803-0a1b2c3d").reason == "unknown-controller"
    assert reg.claim("no-such-session", r).reason == "no-session"
    assert reg.session_frame(s1) is None  # 未 claim：沒有任何 frame
    assert reg.claim(s1, r) == B.ClaimResult(True, r, None)
    assert reg.claim(s1, r) == B.ClaimResult(True, r, None)  # 重複 claim 同一支：冪等
    taken = reg.claim(s2, r)
    assert (taken.ok, taken.reason) == (False, "claimed") and reg.snapshot()[r]["owner"] == s1
    now[0] += 2.0
    reg.observe(24800, s2b1())
    assert reg.claim(s2, l).reason == "not-active"  # 沒有訊號的手把不能 claim
    reg.observe(24801, s2b1())
    assert reg.claim(s1, l).ok  # 切換：放掉原本的右手
    assert reg.snapshot()[r]["owner"] is None and reg.snapshot()[l]["owner"] == s1
    assert reg.claim(s2, r).ok
    assert reg.release(s1).ok and reg.snapshot()[l]["owner"] is None and reg.session_frame(s1) is None
    assert reg.session_frame(s2).controller == r


def test_claim_default_is_only_the_single_right_joycon():
    reg, now = make_registry()
    s1, s2 = reg.open_session("v2"), reg.open_session("v2")
    assert reg.claim_default(s1).reason == "no-default"  # 沒有手把
    l = add(reg, 24801, LEFT_NAME, s2b1())
    assert reg.claim_default(s1).reason == "no-default"  # 唯一一支是左手：不自動綁定
    assert reg.claim(s2, l).ok  # 左手要明確選擇
    reg2, now2 = make_registry()
    r = add(reg2, 24800, RIGHT_NAME, s2b1())
    a, b = reg2.open_session("v2"), reg2.open_session("v2")
    assert reg2.claim_default(a) == B.ClaimResult(True, r, None)
    assert reg2.claim_default(a).reason == "already-owned"
    assert reg2.claim_default(b).reason == "no-default"  # 唯一的右手已被使用
    reg2.release(a)
    now2[0] += 2.0
    assert reg2.claim_default(b).reason == "no-default"  # 沒有訊號
    reg2.observe(24800, s2b1())
    add(reg2, 24801, LEFT_NAME, s2b1())
    assert reg2.claim_default(b).reason == "no-default"  # 兩支：要手動選


def test_a_second_controller_never_takes_over_the_first_player():
    reg, now = make_registry()
    r1 = add(reg, 24800, RIGHT_NAME, s2b1({8: 0x08}))
    p1 = reg.open_session("legacy")
    assert reg.claim_default(p1).ok and reg.session_frame(p1).controller == r1
    r2 = add(reg, 24801, RIGHT_NAME, s2b1({8: 0x04}))  # 第二支右手加入
    assert reg.session_frame(p1).controller == r1 and frame_bytes(reg.session_frame(p1).frame) == (0x08, 0x00)
    p2 = reg.open_session("v2")
    assert reg.claim_default(p2).reason == "no-default"
    assert reg.claim(p2, r2).ok
    now[0] += 2.0
    reg.observe(24801, s2b1({8: 0x02}))  # 第一支斷訊、第二支持續
    assert reg.session_frame(p1) is None and reg.snapshot()[r1]["owner"] == p1
    assert reg.claim_default(p1).reason == "already-owned"


def test_closing_a_session_or_upgrading_to_v2_releases_only_its_own_controller():
    reg, now = make_registry()
    r = add(reg, 24800, RIGHT_NAME, s2b1())
    l = add(reg, 24801, LEFT_NAME, s2b1())
    s1, s2 = reg.open_session("v2"), reg.open_session("v2")
    assert reg.claim(s1, r).ok and reg.claim(s2, l).ok
    reg.close_session(s1)
    assert reg.snapshot()[r]["owner"] is None and reg.snapshot()[l]["owner"] == s2
    reg2, _ = make_registry()
    only = add(reg2, 24800, RIGHT_NAME, s2b1())
    legacy = reg2.open_session("pending")
    reg2.set_session_mode(legacy, "legacy")
    assert reg2.claim_default(legacy).ok
    reg2.set_session_mode(legacy, "v2")  # 新版頁面送出 hello：只擁有自己明確 claim 的手把
    assert reg2.snapshot()[only]["owner"] is None and reg2.roster(legacy)["owned"] is None


# ---------------------------------------------------------------- WebSocket（TestClient，不開網路埠）


def recv_until(ws, predicate, limit=400):
    seen = []
    for _ in range(limit):
        message = ws.receive_json()
        seen.append(message)
        if predicate(message):
            return message, seen
    raise AssertionError(f"no matching message in {limit}: {seen[-5:]}")


def two_controllers():
    reg, now = make_registry()
    r = add(reg, 24800, RIGHT_NAME, s2b1({8: 0x08}, rx=0.5))   # 右 A＋向右
    l = add(reg, 24801, LEFT_NAME, s2b1({10: 0x10}, ly=0.9))   # 左 SR（→ 邏輯 SL）＋向上
    return reg, now, r, l


def test_ws_v2_roster_claim_and_only_the_owned_controllers_frames():
    reg, now, r, l = two_controllers()
    client = TestClient(B.create_app(reg), base_url="http://127.0.0.1:8000")
    with client.websocket_connect("/ws", headers=WS_HEADERS) as ws:
        ws.send_json({"type": "hello", "v": 2})
        roster, _ = recv_until(ws, lambda m: m.get("type") == "roster")
        assert roster["v"] == 2 and roster["owned"] is None
        assert {c["id"]: (c["side"], c["status"], c["owner"]) for c in roster["controllers"]} == {
            r: ("right", "active", None), l: ("left", "active", None)}
        ws.send_json({"type": "claim", "v": 2, "controller": l})
        result, seen = recv_until(ws, lambda m: m.get("type") == "claim-result")
        assert result == {"type": "claim-result", "v": 2, "request": "claim", "ok": True, "controller": l, "reason": None}
        assert not any(m.get("type") == "frame" or "buttons" in m for m in seen)  # claim 之前什麼 frame 都沒有
        frame, _ = recv_until(ws, lambda m: m.get("type") == "frame")
        assert set(frame) == {"type", "v", "controller", "side", "epoch", "x", "y", "buttons"}
        assert (frame["controller"], frame["side"], frame["buttons"]) == (l, "left", [0x20, 0x00])
        assert frame["y"] == pytest.approx(-0.9)
        owned_roster, _ = recv_until(ws, lambda m: m.get("type") == "roster" and m["owned"] == l)
        assert {c["id"]: c["owner"] for c in owned_roster["controllers"]} == {r: None, l: "you"}
        for _ in range(45):
            message = ws.receive_json()
            assert message.get("type") != "frame" or message["controller"] == l


def test_ws_two_players_each_receive_only_their_own_controller():
    reg, now, r, l = two_controllers()
    client = TestClient(B.create_app(reg), base_url="http://127.0.0.1:8000")
    with client.websocket_connect("/ws", headers=WS_HEADERS) as a, client.websocket_connect("/ws", headers=WS_HEADERS) as b:
        for ws in (a, b):
            ws.send_json({"type": "hello", "v": 2})
            recv_until(ws, lambda m: m.get("type") == "roster")
        a.send_json({"type": "claim", "v": 2, "controller": r})
        assert recv_until(a, lambda m: m.get("type") == "claim-result")[0]["ok"] is True
        b.send_json({"type": "claim", "v": 2, "controller": r})
        refused = recv_until(b, lambda m: m.get("type") == "claim-result")[0]
        assert (refused["ok"], refused["reason"]) == (False, "claimed")
        b.send_json({"type": "claim", "v": 2, "controller": l})
        assert recv_until(b, lambda m: m.get("type") == "claim-result")[0]["ok"] is True
        fa = recv_until(a, lambda m: m.get("type") == "frame")[0]
        fb = recv_until(b, lambda m: m.get("type") == "frame")[0]
        assert (fa["controller"], fa["buttons"]) == (r, [0x08, 0x00])
        assert (fb["controller"], fb["buttons"]) == (l, [0x20, 0x00])
        for _ in range(30):
            ma, mb = a.receive_json(), b.receive_json()
            assert ma.get("type") != "frame" or ma["controller"] == r
            assert mb.get("type") != "frame" or mb["controller"] == l
    assert all(c["owner"] is None for c in reg.snapshot().values())  # 連線結束即釋放


def test_ws_v2_rejects_bad_messages_and_illegal_claims():
    reg, now, r, l = two_controllers()
    client = TestClient(B.create_app(reg), base_url="http://127.0.0.1:8000")
    with client.websocket_connect("/ws", headers=WS_HEADERS) as ws:
        ws.send_json({"type": "hello", "v": 2})
        recv_until(ws, lambda m: m.get("type") == "roster")
        for bad in ("not json", json.dumps({"type": "claim", "v": 1, "controller": l}), json.dumps(["claim"]),
                    json.dumps({"type": "steal", "v": 2}), "x" * 2000):
            ws.send_text(bad)
            assert recv_until(ws, lambda m: m.get("type") == "error")[0] == {"type": "error", "v": 2, "reason": "bad-message"}
        for controller, reason in (("left", "invalid-controller"), (None, "invalid-controller"), ("L24803-0a1b2c3d", "unknown-controller")):
            ws.send_json({"type": "claim", "v": 2, "controller": controller})
            result = recv_until(ws, lambda m: m.get("type") == "claim-result")[0]
            assert (result["ok"], result["reason"], result["controller"]) == (False, reason, None)
        assert all(c["owner"] is None for c in reg.snapshot().values())


def test_ws_legacy_client_gets_the_single_right_joycon_in_the_legacy_payload_shape():
    reg, now = make_registry()
    r = add(reg, 24800, RIGHT_NAME, s2b1({8: 0x08}, rx=0.5, ry=-0.25))
    client = TestClient(B.create_app(reg), base_url="http://127.0.0.1:8000")
    with client.websocket_connect("/ws", headers=WS_HEADERS) as ws:  # 舊版頁面：不送任何訊息
        message = ws.receive_json()
        assert message == {"x": pytest.approx(0.5), "y": pytest.approx(0.25), "buttons": [0x08, 0x00]}
        assert reg.snapshot()[r]["owner"] is not None
    assert reg.snapshot()[r]["owner"] is None


def test_ws_and_health_enforce_loopback_host_and_origin():
    reg, now, r, l = two_controllers()
    client = TestClient(B.create_app(reg, ["http://192.168.1.5:8100"]), base_url="http://127.0.0.1:8000")
    with client.websocket_connect("/ws", headers={**WS_HEADERS, "origin": "http://192.168.1.5:8100"}) as ws:
        ws.send_json({"type": "hello", "v": 2})
        assert recv_until(ws, lambda m: m.get("type") == "roster")[0]["v"] == 2
    for headers in ({**WS_HEADERS, "origin": "http://evil.example"}, {"host": "evil.example"}, {"host": "127.0.0.1.evil.com"}):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws", headers=headers):
                pass
    health = client.get("/health", headers=WS_HEADERS).json()
    assert health["ok"] is True and {c["id"] for c in health["controllers"]} == {r, l}
    assert client.get("/health", headers={"host": "evil.example"}).status_code == 403


# ---------------------------------------------------------------- UDP（臨時埠的假 FTCW）／CLI


def test_udp_receivers_identify_each_joycon_on_its_own_ftcw_port():
    fakes = []
    for _ in range(2):
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server.bind(("127.0.0.1", 0))
        server.settimeout(3)
        fakes.append(server)
    left_port, right_port = (f.getsockname()[1] for f in fakes)
    reg = B.ControllerRegistry([left_port, right_port], primary_port=right_port)
    receivers = [B.UdpReceiver(reg, port) for port in (left_port, right_port)]
    for receiver in receivers:
        receiver.start()
    try:
        for server, name, packet in ((fakes[0], LEFT_NAME, s2b1({10: 0x02}, lx=0.4)),
                                     (fakes[1], RIGHT_NAME, s2b1({8: 0x02}, rx=-0.4))):
            data, addr = server.recvfrom(64)
            assert data == b"hello" and addr[0] == "127.0.0.1"
            server.sendto(b"junk", addr)
            server.sendto(s2n1(name), addr)
            server.sendto(packet, addr)
        for _ in range(60):
            if len([c for c in reg.snapshot().values() if c["frame"] is not None]) == 2:
                break
            time.sleep(0.05)
        snap = reg.snapshot()
        left = snap[B.controller_id("left", left_port, LEFT_NAME)]
        right = snap[B.controller_id("right", right_port, RIGHT_NAME)]
        assert frame_bytes(left["frame"]) == (0x02, 0x00) and left["frame"].x == pytest.approx(0.4)
        assert frame_bytes(right["frame"]) == (0x02, 0x00) and right["frame"].x == pytest.approx(-0.4)
        assert reg.stats()["rejected"] == 2
        assert all(receiver.local_address[0] == "127.0.0.1" for receiver in receivers)  # UDP 只綁 loopback
    finally:
        for receiver in receivers:
            receiver.stop()
            receiver.join(2)
        for server in fakes:
            server.close()


def test_cli_probes_consecutive_ftcw_ports_and_stays_loopback_only():
    parser = bridge_main.build_parser()
    assert bridge_main.udp_ports(parser.parse_args([])) == [24800, 24801, 24802, 24803]
    assert bridge_main.udp_ports(parser.parse_args(["--udp-port", "25000", "--udp-port-count", "2"])) == [25000, 25001]
    for bad in (["--udp-port-count", "0"], ["--udp-port-count", "9"], ["--udp-port", "65535", "--udp-port-count", "2"], ["--udp-port", "0"]):
        with pytest.raises(SystemExit):
            bridge_main.udp_ports(parser.parse_args(bad))
    assert "--host" not in parser.format_help()
