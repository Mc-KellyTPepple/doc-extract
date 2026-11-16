"""Arithmetic checks on an extracted receipt.

A receipt carries redundancy: line prices add up to the subtotal, and the subtotal plus tax and service minus any
discount gives the total. When an extraction breaks that, a number was misread, so the document is flagged for review
instead of being trusted. The checks allow for the usual real-world variation (tax already included in the price,
small rounding), because a validator that cries wolf is as useless as one that never speaks.
"""
from __future__ import annotations

from dataclasses import dataclass

from .schema import Receipt


@dataclass
class Issue:
    code: str
    message: str
    fields: list[str]


def _tol(*amounts: float | None) -> float:
    """Allowed difference: 0.2% of the larger amount, never less than one cent."""
    return max(0.011, 0.002 * max((abs(a) for a in amounts if a is not None), default=0))


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= _tol(a, b)


def validate(r: Receipt) -> list[Issue]:
    issues: list[Issue] = []
    if r.total is None:
        issues.append(Issue("missing_total", "No total was found.", ["total"]))
    elif r.total <= 0:
        issues.append(Issue("bad_total", f"The total ({r.total:g}) is not a positive amount.", ["total"]))

    priced = [i for i in r.items if i.price is not None]
    items_sum = sum(i.price for i in priced) if priced else None

    for i in r.items:   # a line's price should equal quantity x unit price
        if i.qty and i.unit_price and i.price is not None and not _close(i.qty * i.unit_price, i.price):
            issues.append(Issue("line_math", f"'{i.name}': {i.qty:g} x {i.unit_price:g} is {i.qty * i.unit_price:g}, but the line says {i.price:g}.", ["items"]))

    discount = r.discount or 0.0
    service = r.service or 0.0
    tax = r.tax or 0.0

    if items_sum is not None and r.subtotal is not None:
        if not (_close(items_sum, r.subtotal) or _close(items_sum - abs(discount), r.subtotal)):
            issues.append(Issue("items_vs_subtotal", f"The line items add up to {items_sum:g} but the subtotal is {r.subtotal:g}.", ["items", "subtotal"]))

    base = r.subtotal if r.subtotal is not None else items_sum
    if base is not None and r.total is not None and r.total > 0:
        net = base - abs(discount)
        accepted = (net + tax + service, net + service, net + tax, net)   # tax may already be inside the prices
        if not any(_close(r.total, a) for a in accepted):
            issues.append(Issue("total_composition", f"Subtotal {base:g} with tax {tax:g}, service {service:g} and discount {abs(discount):g} gives {net + tax + service:g}, but the total is {r.total:g}.", ["total", "subtotal", "tax"]))
    return issues
