import unittest

from docextract.schema import Item, Receipt, extract_json, parse_money, receipt_from_dict
from docextract.validate import validate
from tests.helpers import GOOD


class MoneyAndJson(unittest.TestCase):
    def test_parse_money(self):
        cases = {"Rp 1.234.500": 1234500, "1,234,500": 1234500, "$1,234.50": 1234.5, "12,50": 12.5, "45.000": 45000,
                 "(3.00)": -3.0, "-2.5": -2.5, "7": 7, 7: 7.0, 3.5: 3.5}
        for raw, want in cases.items():
            self.assertAlmostEqual(parse_money(raw), want, msg=repr(raw))
        for raw in (None, "", "n/a", True):
            self.assertIsNone(parse_money(raw), msg=repr(raw))

    def test_extract_json_variants(self):
        self.assertEqual(extract_json('{"a": 1}'), {"a": 1})
        self.assertEqual(extract_json('Sure!\n```json\n{"a": {"b": 2}}\n```\nDone'), {"a": {"b": 2}})
        self.assertEqual(extract_json('<think>{"x":0}</think> {"a": 3} trailing'), {"a": 3})
        self.assertIsNone(extract_json("no json here"))
        self.assertIsNone(extract_json('{"broken": '))

    def test_receipt_from_dict_coerces_and_ignores_junk(self):
        r = receipt_from_dict({"items": [{"name": "x", "price": "1.500"}, "junk", {"name": None}], "total": "Rp 2.000", "tax": "abc"})
        self.assertEqual([i.price for i in r.items], [1500.0, None])
        self.assertEqual(r.total, 2000.0)
        self.assertIsNone(r.tax)
        self.assertEqual(receipt_from_dict(None).items, [])


class Validator(unittest.TestCase):
    def test_consistent_receipt_has_no_issues(self):
        self.assertEqual(validate(receipt_from_dict(GOOD)), [])

    def test_misread_total_is_flagged(self):
        bad = {**GOOD, "total": 93000}
        codes = [i.code for i in validate(receipt_from_dict(bad))]
        self.assertEqual(codes, ["total_composition"])

    def test_items_not_matching_subtotal(self):
        bad = {**GOOD, "items": [{"name": "Latte", "price": 60000}, {"name": "Cake", "price": 20000}]}
        self.assertIn("items_vs_subtotal", [i.code for i in validate(receipt_from_dict(bad))])

    def test_tax_already_included_is_accepted(self):
        r = receipt_from_dict({**GOOD, "total": 85000})
        self.assertEqual(validate(r), [])

    def test_discount_service_and_rounding(self):
        r = Receipt(items=[Item("a", price=100.0), Item("b", price=50.0)], subtotal=150.0, discount=-10.0, service=7.0, tax=14.0, total=161.0)
        self.assertEqual(validate(r), [])
        r.total = 161.1   # within rounding
        self.assertEqual(validate(r), [])
        r.total = 171.0
        self.assertTrue(validate(r))

    def test_line_math(self):
        r = Receipt(items=[Item("a", qty=3, unit_price=10.0, price=40.0)], total=40.0)
        self.assertEqual([i.code for i in validate(r)], ["line_math"])

    def test_missing_and_bad_total(self):
        self.assertEqual([i.code for i in validate(Receipt())], ["missing_total"])
        self.assertEqual([i.code for i in validate(Receipt(total=-5.0))], ["bad_total"])


if __name__ == "__main__":
    unittest.main()
