# Doc Extract

Turn a photo of a receipt or invoice into structured data, and **say when the numbers do not add up** instead of
guessing. A vision model reads the image into JSON; an arithmetic validator then checks the receipt against itself
(line prices add up to the subtotal, subtotal plus tax and service minus discount equals the total). If a check fails,
the model is shown which one and re-reads the image once. Anything still inconsistent is flagged for a person.

It runs on Groq models, Render and GitHub Actions, and is measured on the public
[CORD v2](https://huggingface.co/datasets/naver-clova-ix/cord-v2) receipt set (CC BY 4.0) against OCR baselines.

> **A mistake worth knowing about:** the first benchmark run (kept in `results/v1-amounts-as-numbers/`) used a prompt that
> asked for amounts as numbers, and the model turned the printed `60.000` (sixty thousand) into `60.0`. Eleven of the 15
> wrong documents were this one error, 1000x on every field, which the arithmetic check cannot catch because the sums
> still agree. The prompt now asks for amounts as text exactly as printed, and the benchmark was re-run from scratch.

## Results

100 CORD v2 test receipts (seed 1), the same receipts for every configuration, 95% Wilson intervals
(full table: `results/results.md`, failures: `results/failures.md`).

| Configuration | Total | Subtotal | Tax | Item F1 | All key fields |
|---|---|---|---|---|---|
| OCR + keyword rules | 25% | 18% | 15% | 0.00 | 11% |
| OCR + text model | 38% | 32% | 20% | 0.38 | 24% |
| Vision model | 100% (96-100) | 98% | 83% | 0.92 | 88% (80-93) |
| Vision + validator re-read | 100% | 98% | 83% | 0.92 | 88% |

- **Reading the image directly wins by a wide margin** over OCR followed by a text model, at about 2,100 tokens per receipt against about 680.
- **The validator and re-read did not help on this data.** The re-read ran on 9 receipts, the second reading was adopted on 8, and all 9 stayed flagged;
  accuracy is identical to the single read. The flag caught 1 of the 12 receipts with a wrong key field, and 8 of the 9 receipts it flagged had every key field right
  (it points at line-item problems). The vision model's errors are mostly a missed line (15 receipts) or an empty tax field (7), and both keep the arithmetic consistent.
- `cord-test-0013` has a garbled label in the dataset itself (subtotal 4663646636), so it counts against the model although the model's reading looks right.
- With 100 receipts, differences under about 10 points are noise.

## The four configurations

| Name | What it does | Model calls |
|---|---|---|
| `ocr_rules` | Tesseract text plus keyword rules. Finds total, subtotal, tax only. The floor to beat. | 0 |
| `ocr_llm` | Tesseract text, then a text model writes the JSON. The classic two-stage pipeline. | 1 |
| `vision` | A vision model reads the image and writes the JSON. | 1 |
| `verified` | `vision`, then the validator; on a failed check the model re-reads once. Leftover failures are flagged. | 1 to 2 |

Question the benchmark answers: does reading the image directly beat OCR-then-LLM, does the validator-driven re-read
fix real errors, and **when the validator flags a document, how often is it actually wrong?** That last number decides
whether the flag is useful or noise, so it is reported next to accuracy.

## Metrics

- **Total, subtotal, tax**: exact match within 0.5 currency units, scored only where CORD labels the field.
- **Item F1**: a predicted line matches a labelled line when the price matches and the names are similar.
- **All key fields**: every labelled field among total, subtotal, tax is right.
- **Review flag**: accuracy among unflagged and flagged documents, and the share of wrong documents the flag catches.
- Intervals are 95% Wilson. With about 100 documents, differences smaller than roughly 10 points are noise.

Configurations are compared only on documents that all of them finished.

## Design choices

- **The validator allows real-world variation.** Tax already included in the prices, service charges, discounts and
  small rounding are accepted. A validator that cries wolf is as useless as one that never speaks. The flip side: a
  total that equals the subtotal is accepted even when tax is listed, so some errors cannot be caught by arithmetic.
- **No invented numbers.** The prompt tells the model to copy what is printed and use `null` otherwise; the validator
  never fills a gap.
- **Privacy.** The API processes images in memory only. Nothing uploaded is stored or logged.
- **Built for a limited quota.** A rate limiter, response cache and daily ledger keep the Groq client inside the provider's limits
  (copied from the Data Analyst Agent project). The web service adds per-visitor and daily caps.

## Run it

```bash
pip install -e .                          # requests + pillow
export GROQ_API_KEY=...                   # from console.groq.com/keys (never commit it)
python -m docextract extract receipt.jpg  # prints the JSON, issues and review flag
python -m docextract serve                # HTTP API on $PORT (default 7860)

pip install -e ".[eval]" && sudo apt-get install tesseract-ocr
python -m docextract bench --n 100        # downloads CORD, runs all configurations (resumable)
python -m docextract report               # writes results/results.md, summary.json, failures.md
python -m unittest discover -s tests -t . # 40 tests, no network needed
```

API:

```
POST /extract   {"image": "data:image/jpeg;base64,..."}
-> {"receipt": {...}, "issues": [...], "needs_review": bool, "calls": 1|2, "repaired": bool, "model": "...", "seconds": 4.2}
GET  /health
```

## Deploy

1. Add the repository secret `GROQ_API_KEY`, then run the **Benchmark on CORD** workflow.
2. Render dashboard, New, Blueprint, pick this repo (`render.yaml` defines the service). Set `GROQ_API_KEY` in the service's Environment tab.
3. The service sleeps when idle; the portfolio page wakes it when someone opens the demo. There is no keep-alive pinging.

## Limits

- CORD receipts are Indonesian, photographed, mostly food and drink. Results do not automatically carry over to other
  languages, long invoices with many pages, or handwritten documents.
- Vision-model quality can change when the provider changes models.
- The validator cannot catch errors that keep the arithmetic consistent (for example two misread digits that cancel).

## License

MIT. CORD is CC BY 4.0 (Park et al., 2019).
