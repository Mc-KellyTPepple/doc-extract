"""Small HTTP service (standard library only) around the extractor.

  GET  /health    liveness
  POST /extract   {"image": "data:image/jpeg;base64,..."} -> receipt, issues, needs_review, model, seconds

It runs on a free host with a free Groq key, so it protects the quota: per-IP and daily limits, an image size limit,
and images are processed in memory only. Nothing uploaded is written to disk or logged.
"""
from __future__ import annotations

import base64
import binascii
import json
import os
import threading
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .extract import run_config
from .llm import LLM, LLMError, VISION_MODELS

ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")
MAX_IMAGE_BYTES = 2_500_000          # decoded image size
MAX_BODY_BYTES = 3_500_000           # base64 inflates by a third


class Limits:
    def __init__(self, per_ip_per_hour: int = 6, daily_cap: int = 120, clock=time.time):
        self.per_ip, self.daily_cap, self.clock = per_ip_per_hour, daily_cap, clock
        self.hits: dict[str, deque] = defaultdict(deque)
        self.day, self.count = "", 0
        self.lock = threading.Lock()

    def allow(self, ip: str) -> str | None:
        with self.lock:
            now = self.clock()
            today = time.strftime("%Y-%m-%d", time.gmtime(now))
            if today != self.day:
                self.day, self.count = today, 0
            if self.count >= self.daily_cap:
                return "The daily free quota for this demo is used up. Please try again tomorrow."
            q = self.hits[ip]
            while q and now - q[0] > 3600:
                q.popleft()
            if len(q) >= self.per_ip:
                return f"Rate limit: at most {self.per_ip} receipts per hour per visitor."
            q.append(now)
            self.count += 1
            return None


def decode_image(value: str) -> bytes:
    """Accepts a data URL or bare base64. Raises ValueError with a user-facing message."""
    if not isinstance(value, str) or not value:
        raise ValueError("Send a JSON body like {\"image\": \"data:image/jpeg;base64,...\"}.")
    if value.startswith("data:"):
        header, _, value = value.partition(",")
        if not header.startswith("data:image/"):
            raise ValueError("That file is not an image.")
    try:
        data = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("The image data could not be decoded.") from None
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(f"Image too large (max {MAX_IMAGE_BYTES // 1_000_000} MB).")
    try:   # reject non-images here, before the request spends any quota
        from PIL import Image
        import io
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
    except Exception:
        raise ValueError("That file could not be read as an image.") from None
    return data


class App:
    def __init__(self, llm: LLM, limits: Limits | None = None, runner=run_config):
        self.llm, self.runner = llm, runner
        self.limits = limits or Limits()
        self.lock = threading.Lock()   # one extraction at a time: the Groq rate limiter is shared

    def extract(self, image_field: str, ip: str) -> tuple[int, dict]:
        try:
            data = decode_image(image_field)
        except ValueError as exc:
            return 400, {"error": str(exc)}
        refused = self.limits.allow(ip)
        if refused:
            return 429, {"error": refused}
        t0 = time.monotonic()
        try:
            with self.lock:
                result = self.runner("verified", data, self.llm, None)
        except LLMError as exc:
            msg = ("The model provider is busy or out of free quota right now. Try again later."
                   if "quota" in str(exc).lower() or "budget" in str(exc).lower() else "The model provider returned an error. Try again.")
            return 503, {"error": msg}
        except OSError:
            return 400, {"error": "That file could not be read as an image."}
        except Exception as exc:   # Pillow decode errors, network failures: never leak internals
            print(f"extract failed: {type(exc).__name__}", flush=True)
            if type(exc).__name__ == "UnidentifiedImageError":
                return 400, {"error": "That file could not be read as an image."}
            return 502, {"error": "Could not reach the model provider. Try again later."}
        out = result.to_dict()
        out["seconds"] = round(time.monotonic() - t0, 1)
        return 200, out


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        def _cors(self) -> None:
            self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
            self.send_header("Vary", "Origin")

        def _json(self, code: int, obj: dict) -> None:
            body = json.dumps(obj, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):  # noqa: N802   CORS preflight
            self.send_response(204)
            self._cors()
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Max-Age", "86400")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):  # noqa: N802
            if self.path == "/health":
                self._json(200, {"ok": True})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):  # noqa: N802
            if self.path != "/extract":
                return self._json(404, {"error": "not found"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n > MAX_BODY_BYTES:
                    return self._json(413, {"error": "request too large"})
                data = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(data, dict):
                    raise ValueError
            except (ValueError, json.JSONDecodeError):
                return self._json(400, {"error": "Send a JSON body with an image field."})
            fwd = (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()   # behind a proxy (Render) the client is the first entry
            ip = fwd or self.client_address[0]
            code, obj = app.extract(data.get("image"), ip)
            self._json(code, obj)

        def log_message(self, *a):   # keep logs free of request details
            pass

    return Handler


def build_app(per_ip: int = 6, daily_cap: int = 120) -> App:
    llm = LLM(api_key=os.environ.get("GROQ_API_KEY"), models=VISION_MODELS,
              cache_dir=None, ledger_path=Path(os.environ.get("LEDGER_PATH", "/tmp/groq_ledger.json")))
    return App(llm, Limits(per_ip, daily_cap))


def serve(app: App, host: str = "0.0.0.0", port: int | None = None) -> None:
    port = port or int(os.environ.get("PORT", "7860"))
    print(f"listening on {host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), make_handler(app)).serve_forever()
