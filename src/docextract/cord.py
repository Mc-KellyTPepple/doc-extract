"""Loader for CORD v2 (naver-clova-ix/cord-v2 on Hugging Face, CC BY 4.0): photographed receipts with field labels.

CORD's `ground_truth` JSON has a `gt_parse` with `menu` (items, sometimes a single dict, sometimes with nested `sub`
modifier lines), `sub_total` and `total`. We map it onto our Receipt so predictions and labels are compared on the
same fields. Amounts in CORD are Indonesian rupiah, printed with thousands separators and no decimals.
"""
from __future__ import annotations

import io
import json
import random
from pathlib import Path

from .schema import Item, Receipt, parse_money

DATASET = "naver-clova-ix/cord-v2"


def _as_list(x) -> list:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def gt_to_receipt(gt_parse: dict) -> Receipt:
    items: list[Item] = []

    def add(entry: dict) -> None:
        if not isinstance(entry, dict):
            return
        name = str(entry.get("nm") or "").strip()
        price = parse_money(entry.get("price"))
        if name or price is not None:
            items.append(Item(name=name, qty=parse_money(entry.get("cnt")), unit_price=parse_money(entry.get("unitprice")), price=price))
        for sub in _as_list(entry.get("sub")):
            add(sub)

    for entry in _as_list(gt_parse.get("menu")):
        add(entry)
    sub = gt_parse.get("sub_total") or {}
    tot = gt_parse.get("total") or {}
    return Receipt(
        items=items,
        subtotal=parse_money(sub.get("subtotal_price")),
        discount=parse_money(sub.get("discount_price")),
        service=parse_money(sub.get("service_price")),
        tax=parse_money(sub.get("tax_price")),
        total=parse_money(tot.get("total_price")),
    )


def load_sample(n: int, seed: int, cache_dir: Path, split: str = "test") -> list[dict]:
    """Return n documents as [{"id": "cord-test-0017", "image": <jpeg path>, "gold": Receipt}], chosen with a fixed seed.

    Needs the `datasets` package and network access (the GitHub Actions runner has both). Images are cached on disk.
    """
    from datasets import load_dataset   # imported here so the rest of the package needs no heavy dependency

    ds = load_dataset(DATASET, split=split)
    idx = sorted(random.Random(seed).sample(range(len(ds)), min(n, len(ds))))
    cache_dir.mkdir(parents=True, exist_ok=True)
    docs = []
    for i in idx:
        row = ds[i]
        path = cache_dir / f"{split}-{i:04d}.jpg"
        if not path.exists():
            buf = io.BytesIO()
            row["image"].convert("RGB").save(buf, "JPEG", quality=92)
            path.write_bytes(buf.getvalue())
        gt = json.loads(row["ground_truth"])["gt_parse"]
        docs.append({"id": f"cord-{split}-{i:04d}", "image": path, "gold": gt_to_receipt(gt)})
    return docs
