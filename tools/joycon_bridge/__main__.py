"""python -m tools.joycon_bridge [--port 8000] [--allow-origin http://192.168.x.x:8100]"""

from __future__ import annotations

import argparse

import uvicorn

from .bridge import BIND_HOST, DEFAULT_PORT, DEFAULT_UDP_PORT, ControllerState, PacketLayout, UdpReceiver, create_app


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="REDLINE Joy-Con bridge（只綁 127.0.0.1）")
    p.add_argument("--port", type=int, default=DEFAULT_PORT, help="WebSocket/HTTP 連接埠（預設 8000）")
    p.add_argument("--udp-port", type=int, default=DEFAULT_UDP_PORT, help="Finally the Controller Works 的 UDP 連接埠")
    p.add_argument("--allow-origin", action="append", default=[], metavar="ORIGIN",
                   help="額外允許的網頁 Origin，例如 http://192.168.1.20:8100（可重複）")
    p.add_argument("--dump-packets", action="store_true", help="印出收到的原始 UDP 封包（校正欄位位置用）")
    p.add_argument("--buttons-offset", type=int, default=PacketLayout.buttons_offset)
    p.add_argument("--stick-offset", type=int, default=PacketLayout.stick_offset)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if not 1 <= args.port <= 65535 or not 1 <= args.udp_port <= 65535:
        raise SystemExit("port 必須介於 1–65535")
    layout = PacketLayout(buttons_offset=args.buttons_offset, stick_offset=args.stick_offset)
    state = ControllerState()
    receiver = UdpReceiver(state, args.udp_port, layout, dump=args.dump_packets)
    receiver.start()
    try:
        uvicorn.run(create_app(state, args.allow_origin), host=BIND_HOST, port=args.port, log_level="warning")
    finally:
        receiver.stop()


if __name__ == "__main__":
    main()
