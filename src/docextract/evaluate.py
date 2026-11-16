"""Scoring: field accuracy, item F1, and how well the review flag separates right from wrong documents."""
from __future__ import annotations

import math
import re
from difflib import SequenceMatcher

from .schema import Item, Receipt

FIELDS = ("total", "subtotal", "tax")


def money_equal(a: float | None, b: float | None) -> bool:
    return a is not None and b is not None and abs(a - b) <= 0.5


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def name_similar(a: str, b: str, threshold: float = 0.5) -> bool:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= threshold


def match_items(pred: list[Item], gold: list[Item]) -> tuple[int, int, int]:
    """Greedy one-to-one matching: same line price and a similar name. Returns (true positives, predicted, gold)."""
    free = list(range(len(pred)))
    tp = 0
    for g in gold:
        for j in free:
            p = pred[j]
            if money_equal(p.price, g.price) and name_similar(p.name, g.name):
                free.remove(j)
                tp += 1
                break
    return tp, len(pred), len(gold)


def score_doc(pred: Receipt, gold: Receipt) -> dict:
    """Per-document result. Field correctness is only scored where the label has the field."""
    fields = {f: money_equal(getattr(pred, f), getattr(gold, f)) for f in FIELDS if getattr(gold, f) is not None}
    tp, npred, ngold = match_items(pred.items, gold.items)
    return {"fields": fields, "items_tp": tp, "items_pred": npred, "items_gold": ngold,
            "all_fields": all(fields.values()) if fields else False}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval for a proportion; honest about how little 100 documents can say."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def summarize(rows: list[dict]) -> dict:
    """rows: [{'score': score_doc(...), 'flagged': bool, 'calls': int, 'prompt_tokens': int, ...}]"""
    n = len(rows)
    out: dict = {"documents": n}
    for f in FIELDS:
        have = [r for r in rows if f in r["score"]["fields"]]
        k = sum(r["score"]["fields"][f] for r in have)
        lo, hi = wilson(k, len(have))
        out[f] = {"correct": k, "of": len(have), "accuracy": k / len(have) if have else None, "ci95": [round(lo, 3), round(hi, 3)]}
    tp = sum(r["score"]["items_tp"] for r in rows)
    npred = sum(r["score"]["items_pred"] for r in rows)
    ngold = sum(r["score"]["items_gold"] for r in rows)
    prec = tp / npred if npred else 0.0
    rec = tp / ngold if ngold else 0.0
    out["items"] = {"precision": prec, "recall": rec, "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0}
    right = [r for r in rows if r["score"]["all_fields"]]
    k = len(right)
    lo, hi = wilson(k, n)
    out["all_fields_correct"] = {"correct": k, "of": n, "accuracy": k / n if n else None, "ci95": [round(lo, 3), round(hi, 3)]}

    flagged = [r for r in rows if r["flagged"]]
    clean = [r for r in rows if not r["flagged"]]
    wrong = [r for r in rows if not r["score"]["all_fields"]]
    out["review"] = {
        "flagged": len(flagged),
        "accuracy_when_not_flagged": (sum(r["score"]["all_fields"] for r in clean) / len(clean)) if clean else None,
        "accuracy_when_flagged": (sum(r["score"]["all_fields"] for r in flagged) / len(flagged)) if flagged else None,
        "wrong_documents_caught": (sum(r["flagged"] for r in wrong) / len(wrong)) if wrong else None,
    }
    out["cost"] = {"model_calls_per_doc": sum(r.get("calls", 0) for r in rows) / n if n else 0,
                   "tokens_per_doc": (sum(r.get("prompt_tokens", 0) + r.get("completion_tokens", 0) for r in rows) / n) if n else 0}
    return out
