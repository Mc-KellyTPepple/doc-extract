"""Run the configurations over a CORD sample and write the results. Runs are resumable: finished documents are
skipped, so when a daily quota runs out the run stops cleanly and the next one continues it."""
from __future__ import annotations

import json
from pathlib import Path

from .evaluate import FIELDS, score_doc, summarize
from .extract import CONFIGS, run_config
from .llm import LLM, BudgetExhausted, LLMError
from .schema import receipt_from_dict


def _load(path: Path) -> dict[str, dict]:
    rows = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                rows[row["id"]] = row
    return rows


def run_bench(docs: list[dict], configs: list[str], vision_llm: LLM | None, text_llm: LLM | None, out_dir: Path,
              log=print) -> dict[str, int]:
    """Returns {config: documents finished}. Stops a configuration (not the whole run) when its quota is spent."""
    out_dir.mkdir(parents=True, exist_ok=True)
    finished = {}
    for config in configs:
        path = out_dir / f"{config}.jsonl"
        done = _load(path)
        llm = text_llm if config == "ocr_llm" else vision_llm
        errors = 0
        for doc in docs:
            if doc["id"] in done:
                continue
            before = (llm.usage.prompt_tokens, llm.usage.completion_tokens) if llm else (0, 0)
            try:
                res = run_config(config, Path(doc["image"]).read_bytes(), vision_llm, text_llm)
            except BudgetExhausted as exc:
                log(f"[{config}] stopping: {exc}")
                break
            except LLMError as exc:
                errors += 1
                log(f"[{config}] {doc['id']}: model error, skipped ({str(exc)[:120]})")
                continue
            row = {"id": doc["id"], "config": config, "gold": doc["gold"].to_dict(), "pred": res.receipt.to_dict(),
                   "issues": [i.__dict__ for i in res.issues], "flagged": res.needs_review, "calls": res.calls,
                   "model": res.model, "repaired": res.repaired, "parsed": res.parsed,
                   "prompt_tokens": (llm.usage.prompt_tokens - before[0]) if llm else 0,
                   "completion_tokens": (llm.usage.completion_tokens - before[1]) if llm else 0}
            with path.open("a") as f:
                f.write(json.dumps(row, sort_keys=True) + "\n")
            done[doc["id"]] = row
        finished[config] = len(done)
        log(f"[{config}] {len(done)}/{len(docs)} documents done" + (f", {errors} model errors" if errors else ""))
    return finished


def _score_rows(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        score = score_doc(receipt_from_dict(r["pred"]), receipt_from_dict(r["gold"]))
        out.append({**r, "score": score})
    return out


def build_report(out_dir: Path) -> dict:
    """Score every configuration on the documents that ALL configurations finished, so the comparison is like for like."""
    per = {c: _load(out_dir / f"{c}.jsonl") for c in CONFIGS if (out_dir / f"{c}.jsonl").exists()}
    if not per:
        raise SystemExit(f"no results in {out_dir}")
    common = set.intersection(*(set(v) for v in per.values()))
    summary = {"documents_scored": len(common), "dataset": "CORD v2 test sample", "configs": {}}
    for c, rows in per.items():
        scored = _score_rows([rows[i] for i in sorted(common)])
        summary["configs"][c] = summarize(scored)
        summary["configs"][c]["model_errors_not_scored"] = None
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True))
    (out_dir / "results.md").write_text(_markdown(summary))
    (out_dir / "failures.md").write_text(_failures(per, common))
    return summary


def _pct(x) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def _markdown(s: dict) -> str:
    lines = [f"Scored on {s['documents_scored']} CORD test receipts that every configuration finished. "
             "Intervals are 95% Wilson; with this few documents, differences under about 10 points are noise.", "",
             "| Configuration | Total | Subtotal | Tax | Item F1 | All key fields | Calls/doc |",
             "|---|---|---|---|---|---|---|"]
    for c, m in s["configs"].items():
        cell = lambda k: f"{_pct(m[k]['accuracy'])} ({m[k]['ci95'][0]:.2f}-{m[k]['ci95'][1]:.2f})"  # noqa: E731
        lines.append(f"| {c} | {cell('total')} | {cell('subtotal')} | {cell('tax')} | {m['items']['f1']:.2f} | "
                     f"{cell('all_fields_correct')} | {m['cost']['model_calls_per_doc']:.1f} |")
    lines += ["", "Review flag (documents the arithmetic validator sends to a person):", "",
              "| Configuration | Flagged | Right when not flagged | Right when flagged | Wrong documents caught |", "|---|---|---|---|---|"]
    for c, m in s["configs"].items():
        r = m["review"]
        lines.append(f"| {c} | {r['flagged']} | {_pct(r['accuracy_when_not_flagged'])} | {_pct(r['accuracy_when_flagged'])} | {_pct(r['wrong_documents_caught'])} |")
    return "\n".join(lines) + "\n"


def _failures(per: dict, common: set, limit: int = 12) -> str:
    """Documents where the verified (or, failing that, vision) configuration is wrong, and whether it flagged them."""
    config = "verified" if "verified" in per else next(iter(per))
    lines = [f"# Failures of `{config}`", "", "Each entry: document, whether it was flagged, and the fields that differ (predicted vs label).", ""]
    shown = 0
    for doc_id in sorted(common):
        row = per[config][doc_id]
        pred, gold = receipt_from_dict(row["pred"]), receipt_from_dict(row["gold"])
        score = score_doc(pred, gold)
        if score["all_fields"] and score["items_tp"] == score["items_gold"] == score["items_pred"]:
            continue
        diffs = [f"{f}: {getattr(pred, f)} vs {getattr(gold, f)}" for f in FIELDS if f in score["fields"] and not score["fields"][f]]
        diffs.append(f"items matched {score['items_tp']} of {score['items_gold']} labelled ({score['items_pred']} predicted)")
        why = "; ".join(i["message"] for i in row["issues"]) or "no check failed"
        lines.append(f"- `{doc_id}` {'FLAGGED' if row['flagged'] else 'not flagged'}: " + "; ".join(diffs) + f". Checks: {why}")
        shown += 1
        if shown >= limit:
            break
    return "\n".join(lines) + "\n"
