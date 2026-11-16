import io
import json
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageFont

GOOD = {"vendor": "Cafe", "date": "2026-01-02",
        "items": [{"name": "Latte", "qty": 2, "unit_price": 30000, "price": 60000},
                  {"name": "Cake", "qty": 1, "unit_price": 25000, "price": 25000}],
        "subtotal": 85000, "discount": None, "service": None, "tax": 8500, "total": 93500}


class FakeLLM:
    """Stands in for the Groq client: replies are scripted and every request is recorded."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        self.usage = SimpleNamespace(prompt_tokens=0, completion_tokens=0, requests=0)

    def chat(self, messages, tools=None, tool_choice=None, max_tokens=1024, temperature=0.0):
        self.requests.append(messages)
        reply = self.replies.pop(0)
        content = reply if isinstance(reply, str) else json.dumps(reply)
        self.usage.requests += 1
        self.usage.prompt_tokens += 100
        self.usage.completion_tokens += 50
        return {"message": {"role": "assistant", "content": content}, "model": "fake-vision", "cached": False, "usage": {}}


def receipt_png(lines, size=(640, 520)) -> bytes:
    """A plain synthetic receipt: black text on white, large enough for Tesseract."""
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=30)
    y = 20
    for line in lines:
        draw.text((24, y), line, fill="black", font=font)
        y += 46
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()
