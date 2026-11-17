"""Find out which Groq models this key can use for images. Model lists change, so check instead of assuming."""
from __future__ import annotations

import re

import requests

from .extract import data_url, prepare_image

SKIP = re.compile(r"whisper|tts|orpheus|guard|safeguard|embed|allam|compound|prompt-guard", re.I)


def _png() -> bytes:
    import io
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (480, 160), "white")
    ImageDraw.Draw(img).text((20, 50), "TOTAL 12345", fill="black", font=ImageFont.load_default(size=48))
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def probe(api_key: str | None) -> int:
    if not api_key:
        print("GROQ_API_KEY is not set")
        return 1
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=30)
    print(f"GET /models -> {r.status_code}")
    if r.status_code != 200:
        print(r.text[:300])
        return 1
    models = sorted(m["id"] for m in r.json().get("data", []))
    print("models:", ", ".join(models))
    url = data_url(prepare_image(_png()))
    ok = []
    for m in models:
        if SKIP.search(m):
            continue
        body = {"model": m, "max_completion_tokens": 200, "temperature": 0,
                "messages": [{"role": "user", "content": [{"type": "text", "text": "What number follows the word TOTAL in this image? Reply with the number only."},
                                                          {"type": "image_url", "image_url": {"url": url}}]}]}
        try:
            resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=body, timeout=90)
        except requests.RequestException as exc:
            print(f"{m}: network error {type(exc).__name__}")
            continue
        if resp.status_code == 200:
            text = (resp.json()["choices"][0]["message"].get("content") or "").strip().replace("\n", " ")[:80]
            read = "12345" in text.replace(",", "")
            print(f"{m}: 200 accepts images; answer={text!r} {'(read it correctly)' if read else '(did not read it)'}")
            if read:
                ok.append(m)
        else:
            print(f"{m}: {resp.status_code} {resp.text[:160]!r}")
    print("VISION-CAPABLE:", ", ".join(ok) or "none")
    return 0
