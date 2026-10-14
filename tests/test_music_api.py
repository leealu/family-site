import hashlib
import hmac
import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import unittest
from urllib.parse import parse_qs, urlparse


SERVER_PATH = Path(__file__).resolve().parents[1] / "outputs" / "site" / "server.py"
SPEC = importlib.util.spec_from_file_location("family_site_server", SERVER_PATH)
site_server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(site_server)


class MetingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        self.server.requests.append(query)
        if query.get("type") == ["search"]:
            cover_endpoint = f"http://127.0.0.1:{self.server.server_port}/api?server=netease&type=pic&id=album-cover&auth=temporary-signature"
            body = json.dumps([{
                "title": "小星星",
                "author": "测试歌手",
                "album": "测试专辑",
                "url": "https://music.example.invalid/api?server=netease&type=url&id=123456&auth=temporary-signature",
                "pic": cover_endpoint,
                "lrc": "https://music.example.invalid/api?server=netease&type=lrc&id=123456&auth=temporary-signature",
            }], ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif query.get("type") == ["url"]:
            self.send_response(302)
            self.send_header("Location", "https://cdn.example.invalid/song.mp3")
            self.end_headers()
        elif query.get("type") == ["pic"]:
            self.send_response(302)
            self.send_header("Location", "https://cdn.example.invalid/cover.jpg")
            self.end_headers()
        elif query.get("type") == ["song"]:
            body = json.dumps([{
                "id": "123456",
                "title": "小星星",
                "pic": f"http://127.0.0.1:{self.server.server_port}/api?server=netease&type=pic&id=album-cover&auth=temporary-signature",
            }], ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(400)

    def log_message(self, *_args):
        pass


class MusicApiCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MetingHandler)
        cls.server.requests = []
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.source = {
            "id": "a" * 32,
            "name": "测试音源",
            "baseUrl": f"http://127.0.0.1:{cls.server.server_port}/api",
            "platform": "netease",
            "apiKey": "test-shared-secret",
            "authMode": "meting-hmac",
            "enabled": True,
        }

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        self.server.requests.clear()

    def test_search_maps_meting_results_without_exposing_shared_secret(self):
        results = site_server.search_music_source(self.source, "小星星")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["itemId"], "123456")
        self.assertEqual(results[0]["title"], "小星星")
        self.assertEqual(results[0]["durationSeconds"], 0)
        self.assertNotIn("token", self.server.requests[0])

    def test_search_resolves_internal_meting_cover_endpoint_for_browser(self):
        results = site_server.search_music_source(self.source, "小星星")
        self.assertEqual(results[0]["coverUrl"], "https://cdn.example.invalid/cover.jpg")
        self.assertEqual(self.server.requests[1]["type"], ["pic"])
        self.assertEqual(self.server.requests[1]["id"], ["album-cover"])
        expected = hmac.new(
            self.source["apiKey"].encode(),
            b"neteasepicalbum-cover",
            hashlib.sha1,
        ).hexdigest()
        self.assertEqual(self.server.requests[1]["token"], [expected])

    def test_saved_track_without_cover_can_resolve_cover_from_song_details(self):
        cover = site_server.resolve_saved_music_cover(self.source, {"itemId":"123456"})
        self.assertEqual(cover, "https://cdn.example.invalid/cover.jpg")
        self.assertEqual(self.server.requests[0]["type"], ["song"])
        self.assertEqual(self.server.requests[1]["type"], ["pic"])

    def test_playback_signs_request_and_uses_redirect_location(self):
        media_url = site_server.resolve_music_url(self.source, "123456")
        expected = hmac.new(
            self.source["apiKey"].encode(),
            b"neteaseurl123456",
            hashlib.sha1,
        ).hexdigest()
        self.assertEqual(self.server.requests[0]["token"], [expected])
        self.assertEqual(media_url, "https://cdn.example.invalid/song.mp3")

    def test_legacy_token_mode_keeps_static_token_behavior(self):
        source = {**self.source, "authMode": "token"}
        site_server.search_music_source(source, "小星星")
        self.assertEqual(self.server.requests[0]["token"], [source["apiKey"]])

    def test_hmac_mode_requires_a_shared_secret(self):
        source = {**self.source, "id": "b" * 32, "apiKey": ""}
        with self.assertRaisesRegex(ValueError, "服务密钥"):
            site_server.sanitize_music_sources([source])


if __name__ == "__main__":
    unittest.main()


