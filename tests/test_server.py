import base64
import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from docextract.extract import Result
from docextract.llm import LLMError
from docextract.schema import receipt_from_dict
from docextract.server import App, Limits, decode_image, make_handler
from tests.helpers import GOOD, receipt_png


def data_url(b: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(b).decode()


class Decode(unittest.TestCase):
    def test_decode(self):
        png = receipt_png(["x"])
        self.assertEqual(decode_image(data_url(png)), png)
        self.assertEqual(decode_image(base64.b64encode(png).decode()), png)
        for bad in ("", None, "data:text/plain;base64,aGk=", "data:image/png;base64,@@@"):
            with self.assertRaises(ValueError):
                decode_image(bad)
        with self.assertRaises(ValueError):
            decode_image(base64.b64encode(b"0" * 2_600_000).decode())


class AppLogic(unittest.TestCase):
    def runner(self, config, data, llm, text_llm):
        return Result(receipt_from_dict(GOOD), [], calls=1, model="m")

    def test_success_and_limits(self):
        app = App(None, Limits(per_ip_per_hour=2, daily_cap=3), runner=self.runner)
        img = data_url(receipt_png(["x"]))
        code, out = app.extract(img, "1.1.1.1")
        self.assertEqual((code, out["receipt"]["total"], out["needs_review"]), (200, 93500.0, False))
        self.assertEqual(app.extract(img, "1.1.1.1")[0], 200)
        self.assertEqual(app.extract(img, "1.1.1.1")[0], 429)           # per-IP
        self.assertEqual(app.extract(img, "2.2.2.2")[0], 200)
        code, out = app.extract(img, "3.3.3.3")
        self.assertEqual(code, 429)                                       # daily cap
        self.assertIn("daily", out["error"])

    def test_bad_input_costs_no_quota(self):
        app = App(None, Limits(per_ip_per_hour=1, daily_cap=1), runner=self.runner)
        self.assertEqual(app.extract("nonsense", "9.9.9.9")[0], 400)
        self.assertEqual(app.extract(data_url(receipt_png(["x"])), "9.9.9.9")[0], 200)

    def test_provider_errors_are_friendly(self):
        def quota(*a):
            raise LLMError("every model in the chain is out of quota for today")
        def boom(*a):
            raise RuntimeError("secret details")
        img = data_url(receipt_png(["x"]))
        code, out = App(None, runner=quota).extract(img, "a")
        self.assertEqual(code, 503)
        code, out = App(None, runner=boom).extract(img, "b")
        self.assertEqual(code, 502)
        self.assertNotIn("secret", json.dumps(out))

    def test_without_a_model_key_the_app_reports_not_configured(self):
        from docextract.extract import run_config
        code, out = App(None, runner=run_config).extract(data_url(receipt_png(["x"])), "d")
        self.assertEqual(code, 503)
        self.assertIn("not configured", out["error"])

    def test_non_image_bytes_are_a_400(self):
        from docextract.extract import run_config
        app = App(None, runner=run_config)
        code, out = app.extract("data:image/png;base64," + base64.b64encode(b"not an image at all").decode(), "c")
        self.assertEqual(code, 400)


class Http(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runner = lambda *a: Result(receipt_from_dict(GOOD), [], calls=1, model="m")  # noqa: E731
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(App(None, runner=runner)))
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def call(self, method, path, body=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read() or b"{}"), r.headers
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}"), e.headers

    def test_endpoints(self):
        self.assertEqual(self.call("GET", "/health")[:2], (200, {"ok": True}))
        self.assertEqual(self.call("GET", "/nope")[0], 404)
        code, out, headers = self.call("POST", "/extract", {"image": data_url(receipt_png(["x"]))})
        self.assertEqual((code, out["receipt"]["total"]), (200, 93500.0))
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(self.call("POST", "/extract", {"image": 5})[0], 400)
        self.assertEqual(self.call("POST", "/other", {})[0], 404)
        self.assertEqual(self.call("OPTIONS", "/extract")[0], 204)


if __name__ == "__main__":
    unittest.main()
