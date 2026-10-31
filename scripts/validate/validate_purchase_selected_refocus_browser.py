#!/usr/bin/env python3
"""正式 Browser proof：購買區已選卡重新聚焦的四種視覺狀態（桌面與客廳模式，固定 1280×720 舞台）。

方向輸入全部經由既有的 mock bridge 搖桿（與 validate_joycon_controller／validate_living_room_controller 相同），
選擇用既有的購買卡 B 勾選；不直接設定 `.rl-pad-focus` 或 `.purchase-card-selected`。

每張購買卡的視覺狀態由實際 computed style 判定：
  白色遮罩  ＝ `.purchase-card-selected-overlay` 顯示、背景 rgba(255,255,255,0.28)
  黃色邊框  ＝ 卡牌 `::after` 有 2px 實線 rgb(255,216,61)
  中央準星  ＝ 同一個 `::after` 的十字＋圓環 background-image
預期：
  已選且已聚焦 → 白罩＋黃框＋準星
  已選未聚焦   → 只有白罩
  未選已聚焦   → 只有黃框＋準星
  未選未聚焦   → 都沒有
且同時最多一組黃框與準星（方向焦點同時只有一張）。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_living_room_controller as vl  # noqa: E402
from validate_joycon_controller import (  # noqa: E402
    MOCK_WS, Pad, enable_controller, focus_dom_toward, post_json, start_server,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/records/purchase/selected-card-refocus-20261020"
REPORT_JSON = ROOT / "docs/records/purchase/SELECTED_CARD_REFOCUS_VALIDATION.json"
REPORT_MD = ROOT / "docs/records/purchase/SELECTED_CARD_REFOCUS_VALIDATION.md"

CARD_STATES_JS = """() => [...document.querySelectorAll('#purchaseRandom .card, #purchaseStatic .card')].map((card, index) => {
  const after = getComputedStyle(card, '::after');
  const overlay = card.querySelector('.purchase-card-selected-overlay');
  const ov = overlay ? getComputedStyle(overlay) : null;
  const hasAfter = after.content !== 'none' && after.display !== 'none';
  const image = after.backgroundImage || '';
  return {
    index, zone: card.closest('#purchaseRandom') ? 'random' : 'static', name: card.dataset.cardName,
    selected: card.classList.contains('purchase-card-selected'),
    focused: card.classList.contains('rl-pad-focus'),
    white: !!ov && ov.display !== 'none' && ov.backgroundColor === 'rgba(255, 255, 255, 0.28)',
    frame: hasAfter && after.borderTopStyle === 'solid' && after.borderTopWidth !== '0px' && after.borderTopColor === 'rgb(255, 216, 61)',
    crosshair: hasAfter && image.includes('linear-gradient') && image.includes('radial-gradient'),
    afterZ: after.zIndex, overlayZ: ov ? ov.zIndex : null,
  };
})"""

EXPECTED = {  # (selected, focused) -> (white, frame, crosshair)
    (True, True): (True, True, True),
    (True, False): (True, False, False),
    (False, True): (False, True, True),
    (False, False): (False, False, False),
}
STATE_NAME = {
    (True, True): "已選且已聚焦", (True, False): "已選但未聚焦", (False, True): "未選但已聚焦", (False, False): "未選且未聚焦",
}


def verdict(states: list[dict]) -> dict:
    wrong = []
    kinds = set()
    for s in states:
        key = (s["selected"], s["focused"])
        kinds.add(key)
        if (s["white"], s["frame"], s["crosshair"]) != EXPECTED[key]:
            wrong.append({"card": f"{s['zone']}:{s['name']}", "state": STATE_NAME[key], "got": [s["white"], s["frame"], s["crosshair"]]})
    focused = [s for s in states if s["focused"]]
    frames = [s for s in states if s["frame"]]
    return {
        "ok": not wrong and len(focused) <= 1 and len(frames) <= 1 and len(frames) == len(focused),
        "wrong": wrong, "focused_count": len(focused), "frame_count": len(frames),
        "crosshair_count": sum(1 for s in states if s["crosshair"]), "white_count": sum(1 for s in states if s["white"]),
        "kinds": sorted(STATE_NAME[k] for k in kinds),
        "layering_ok": all(int(s["afterZ"]) > int(s["overlayZ"]) for s in states if s["selected"] and s["focused"]),
    }


def shot(page, name: str, shots: list[str]) -> None:
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path))
    shots.append(str(path.relative_to(ROOT)))
    panel = page.locator("#randomMarketPanel").bounding_box()
    static = page.locator("#controlPanel").bounding_box()
    clip = {"x": panel["x"], "y": panel["y"], "width": min(panel["width"], 700), "height": static["y"] + static["height"] - panel["y"]}
    crop = OUT / f"{name}_crop.png"
    page.screenshot(path=str(crop), clip=clip)
    shots.append(str(crop.relative_to(ROOT)))


def run_mode(browser, base: str, mode: str, record, errors: list[str], shots: list[str]) -> dict:
    setup = post_json(base, "/test/setup-move-confirmation-proof",
                      {"mover_faction": "taiwan_green", "mover_base": "新竹", "mover_town": "臺北", "moves_left": 5})
    result = post_json(base, "/test/set-hand", {"game_id": setup["game_id"], "player_id": setup["player_id"],
                                                "cards": ["追隨者", "樂捐者", "追隨者"], "turn_phase": "action"})
    assert result.get("success"), result
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    context.add_init_script(MOCK_WS)
    page = context.new_page()
    page.on("console", lambda m: errors.append(f"[{mode}] {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"[{mode}] {e}"))
    suffix = "&display=living-room" if mode == "living-room" else ""
    page.goto(base + setup["url"] + suffix, wait_until="networkidle")
    page.wait_for_selector("#gameShell", state="visible", timeout=15000)
    page.evaluate("() => window.closeEventReveal && closeEventReveal()")
    page.wait_for_timeout(400)
    enable_controller(page)
    pad = Pad(page)
    pad.neutral()
    session = vl.Session(page, record) if mode == "living-room" else None

    stage = page.evaluate("""() => { const s = document.getElementById('designStage'); const r = s.getBoundingClientRect();
      return {w: s.offsetWidth, h: s.offsetHeight, display: document.documentElement.dataset.display || 'desktop', scale: r.width / s.offsetWidth}; }""")
    record(f"{mode}_stage_is_fixed_1280x720_scaled", stage["w"] == 1280 and stage["h"] == 720, stage)

    def focus_card(selector: str, zone: str) -> bool:
        """真實方向輸入把焦點移到指定購買卡。"""
        if mode == "living-room":
            session.goto_zone(zone)
            for _ in range(10):
                pad.push("left")
            for _ in range(int(selector)):
                pad.push("right")
            session.settle()
            return page.evaluate("() => !!document.querySelector('.rl-pad-focus')")
        if not page.evaluate("() => !!document.querySelector('.rl-pad-focus')"):
            pad.push("right")  # 第一次方向輸入只放焦點（既有行為），之後才逐步移動
        return focus_dom_toward(pad, page, selector)

    detail = {}
    for zone, root in (("random", "#purchaseRandom"), ("static", "#purchaseStatic")):
        first = f"{root} .purchase-card-item:nth-child(1) .card"
        if mode == "living-room":
            ok = focus_card("0", zone)
        else:
            ok = focus_card(first, zone)
        states0 = page.evaluate(CARD_STATES_JS)
        v0 = verdict(states0)
        focused_name = next((s["name"] for s in states0 if s["focused"]), None)
        record(f"{mode}_{zone}_direction_input_focuses_exactly_one_card", ok and v0["focused_count"] == 1 and v0["frame_count"] == 1, v0)
        if zone == "random":
            shot(page, f"{mode}_0_unselected_focused_only", shots)

        pad.tap("B")  # 既有購買卡 B：勾選
        page.wait_for_timeout(150)
        s1 = page.evaluate(CARD_STATES_JS)
        v1 = verdict(s1)
        sel = [s for s in s1 if s["selected"]]
        record(f"{mode}_{zone}_selected_and_focused_shows_white_yellow_frame_and_crosshair",
               len(sel) == 1 and sel[0]["focused"] and sel[0]["white"] and sel[0]["frame"] and sel[0]["crosshair"] and v1["ok"] and v1["layering_ok"], v1)
        if zone == "random":
            shot(page, f"{mode}_1_selected_and_focused", shots)

        pad.push("right")  # 焦點離開已選卡
        page.wait_for_timeout(150)
        s2 = page.evaluate(CARD_STATES_JS)
        v2 = verdict(s2)
        sel2 = [s for s in s2 if s["selected"]]
        foc2 = [s for s in s2 if s["focused"]]
        record(f"{mode}_{zone}_selected_unfocused_has_white_only_and_unselected_focused_has_frame_and_crosshair_only",
               len(sel2) == 1 and not sel2[0]["focused"] and sel2[0]["white"] and not sel2[0]["frame"] and not sel2[0]["crosshair"]
               and len(foc2) == 1 and not foc2[0]["selected"] and not foc2[0]["white"] and foc2[0]["frame"] and foc2[0]["crosshair"]
               and v2["ok"] and set(v2["kinds"]) >= {"已選但未聚焦", "未選但已聚焦", "未選且未聚焦"}, v2)
        if zone == "random":
            shot(page, f"{mode}_2_selected_unfocused_and_unselected_focused", shots)

        pad.push("left")  # 方向鍵再次聚焦已選卡
        page.wait_for_timeout(150)
        s3 = page.evaluate(CARD_STATES_JS)
        v3 = verdict(s3)
        sel3 = [s for s in s3 if s["selected"]]
        record(f"{mode}_{zone}_direction_refocus_on_selected_card_restores_all_three_cues_with_single_focus",
               len(sel3) == 1 and sel3[0]["name"] == focused_name and sel3[0]["focused"] and sel3[0]["white"] and sel3[0]["frame"]
               and sel3[0]["crosshair"] and v3["ok"] and v3["focused_count"] == 1 and v3["frame_count"] == 1, v3)
        if zone == "random":
            shot(page, f"{mode}_3_selected_refocused_by_direction", shots)

        pad.tap("B")  # 取消勾選，下一個區域重新驗證
        page.wait_for_timeout(150)
        s4 = page.evaluate(CARD_STATES_JS)
        record(f"{mode}_{zone}_deselect_returns_to_frame_and_crosshair_only", verdict(s4)["ok"]
               and not any(s["selected"] for s in s4) and sum(s["frame"] for s in s4) == 1, verdict(s4))
        detail[zone] = {"first_focus": focused_name, "after_select": v1, "after_move": v2, "after_refocus": v3}

    # 實際購買控制仍可用：選擇仍走既有 checkbox 路徑（selectedPurchaseIndices）
    record(f"{mode}_no_selection_left_behind", page.evaluate("() => selectedPurchaseIndices.size") == 0)
    context.close()
    return detail


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []
    errors: list[str] = []
    shots: list[str] = []

    def record(name: str, ok: bool, detail=None) -> None:
        checks.append({"name": name, "passed": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {json.dumps(detail, ensure_ascii=False, default=str)[:600]}"), flush=True)

    server = None
    base = os.environ.get("REDLINE_BASE_URL", "").rstrip("/")
    if not base:
        server, base = start_server()
    details = {}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for mode in ("desktop", "living-room"):
                try:
                    details[mode] = run_mode(browser, base, mode, record, errors, shots)
                except Exception as exc:
                    record(f"{mode}_scenario_completed_without_exception", False, repr(exc))
            browser.close()
    finally:
        if server:
            server.terminate()
    fatal = [e for e in errors if "favicon" not in e and "Failed to load resource" not in e and "net::ERR" not in e]
    record("browser_console_has_no_errors", not fatal, fatal[:5])

    summary = {"total": len(checks), "passed": sum(1 for c in checks if c["passed"])}
    summary["failed"] = summary["total"] - summary["passed"]
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": summary, "checks": checks, "details": details, "screenshots": shots,
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    REPORT_MD.write_text("\n".join([
        "# 購買區已選卡重新聚焦 Browser 驗證", "", f"Summary: **{summary['passed']}/{summary['total']} passed**", "",
        *[f"- {'PASS' if c['passed'] else 'FAIL'}: `{c['name']}`" for c in checks], "",
        "截圖（固定 1280×720；桌面與客廳模式各四種狀態）：", *[f"- `{p}`" for p in shots], "",
    ]), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    sys.exit(1 if summary["failed"] else 0)


if __name__ == "__main__":
    main()
