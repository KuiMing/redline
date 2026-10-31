"""python -m tools.joycon_bridge [--port 8000] [--udp-port 24800 --udp-port-count 4] [--allow-origin http://192.168.x.x:8100]"""

from __future__ import annotations

import argparse
import os

import uvicorn

from .bridge import (
    DEFAULT_BIND_HOST,
    DEFAULT_PORT,
    DEFAULT_UDP_HOST,
    DEFAULT_UDP_PORT,
    DEFAULT_UDP_PORT_COUNT,
    MAX_UDP_PORT_COUNT,
    ControllerRegistry,
    PacketLayout,
    UdpReceiver,
    create_app,
)


ORIGINS_ENV = "REDLINE_JOYCON_ALLOW_ORIGINS"


def allowed_origins(args: argparse.Namespace) -> list[str]:
    from_env = [o.strip() for o in os.environ.get(ORIGINS_ENV, "").split(",") if o.strip()]
    return list(dict.fromkeys([*from_env, *args.allow_origin]))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="REDLINE Joy-Con bridge（預設只綁 127.0.0.1）")
    p.add_argument("--port", type=int, default=DEFAULT_PORT, help="WebSocket/HTTP 連接埠（預設 8000）")
    p.add_argument("--bind-host", default=DEFAULT_BIND_HOST,
                   help="WebSocket/HTTP 綁定位址（預設 127.0.0.1；Docker 容器內用 0.0.0.0，並只把 host port 發布到 127.0.0.1）")
    p.add_argument("--udp-host", default=DEFAULT_UDP_HOST,
                   help="Finally the Controller Works 所在主機（預設 127.0.0.1；Docker 內用 host.docker.internal）")
    p.add_argument("--udp-port", type=int, default=DEFAULT_UDP_PORT,
                   help="Finally the Controller Works 的第一個 UDP 連接埠；也是舊版「單一右 Joy-Con」預設身份所在的埠")
    p.add_argument("--udp-port-count", type=int, default=DEFAULT_UDP_PORT_COUNT,
                   help=f"從 --udp-port 起連續探測幾個 FTCW 埠（每埠一支手把，1–{MAX_UDP_PORT_COUNT}，預設 {DEFAULT_UDP_PORT_COUNT}）")
    p.add_argument("--allow-origin", action="append", default=[], metavar="ORIGIN",
                   help=f"額外允許的網頁 Origin，例如 http://192.168.1.20:8100（可重複；也可用環境變數 {ORIGINS_ENV}，以逗號分隔）")
    p.add_argument("--dump-packets", action="store_true", help="印出收到的原始 UDP 封包（校正欄位位置用）")
    p.add_argument("--buttons-offset", type=int, default=PacketLayout.buttons_offset)
    p.add_argument("--stick-offset", type=int, default=PacketLayout.stick_offset, help="右搖桿 rx/ry 的 offset")
    p.add_argument("--left-stick-offset", type=int, default=PacketLayout.left_stick_offset, help="左搖桿 lx/ly 的 offset")
    return p


def udp_ports(args: argparse.Namespace) -> list[int]:
    if not 1 <= args.udp_port_count <= MAX_UDP_PORT_COUNT:
        raise SystemExit(f"--udp-port-count 必須介於 1–{MAX_UDP_PORT_COUNT}")
    ports = list(range(args.udp_port, args.udp_port + args.udp_port_count))
    if not all(1 <= port <= 65535 for port in ports):
        raise SystemExit("UDP port 必須介於 1–65535")
    return ports


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if not 1 <= args.port <= 65535:
        raise SystemExit("port 必須介於 1–65535")
    ports = udp_ports(args)
    layout = PacketLayout(buttons_offset=args.buttons_offset, stick_offset=args.stick_offset, left_stick_offset=args.left_stick_offset)
    registry = ControllerRegistry(ports, primary_port=args.udp_port, layout=layout, udp_host=args.udp_host)
    receivers = [UdpReceiver(registry, port, dump=args.dump_packets, udp_host=args.udp_host) for port in ports]
    for receiver in receivers:
        receiver.start()
    try:
        uvicorn.run(create_app(registry, allowed_origins(args)), host=args.bind_host, port=args.port, log_level="warning")
    finally:
        for receiver in receivers:
            receiver.stop()


if __name__ == "__main__":
    main()
