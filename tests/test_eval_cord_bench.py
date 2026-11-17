import json
import tempfile
import unittest
from pathlib import Path

from docextract.bench import build_report, run_bench
from docextract.cord import gt_to_receipt
from docextract.evaluate import match_items, money_equal, name_similar, score_doc, summarize, wilson
from docextract.llm import BudgetExhausted
from docextract.schema import Item, Receipt, receipt_from_dict
from tests.helpers import GOOD, FakeLLM, receipt_png


class Scoring(unittest.TestCase):
    def test_money_and_names(self):
        self.assertTrue(money_equal(100.0, 100.4))
        self.assertFalse(money_equal(100.0, 101.0))
        self.assertFalse(money_equal(None, 5.0))
        self.assertTrue(name_similar("Ice Lemon Tea", "ICE LEMON TEA"))
        self.assertFalse(name_similar("Latte", "Fried rice"))

    def test_item_matching_is_one_to_one(self):
        gold = [Item("Tea", price=5.0), Item("Tea", price=5.0)]
        pred = [Item("tea", price=5.0)]
        self.assertEqual(match_items(pred, gold), (1, 1, 2))

    def test_score_doc_only_scores_labelled_fields(self):
        gold = receipt_from_dict({**GOOD, "tax": None})
        pred = receipt_from_dict({**GOOD, "total": 1})
        s = score_doc(pred, gold)
        self.assertEqual(s["fields"], {"total": False, "subtotal": True})
        self.assertFalse(s["all_fields"])

    def test_wilson_interval_brackets_the_estimate(self):
        lo, hi = wilson(80, 100)
        self.assertLess(lo, 0.8)
        self.assertGreater(hi, 0.8)
        self.assertEqual(wilson(0, 0), (0.0, 0.0))

    def test_summary_review_numbers(self):
        def row(correct, flagged):
            gold = receipt_from_dict(GOOD)
            pred = receipt_from_dict(GOOD if correct else {**GOOD, "total": 1})
            return {"score": score_doc(pred, gold), "flagged": flagged, "calls": 1, "prompt_tokens": 10, "completion_tokens": 5}
        rows = [row(True, False), row(True, False), row(False, True), row(False, False)]
        s = summarize(rows)
        self.assertEqual(s["all_fields_correct"]["correct"], 2)
        self.assertAlmostEqual(s["review"]["accuracy_when_not_flagged"], 2 / 3)
        self.assertEqual(s["review"]["accuracy_when_flagged"], 0.0)
        self.assertAlmostEqual(s["review"]["wrong_documents_caught"], 0.5)
        self.assertEqual(s["cost"]["tokens_per_doc"], 15)


class Cord(unittest.TestCase):
    def test_gt_parse_list_dict_and_sub_items(self):
        gt = {"menu": [{"nm": "ICE TEA", "cnt": "2", "unitprice": "5.000", "price": "10.000", "sub": {"nm": "SUGAR", "price": "1.000"}},
                       {"nm": "RICE", "price": "15,000"}],
              "sub_total": {"subtotal_price": "26.000", "tax_price": "2.600", "discount_price": "-1.000"},
              "total": {"total_price": "27.600"}}
        r = gt_to_receipt(gt)
        self.assertEqual([(i.name, i.price) for i in r.items], [("ICE TEA", 10000.0), ("SUGAR", 1000.0), ("RICE", 15000.0)])
        self.assertEqual((r.subtotal, r.tax, r.discount, r.total), (26000.0, 2600.0, -1000.0, 27600.0))
        single = gt_to_receipt({"menu": {"nm": "X", "price": "3.000"}, "total": {"total_price": "3.000"}})
        self.assertEqual(len(single.items), 1)
        self.assertEqual(gt_to_receipt({}).total, None)


class Bench(unittest.TestCase):
    def make_docs(self, d: Path, n: int):
        docs = []
        for i in range(n):
            p = d / f"{i}.png"
            p.write_bytes(receipt_png([f"DOC {i}"]))
            docs.append({"id": f"doc-{i}", "image": p, "gold": receipt_from_dict(GOOD)})
        return docs

    def test_run_is_resumable_and_report_is_written(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            docs = self.make_docs(t, 3)
            out = t / "out"
            llm = FakeLLM([GOOD, {**GOOD, "total": 98500}, GOOD, GOOD])   # doc1 needs a repair (2 calls)
            done = run_bench(docs, ["verified"], llm, None, out, log=lambda *_: None)
            self.assertEqual(done, {"verified": 3})
            rows = [json.loads(x) for x in (out / "verified.jsonl").read_text().splitlines()]
            self.assertEqual([r["calls"] for r in rows], [1, 2, 1])
            self.assertEqual(rows[1]["prompt_tokens"], 200)
            # a second run does nothing: no replies are left to consume, so any call would fail
            run_bench(docs, ["verified"], FakeLLM([]), None, out, log=lambda *_: None)
            summary = build_report(out)
            m = summary["configs"]["verified"]
            self.assertEqual(summary["documents_scored"], 3)
            self.assertEqual(m["all_fields_correct"]["correct"], 3)
            self.assertIn("| verified |", (out / "results.md").read_text())
            self.assertTrue((out / "failures.md").exists())

    def test_quota_exhaustion_stops_cleanly_and_keeps_progress(self):
        class Dies(FakeLLM):
            def chat(self, *a, **k):
                if not self.replies:
                    raise BudgetExhausted("out of quota")
                return super().chat(*a, **k)
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            docs = self.make_docs(t, 3)
            done = run_bench(docs, ["vision"], Dies([GOOD]), None, t / "out", log=lambda *_: None)
            self.assertEqual(done, {"vision": 1})

    def test_a_document_needing_new_calls_does_not_block_cached_ones_behind_it(self):
        # verified reuses vision's cached first reading, but a repair is a new call. Out of quota, doc 0 needs a
        # repair and must be skipped, while docs 1 and 2 (clean, answered from the cache) must still finish.
        class Cached(FakeLLM):
            def chat(self, messages, **k):
                if len(messages) > 2:          # a repair turn: no quota left
                    raise BudgetExhausted("out of quota")
                return super().chat(messages, **k)
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            docs = self.make_docs(t, 3)
            llm = Cached([{**GOOD, "total": 98500}, GOOD, GOOD])
            done = run_bench(docs, ["verified"], llm, None, t / "out", log=lambda *_: None)
            self.assertEqual(done, {"verified": 2})
            ids = [json.loads(x)["id"] for x in (t / "out" / "verified.jsonl").read_text().splitlines()]
            self.assertEqual(ids, ["doc-1", "doc-2"])

    def test_report_compares_only_documents_every_config_finished(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            docs = self.make_docs(t, 2)
            out = t / "out"
            run_bench(docs, ["vision"], FakeLLM([GOOD, GOOD]), None, out, log=lambda *_: None)
            run_bench(docs[:1], ["ocr_llm"], None, FakeLLM([GOOD]), out, log=lambda *_: None)
            self.assertEqual(build_report(out)["documents_scored"], 1)


if __name__ == "__main__":
    unittest.main()
