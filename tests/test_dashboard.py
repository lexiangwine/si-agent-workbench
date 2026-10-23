from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest

from workbench.dashboard import make_handler
from workbench.engine import Engine

REPO = Path(__file__).resolve().parents[1]


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        for name in ("workflows", "agents", "workbench"):
            shutil.copytree(REPO / name, root / name)
        self.engine = Engine(root)
        self.engine.demo("demo")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.engine))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def get(self, path, headers=None, method="GET"):
        conn = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            conn.request(method, path, headers=headers or {})
            r = conn.getresponse()
            return r.status, dict(r.headers), r.read()
        finally:
            conn.close()

    def test_real_project_status_api(self):
        status, headers, data = self.get("/api/projects")
        self.assertEqual(200, status)
        self.assertEqual("demo_complete", json.loads(data)["projects"][0]["status"])
        self.assertEqual("no-store", headers["Cache-Control"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_preview_artifact(self):
        status, _, data = self.get("/api/artifact?project=demo&stage=requirements")
        self.assertEqual(200, status)
        self.assertIn("离线演示", json.loads(data)["text"])

    def test_reject_host_rebinding(self):
        self.assertEqual(403, self.get("/api/projects", {"Host":"attacker.example"})[0])

    def test_no_file_browsing_or_write_endpoint(self):
        self.assertEqual(404, self.get("/.env")[0])
        self.assertEqual(404, self.get("/../../README.md")[0])
        self.assertEqual(400, self.get("/api/artifact?project=../escape&stage=requirements")[0])
        self.assertEqual(501, self.get("/api/projects", method="POST")[0])

    def test_static_assets_and_csp(self):
        for path in ("/", "/app.js", "/style.css"):
            status, headers, body = self.get(path)
            self.assertEqual(200, status)
            self.assertTrue(body)
            self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])


if __name__ == "__main__":
    unittest.main()
