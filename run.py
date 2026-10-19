"""项目启动入口：python run.py"""
from __future__ import annotations

import argparse
import socket
import threading
import time
import webbrowser

from backend.server import create_server


def free_port(start: int) -> int:
    for port in range(start, start + 40):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SystemExit("找不到可用端口，请用 --port 指定")


def main() -> None:
    parser = argparse.ArgumentParser(description="回合制 RPG · 十域九王")
    parser.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    port = free_port(args.port) if args.host == "127.0.0.1" else args.port
    httpd = create_server(args.host, port)
    url = f"http://{args.host}:{port}"
    print("=" * 56)
    print("  十域九王 · 回合制 RPG")
    print(f"  服务已启动: {url}")
    print("  按 Ctrl+C 停止服务")
    print("=" * 56)
    if not args.no_browser:
        threading.Thread(target=lambda: (time.sleep(0.8), webbrowser.open(url)), daemon=True).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止。")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
