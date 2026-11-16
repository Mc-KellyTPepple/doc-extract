Scored on 100 CORD test receipts that every configuration finished. Intervals are 95% Wilson; with this few documents, differences under about 10 points are noise.

| Configuration | Total | Subtotal | Tax | Item F1 | All key fields | Calls/doc |
|---|---|---|---|---|---|---|
| ocr_rules | 25% (0.18-0.35) | 18% (0.11-0.30) | 15% (0.07-0.28) | 0.00 | 11% (0.06-0.19) | 0.0 |
| ocr_llm | 38% (0.29-0.48) | 32% (0.22-0.44) | 20% (0.10-0.34) | 0.38 | 24% (0.17-0.33) | 1.0 |

Review flag (documents the arithmetic validator sends to a person):

| Configuration | Flagged | Right when not flagged | Right when flagged | Wrong documents caught |
|---|---|---|---|---|
| ocr_rules | 76 | 46% | 0% | 85% |
| ocr_llm | 76 | 71% | 9% | 91% |
