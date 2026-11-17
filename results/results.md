Scored on 34 CORD test receipts that every configuration finished. Intervals are 95% Wilson; with this few documents, differences under about 10 points are noise.

| Configuration | Total | Subtotal | Tax | Item F1 | All key fields | Calls/doc |
|---|---|---|---|---|---|---|
| ocr_rules | 16% (0.07-0.33) | 14% (0.05-0.35) | 8% (0.01-0.33) | 0.00 | 6% (0.02-0.19) | 0.0 |
| ocr_llm | 29% (0.16-0.47) | 29% (0.14-0.50) | 8% (0.01-0.33) | 0.26 | 21% (0.10-0.37) | 1.0 |
| vision | 100% (0.89-1.00) | 95% (0.77-0.99) | 100% (0.77-1.00) | 0.99 | 91% (0.77-0.97) | 1.0 |
| verified | 100% (0.89-1.00) | 95% (0.77-0.99) | 100% (0.77-1.00) | 0.99 | 91% (0.77-0.97) | 1.0 |

Review flag (documents the arithmetic validator sends to a person):

| Configuration | Flagged | Right when not flagged | Right when flagged | Wrong documents caught |
|---|---|---|---|---|
| ocr_rules | 28 | 33% | 0% | 88% |
| ocr_llm | 27 | 57% | 11% | 89% |
| vision | 0 | 91% | n/a | 0% |
| verified | 0 | 91% | n/a | 0% |
