Scored on 75 CORD test receipts that every configuration finished. Intervals are 95% Wilson; with this few documents, differences under about 10 points are noise.

| Configuration | Total | Subtotal | Tax | Item F1 | All key fields | Calls/doc |
|---|---|---|---|---|---|---|
| ocr_rules | 21% (0.13-0.32) | 20% (0.11-0.34) | 11% (0.04-0.28) | 0.00 | 12% (0.06-0.21) | 0.0 |
| ocr_llm | 33% (0.23-0.45) | 34% (0.22-0.49) | 15% (0.06-0.33) | 0.35 | 25% (0.17-0.36) | 1.0 |
| vision | 100% (0.95-1.00) | 98% (0.88-1.00) | 81% (0.63-0.92) | 0.95 | 87% (0.77-0.93) | 1.0 |
| verified | 100% (0.95-1.00) | 98% (0.88-1.00) | 81% (0.63-0.92) | 0.95 | 87% (0.77-0.93) | 1.0 |

Review flag (documents the arithmetic validator sends to a person):

| Configuration | Flagged | Right when not flagged | Right when flagged | Wrong documents caught |
|---|---|---|---|---|
| ocr_rules | 57 | 50% | 0% | 86% |
| ocr_llm | 56 | 63% | 12% | 88% |
| vision | 0 | 87% | n/a | 0% |
| verified | 0 | 87% | n/a | 0% |
