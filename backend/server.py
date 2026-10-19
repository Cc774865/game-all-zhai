"""HTTP 服务：零依赖（Python 标准库）的 REST API + 静态前端托管。"""
from __future__ import annotations

import json
import mimetypes
import os
import posixpath
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .data_loader import areas, classes, enemies
from .game import VERSION, GameError, GameService

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
LOCK = threading.Lock()
SERVICE = GameService()


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "RPGServer/1.0"
    protocol_version = "HTTP/1.1"

    # ---------- 输出工具 ----------
    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: str) -> None:
        if not os.path.isfile(path):
            self._send_json({"error": "资源不存在"}, 404)
            return
        ctype, _ = mimetypes.guess_type(path)
        ctype = ctype or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        with open(path, "rb") as fp:
            body = fp.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise GameError("请求体不是合法 JSON")

    def log_message(self, fmt: str, *args) -> None:  # 静音默认访问日志
        pass

    # ---------- 路由 ----------
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)
        try:
            with LOCK:
                if path == "/api/state":
                    self._send_json(SERVICE.state())
                    return
                if path == "/api/meta":
                    self._send_json(self._meta())
                    return
                if path == "/api/saves":
                    from .modules import save as save_mod
                    self._send_json({"saves": save_mod.list_saves()})
                    return
                if path.startswith("/api/"):
                    self._send_json({"error": "接口不存在"}, 404)
                    return
            self._serve_static(path)
        except GameError as exc:
            self._send_json({"error": str(exc)}, 400)
        except Exception as exc:  # noqa: BLE001
            self._send_json({"error": f"服务器内部错误: {exc}"}, 500)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            payload = self._read_json()
        except GameError as exc:
            self._send_json({"error": str(exc)}, 400)
            return
        try:
            with LOCK:
                if path == "/api/new":
                    self._send_json(SERVICE.new_game(payload.get("name", ""), payload.get("class_id", "")))
                    return
                if path == "/api/load":
                    self._send_json(SERVICE.load_game(payload.get("slot", "")))
                    return
                if path == "/api/action":
                    self._send_json(SERVICE.do_action(payload.get("action", ""), payload))
                    return
                if path == "/api/battle":
                    self._send_json(SERVICE.battle_action(payload))
                    return
                if path == "/api/save":
                    self._send_json(SERVICE.save_game(payload.get("slot", "")))
                    return
                if path == "/api/delete-save":
                    self._send_json(SERVICE.delete_save(payload.get("slot", "")))
                    return
                if path == "/api/leave":
                    self._send_json(SERVICE.leave())
                    return
                self._send_json({"error": "接口不存在"}, 404)
        except ValueError as exc:
            self._send_json({"error": str(exc), "state": SERVICE.state()}, 400)
        except Exception as exc:  # noqa: BLE001
            self._send_json({"error": f"服务器内部错误: {exc}"}, 500)

    def _serve_static(self, path: str) -> None:
        if path in ("/", ""):
            path = "/index.html"
        safe = posixpath.normpath(path).lstrip("/")
        full = os.path.realpath(os.path.join(FRONTEND_DIR, safe))
        if not full.startswith(os.path.realpath(FRONTEND_DIR)):
            self._send_json({"error": "禁止访问"}, 403)
            return
        self._send_file(full)

    def _meta(self) -> dict:
        cls = classes()
        return {
            "version": VERSION,
            "classes": [
                {
                    "id": key,
                    "name": value["name"],
                    "title": value["title"],
                    "emoji": value["emoji"],
                    "desc": value["desc"],
                    "difficulty": value["difficulty"],
                    "base": value["base"],
                    "growth": value["growth"],
                }
                for key, value in cls.items()
            ],
            "areas": [
                {
                    "id": a["id"], "name": a["name"], "emoji": a["emoji"],
                    "level_range": a["level_range"], "safe": a["safe"],
                    "boss": a["boss"], "desc": a["desc"],
                }
                for a in areas()
            ],
            "counts": {
                "classes": len(cls),
                "areas": len(areas()),
                "bosses": sum(1 for a in areas() if a["boss"]),
                "enemies": len(enemies()),
            },
        }


def create_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), ApiHandler)
    httpd.daemon_threads = True
    return httpd
