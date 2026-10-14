from http.server import ThreadingHTTPServer
from pathlib import Path
import importlib.util
import re
import threading
import unittest
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "outputs" / "site" / "server.py"
SPEC = importlib.util.spec_from_file_location("family_site_server_for_favicon", SERVER_PATH)
site_server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(site_server)


class FaviconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), site_server.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_homepage_declares_a_versioned_flower_favicon(self):
        html = (ROOT / "outputs" / "site" / "index.html").read_text(encoding="utf-8")
        self.assertRegex(html, r'<link[^>]+rel="icon"[^>]+href="/favicon\.svg\?v=[^"]+"')

    def test_favicon_route_serves_the_svg_file(self):
        with urlopen(f"{self.base_url}/favicon.svg?v=20261015-1") as response:
            body = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("image/svg+xml", response.headers["Content-Type"])
            self.assertIn("<svg", body)
            self.assertIn("<ellipse", body)


if __name__ == "__main__":
    unittest.main()

