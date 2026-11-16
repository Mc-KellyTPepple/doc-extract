Scored on 45 CORD test receipts that every configuration finished. Intervals are 95% Wilson; with this few documents, differences under about 10 points are noise.

| Configuration | Total | Subtotal | Tax | Item F1 | All key fields | Calls/doc |
|---|---|---|---|---|---|---|
| ocr_rules | 17% (0.08-0.31) | 10% (0.04-0.26) | 16% (0.06-0.38) | 0.00 | 4% (0.01-0.15) | 0.0 |
| ocr_llm | 29% (0.17-0.44) | 24% (0.12-0.42) | 11% (0.03-0.31) | 0.41 | 18% (0.09-0.31) | 1.0 |
| vision | 71% (0.56-0.83) | 69% (0.51-0.83) | 58% (0.36-0.77) | 0.71 | 67% (0.52-0.79) | 1.0 |

Review flag (documents the arithmetic validator sends to a person):

| Configuration | Flagged | Right when not flagged | Right when flagged | Wrong documents caught |
|---|---|---|---|---|
| ocr_rules | 38 | 29% | 0% | 88% |
| ocr_llm | 37 | 62% | 8% | 92% |
| vision | 9 | 69% | 56% | 27% |
