Scored on 40 CORD test receipts that every configuration finished. Intervals are 95% Wilson; with this few documents, differences under about 10 points are noise.

| Configuration | Total | Subtotal | Tax | Item F1 | All key fields | Calls/doc |
|---|---|---|---|---|---|---|
| ocr_rules | 19% (0.10-0.34) | 12% (0.04-0.29) | 18% (0.06-0.41) | 0.00 | 5% (0.01-0.17) | 0.0 |
| ocr_llm | 32% (0.20-0.48) | 31% (0.17-0.50) | 12% (0.03-0.34) | 0.30 | 18% (0.09-0.32) | 1.0 |
| vision | 100% (0.91-1.00) | 96% (0.81-0.99) | 100% (0.82-1.00) | 0.96 | 92% (0.80-0.97) | 1.0 |

Review flag (documents the arithmetic validator sends to a person):

| Configuration | Flagged | Right when not flagged | Right when flagged | Wrong documents caught |
|---|---|---|---|---|
| ocr_rules | 33 | 29% | 0% | 87% |
| ocr_llm | 33 | 57% | 9% | 91% |
| vision | 6 | 91% | 100% | 0% |
