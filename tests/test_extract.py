import unittest

from docextract.extract import REPAIR, prepare_image, rules_extract, run_config
from tests.helpers import GOOD, FakeLLM, receipt_png


class Extraction(unittest.TestCase):
    def setUp(self):
        self.png = receipt_png(["CAFE", "Latte 2 x 30000", "TOTAL 93500"])

    def test_vision_single_call(self):
        llm = FakeLLM([GOOD])
        res = run_config("vision", self.png, llm)
        self.assertEqual((res.calls, res.receipt.total, res.needs_review), (1, 93500.0, False))
        content = llm.requests[0][1]["content"]
        self.assertEqual([p["type"] for p in content], ["text", "image_url"])
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))

    def test_amounts_printed_with_thousands_dots_are_read_at_the_right_scale(self):
        # the first benchmark run lost most of its accuracy to "60.000" being written as the JSON number 60.0
        reply = {"vendor": None, "date": None, "items": [{"name": "Tea", "qty": 2, "unit_price": "30.000", "price": "60.000"}],
                 "subtotal": "60.000", "discount": None, "service": None, "tax": None, "total": "60.000"}
        res = run_config("verified", self.png, FakeLLM([reply]))
        self.assertEqual((res.receipt.total, res.receipt.items[0].price, res.needs_review), (60000.0, 60000.0, False))

    def test_the_prompt_asks_for_amounts_as_printed_text(self):
        from docextract.extract import SYSTEM
        self.assertIn("exactly as it is printed", SYSTEM)
        self.assertIn('"60.000"', SYSTEM)

    def test_verified_skips_second_call_when_clean(self):
        llm = FakeLLM([GOOD])
        res = run_config("verified", self.png, llm)
        self.assertEqual((res.calls, res.repaired, res.needs_review), (1, False, False))

    def test_verified_repairs_a_misread_total(self):
        llm = FakeLLM([{**GOOD, "total": 98500}, GOOD])
        res = run_config("verified", self.png, llm)
        self.assertEqual((res.calls, res.repaired, res.receipt.total, res.needs_review), (2, True, 93500.0, False))
        repair_prompt = llm.requests[1][-1]["content"]
        self.assertIn("Automatic checks", repair_prompt)
        self.assertIn("total is 98500", repair_prompt)

    def test_verified_flags_when_repair_does_not_help(self):
        llm = FakeLLM([{**GOOD, "total": 98500}, {**GOOD, "total": 98500}])
        res = run_config("verified", self.png, llm)
        self.assertEqual((res.calls, res.needs_review), (2, True))

    def test_verified_keeps_first_reading_if_repair_is_worse(self):
        first = {**GOOD, "total": 98500}                     # 1 issue
        worse = {**GOOD, "total": 1, "subtotal": 5}          # more issues
        res = run_config("verified", self.png, FakeLLM([first, worse]))
        self.assertEqual(res.receipt.total, 98500.0)
        self.assertFalse(res.repaired)

    def test_unparseable_reply_is_flagged_not_trusted(self):
        res = run_config("vision", self.png, FakeLLM(["I cannot read this."]))
        self.assertTrue(res.needs_review)
        self.assertFalse(res.parsed)

    def test_ocr_llm_uses_text_model_and_ocr_text(self):
        text_llm = FakeLLM([GOOD])
        res = run_config("ocr_llm", self.png, None, text_llm)
        self.assertEqual(res.receipt.total, 93500.0)
        self.assertIn("OCR text", text_llm.requests[0][1]["content"])

    def test_ocr_rules_finds_total_from_a_rendered_receipt(self):
        res = run_config("ocr_rules", receipt_png(["CAFE LUNA", "Latte 30000", "Cake 25000", "Subtotal 55000", "Tax 5500", "TOTAL 60500"]), None)
        self.assertEqual(res.receipt.total, 60500.0)
        self.assertEqual(res.receipt.subtotal, 55000.0)
        self.assertEqual(res.calls, 0)

    def test_rules_extract_text(self):
        r = rules_extract("Item 1  5.000\nSub Total 5.000\nPPN 500\nGrand Total 5.500\nChange 4.500")
        self.assertEqual((r.subtotal, r.tax, r.total), (5000.0, 500.0, 5500.0))

    def test_unknown_config(self):
        with self.assertRaises(ValueError):
            run_config("nope", self.png, None)

    def test_prepare_image_shrinks_and_rejects_non_images(self):
        from PIL import Image
        import io
        big = io.BytesIO()
        Image.new("RGB", (4000, 3000), "white").save(big, "PNG")
        out = Image.open(io.BytesIO(prepare_image(big.getvalue())))
        self.assertEqual(max(out.size), 1600)
        with self.assertRaises(Exception):
            prepare_image(b"not an image")
        self.assertIn("{issues}", REPAIR)


if __name__ == "__main__":
    unittest.main()
