"""Read-only loopback dashboard. No model calls, writes, or filesystem browsing."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import parse_qs, urlsplit

from .storage import WorkbenchError, read_text


def make_handler(engine):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # Avoid logging untrusted request URLs or project names.
            pass

        def reply(self, code, value, content_type="application/json; charset=utf-8"):
            data = value.encode("utf-8") if isinstance(value, str) else json.dumps(value, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            port = self.server.server_address[1]
            if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
                self.reply(403, {"error": "本地访问主机不被允许"})
                return
            route = urlsplit(self.path)
            try:
                assets = {"/": ("dashboard.html", "text/html; charset=utf-8"),
                          "/app.js": ("dashboard.js", "text/javascript; charset=utf-8"),
                          "/style.css": ("dashboard.css", "text/css; charset=utf-8")}
                if route.path in assets:
                    filename, content_type = assets[route.path]
                    self.reply(200, read_text(engine.root / "workbench" / filename), content_type)
                elif route.path == "/api/projects":
                    values = []
                    for name in engine.store.names():
                        try:
                            values.append(engine.status(name))
                        except (WorkbenchError, OSError, KeyError, TypeError):
                            values.append({"name": name, "status": "invalid", "mode": "unknown", "stages": []})
                    self.reply(200, {"projects": values})
                elif route.path == "/api/artifact":
                    args = parse_qs(route.query)
                    name, sid = args.get("project", [""])[0], args.get("stage", [""])[0]
                    engine.stage(name, sid)
                    self.reply(200, {"text": read_text(engine.artifact_path(name, sid), 150_000)})
                else:
                    self.reply(404, {"error": "页面不存在"})
            except (WorkbenchError, OSError, KeyError, TypeError, ValueError):
                self.reply(400, {"error": "项目或交付物不可用，请在终端检查。"})

    return Handler


def serve(engine, port=8765):
    if not 0 <= port <= 65535:
        raise WorkbenchError("端口范围应为0—65535。")
    with ThreadingHTTPServer(("127.0.0.1", port), make_handler(engine)) as server:
        actual = server.server_address[1]
        print(f"SI Agent Workbench: http://127.0.0.1:{actual} （只读，Ctrl+C停止）", flush=True)
        server.serve_forever()
