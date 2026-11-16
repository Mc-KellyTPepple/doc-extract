"""The receipt data model, and tolerant parsing of money amounts and model JSON."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


@dataclass
class Item:
    name: str = ""
    qty: float | None = None
    unit_price: float | None = None
    price: float | None = None          # the line total as printed


@dataclass
class Receipt:
    items: list[Item] = field(default_factory=list)
    subtotal: float | None = None
    discount: float | None = None
    service: float | None = None
    tax: float | None = None
    total: float | None = None
    vendor: str | None = None
    date: str | None = None

    def to_dict(self) -> dict:
        return {
            "vendor": self.vendor, "date": self.date,
            "items": [{"name": i.name, "qty": i.qty, "unit_price": i.unit_price, "price": i.price} for i in self.items],
            "subtotal": self.subtotal, "discount": self.discount, "service": self.service, "tax": self.tax, "total": self.total,
        }


def parse_money(value) -> float | None:
    """'Rp 1.234.500' -> 1234500.0, '$1,234.50' -> 1234.5, '12,50' -> 12.5, '(3.00)' -> -3.0, None -> None.

    A separator followed by exactly three digits is a thousands separator; one or two digits is a decimal part.
    The ambiguous '1.234' is read as 1234, which is right for the integer currencies in the CORD data.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    negative = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = re.sub(r"[^\d.,]", "", s)
    if not re.search(r"\d", s):
        return None
    last = max(s.rfind("."), s.rfind(","))
    if last == -1:
        number = s
    else:
        head, frac = s[:last], s[last + 1:]
        head = re.sub(r"[.,]", "", head)
        number = f"{head}.{frac}" if 1 <= len(frac) <= 2 else head + frac
    try:
        out = float(number)
    except ValueError:
        return None
    return -out if negative else out


def extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of a model reply (handles code fences and chatter around it)."""
    if not text:
        return None
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidates = [fenced.group(1)] if fenced else []
    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start:i + 1])
                    break
    for c in candidates:
        try:
            obj = json.loads(c)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def receipt_from_dict(d: dict | None) -> Receipt:
    """Build a Receipt from a model's JSON, coercing every amount with parse_money and ignoring junk."""
    d = d or {}
    items = []
    for raw in d.get("items") or []:
        if not isinstance(raw, dict):
            continue
        items.append(Item(
            name=str(raw.get("name") or "").strip(),
            qty=parse_money(raw.get("qty")),
            unit_price=parse_money(raw.get("unit_price")),
            price=parse_money(raw.get("price")),
        ))
    text = lambda k: (str(d[k]).strip() or None) if d.get(k) is not None else None  # noqa: E731
    return Receipt(
        items=items,
        subtotal=parse_money(d.get("subtotal")), discount=parse_money(d.get("discount")),
        service=parse_money(d.get("service")), tax=parse_money(d.get("tax")), total=parse_money(d.get("total")),
        vendor=text("vendor"), date=text("date"),
    )
