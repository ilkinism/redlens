"""The one process: the page and the API on a single port.

Nothing here opens an outbound connection. That is the product's central
promise, and it is kept by the code containing no client of any kind.
"""

from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from redlens.api import RedlensAPI, Reply
from redlens.config import Config, load_config

WEB_ROOT = Path(__file__).resolve().parents[2] / "web"


class Handler(BaseHTTPRequestHandler):
    api: RedlensAPI = None
    web_root: Path = WEB_ROOT
    max_body: int = 67_108_864
    server_version = "Redlens"

    def _send(self, status, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # A page that must not exfiltrate says so to the browser as well.
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; connect-src 'self'; "
                         "img-src 'self' data:; style-src 'self'; "
                         "script-src 'self'; form-action 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, reply: Reply):
        self._send(reply.status, json.dumps(reply.body).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > self.max_body:
            return "too-large"
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    def log_message(self, fmt, *args):
        pass

    def _serve_asset(self, path):
        relative = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
        target = (self.web_root / relative).resolve()
        root = self.web_root.resolve()
        if root not in target.parents and target != root:
            self._send(403, b"forbidden", "text/plain; charset=utf-8")
            return
        if not target.is_file():
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        kind = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        charset = ("; charset=utf-8" if kind.startswith("text/")
                   or kind.endswith("javascript") else "")
        self._send(200, target.read_bytes(), f"{kind}{charset}")

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/health":
            self._json(self.api.health())


        elif path.startswith("/api/"):
            self._json(Reply(404, {"error": "No such endpoint."}))
        else:
            self._serve_asset(path)

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        body = self._read_json()
        if body == "too-large":
            self._json(Reply(413, {"error": "That request is too large."}))
            return
        if body is None:
            self._json(Reply(400, {"error": "That was not JSON."}))
            return
        if path == "/api/compare":
            self._json(self.api.compare(body))
        elif path == "/api/note":
            self._json(self.api.note(body))
        else:
            self._json(Reply(404, {"error": "No such endpoint."}))


def build_server(config: Config | None = None, *, api: RedlensAPI | None = None):
    settings = config or load_config()
    handler = type("BoundHandler", (Handler,), {
        "api": api or RedlensAPI(settings), "web_root": WEB_ROOT,
        # The transport cap is a backstop, not the user-facing limit. Base64
        # inflates a file by 4/3 and JSON adds a little more, so this sits
        # above the configured size — that way the API reports the limit in
        # megabytes instead of the socket layer refusing with a blunter
        # message.
        "max_body": settings.max_document_bytes * 3 + 65_536})
    server = ThreadingHTTPServer((settings.host, settings.port), handler)
    server.daemon_threads = True
    return server


def main() -> None:
    settings = load_config()
    server = build_server(settings)
    address = f"http://{settings.host}:{server.server_address[1]}"
    print(f"Redlens is running.\n  App:    {address}/\n"
          f"  Health: {address}/api/health\n"
          f"Both documents are read on this machine and never uploaded.\n"
          f"Neither is stored: nothing survives the request.\n"
          f"Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
