"""Four ways to turn a receipt image into structured data.

  ocr_rules  Tesseract text + keyword rules. No model. Finds total, subtotal and tax only. The floor to beat.
  ocr_llm    Tesseract text, then a text model writes the JSON. The classic two-stage pipeline.
  vision     A vision model reads the image and writes the JSON in one call.
  verified   vision, then the arithmetic validator; if the numbers do not add up, the model is shown which checks
             failed and re-reads the image once. Whatever still fails is flagged for human review.
"""
from __future__ import annotations

import base64
import io
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .llm import LLM
from .schema import Receipt, extract_json, parse_money, receipt_from_dict
from .validate import Issue, validate

CONFIGS = ("ocr_rules", "ocr_llm", "vision", "verified")
MAX_SIDE, JPEG_QUALITY = 1600, 85

SYSTEM = """You read receipts and invoices and return their contents as one JSON object, and nothing else.

Schema (every amount is a STRING copied exactly as printed; qty is a number):
{"vendor": string|null, "date": string|null,
 "items": [{"name": string, "qty": number|null, "unit_price": string|null, "price": string|null}],
 "subtotal": string|null, "discount": string|null, "service": string|null, "tax": string|null, "total": string|null}

Rules:
- Copy what is printed. Never calculate a missing value and never invent one: use null when a field is not on the document.
- Write each amount as a string exactly as it is printed, keeping its dots and commas but dropping the currency symbol: "60.000", "1,234.50", "12,50", "-2.62". Never convert an amount to a number yourself; in many currencies "60.000" means sixty thousand, and writing it as a number would turn it into 60.
- "price" on an item is the line total as printed (quantity times unit price). "total" is the final amount due.
- "subtotal" is the amount before tax and service. "tax" is tax only; put service charges in "service".
- Put each purchased line in "items" once, in the order printed. Skip payment lines (cash, change, card)."""

REPAIR = """Automatic checks on your answer failed:
{issues}

Look at the image again. If you misread a number, return the corrected JSON. If the receipt really is printed that way, return the same JSON unchanged. Return only the JSON object."""


@dataclass
class Result:
    receipt: Receipt
    issues: list[Issue] = field(default_factory=list)
    calls: int = 0
    model: str = ""
    repaired: bool = False
    parsed: bool = True           # False when the model's reply held no usable JSON

    @property
    def needs_review(self) -> bool:
        return bool(self.issues) or not self.parsed

    def to_dict(self) -> dict:
        return {"receipt": self.receipt.to_dict(), "issues": [i.__dict__ for i in self.issues],
                "needs_review": self.needs_review, "calls": self.calls, "model": self.model,
                "repaired": self.repaired, "parsed": self.parsed}


# ---- image handling --------------------------------------------------------------------------------------------
def prepare_image(data: bytes) -> bytes:
    """Re-encode as a JPEG no larger than MAX_SIDE on its long edge (keeps requests small and strips metadata)."""
    from PIL import Image, ImageOps
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    img = img.convert("RGB")
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=JPEG_QUALITY)
    return out.getvalue()


def data_url(jpeg: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()


# ---- OCR ------------------------------------------------------------------------------------------------------
def ocr_text(jpeg: bytes) -> str:
    if not shutil.which("tesseract"):
        raise RuntimeError("tesseract is not installed")
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "in.jpg"
        src.write_bytes(jpeg)
        proc = subprocess.run(["tesseract", str(src), "-", "--psm", "6"], capture_output=True, text=True, timeout=60)
    return proc.stdout


_AMOUNT = re.compile(r"-?\(?\d[\d.,]*\d\)?|\d")


def _line_amount(line: str) -> float | None:
    found = _AMOUNT.findall(line)
    return parse_money(found[-1]) if found else None


def rules_extract(text: str) -> Receipt:
    """Keyword rules over OCR text. Deliberately simple: this is the baseline, not the product."""
    total = subtotal = tax = None
    for line in text.splitlines():
        low = line.lower()
        amount = _line_amount(line)
        if amount is None:
            continue
        if re.search(r"sub\s*-?\s*total|subtotal", low):
            subtotal = subtotal if subtotal is not None else amount
        elif re.search(r"\b(tax|ppn|pb1|vat|gst)\b", low):
            tax = tax if tax is not None else amount
        elif re.search(r"\b(grand\s*total|total|amount due|jumlah)\b", low) and not re.search(r"qty|item|change|kembali", low):
            total = amount if total is None or "grand" in low else total
    return Receipt(subtotal=subtotal, tax=tax, total=total)


# ---- model calls ----------------------------------------------------------------------------------------------
def _reply(llm: LLM, messages: list, max_tokens: int = 1500):
    out = llm.chat(messages, max_tokens=max_tokens)
    return out["message"].get("content") or "", out["model"]


def _vision_messages(jpeg: bytes) -> list:
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": [{"type": "text", "text": "Extract this receipt."},
                                         {"type": "image_url", "image_url": {"url": data_url(jpeg)}}]}]


def run_config(config: str, image: bytes, vision_llm: LLM | None, text_llm: LLM | None = None) -> Result:
    if config not in CONFIGS:
        raise ValueError(f"unknown config {config!r}; choose from {', '.join(CONFIGS)}")
    jpeg = prepare_image(image)

    if config == "ocr_rules":
        receipt = rules_extract(ocr_text(jpeg))
        return Result(receipt, validate(receipt), calls=0, model="tesseract")

    if config == "ocr_llm":
        text = ocr_text(jpeg)
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": "Extract this receipt from its OCR text (it may contain recognition errors):\n\n" + text[:6000]}]
        reply, model = _reply(text_llm, messages)
        obj = extract_json(reply)
        receipt = receipt_from_dict(obj)
        return Result(receipt, validate(receipt), calls=1, model=model, parsed=obj is not None)

    messages = _vision_messages(jpeg)
    reply, model = _reply(vision_llm, messages)
    obj = extract_json(reply)
    receipt = receipt_from_dict(obj)
    result = Result(receipt, validate(receipt), calls=1, model=model, parsed=obj is not None)
    if config == "vision" or (result.parsed and not result.issues):
        return result

    # verified: one repair round, only when something failed
    problems = "\n".join(f"- {i.message}" for i in result.issues) or "- Your reply did not contain a valid JSON object."
    messages += [{"role": "assistant", "content": reply}, {"role": "user", "content": REPAIR.format(issues=problems)}]
    reply2, model2 = _reply(vision_llm, messages)
    obj2 = extract_json(reply2)
    if obj2 is not None:
        receipt2 = receipt_from_dict(obj2)
        issues2 = validate(receipt2)
        # keep the second reading unless it is worse than the first
        if not result.parsed or len(issues2) <= len(result.issues):
            return Result(receipt2, issues2, calls=2, model=model2, repaired=True, parsed=True)
    return Result(receipt, result.issues, calls=2, model=model, repaired=False, parsed=result.parsed)
