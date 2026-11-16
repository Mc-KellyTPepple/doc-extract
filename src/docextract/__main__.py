"""Command line: extract one image, run the benchmark, build the report, or serve the HTTP API."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .bench import build_report, run_bench
from .extract import CONFIGS, run_config
from .llm import LLM, TEXT_MODELS, VISION_MODELS


def _llms(args, mode: str = "live"):
    key = os.environ.get("GROQ_API_KEY")
    common = dict(api_key=key, cache_dir=Path(args.cache), mode=mode, ledger_path=Path(args.ledger), max_requests=args.max_requests)
    vm = [m for m in (os.environ.get("DOCX_VISION_MODELS") or "").split(",") if m] or VISION_MODELS
    tm = [m for m in (os.environ.get("DOCX_TEXT_MODELS") or "").split(",") if m] or TEXT_MODELS
    return LLM(models=vm, **common), LLM(models=tm, **common)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="docextract")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("extract", help="extract one receipt image")
    e.add_argument("image")
    e.add_argument("--config", default="verified", choices=CONFIGS)

    b = sub.add_parser("bench", help="run configurations over a CORD sample (needs `datasets` and network)")
    b.add_argument("--configs", nargs="+", default=list(CONFIGS), choices=CONFIGS)
    b.add_argument("--n", type=int, default=100)
    b.add_argument("--seed", type=int, default=1)

    sub.add_parser("report", help="score saved results and write results.md / summary.json / failures.md")
    sub.add_parser("serve", help="run the HTTP API")

    for sp in (e, b):
        sp.add_argument("--cache", default="results/cache")
        sp.add_argument("--ledger", default="results/ledger.json")
        sp.add_argument("--max-requests", type=int, default=900)
    args = p.parse_args(argv)

    if args.cmd == "extract":
        vision, text = _llms(args)
        res = run_config(args.config, Path(args.image).read_bytes(), vision, text)
        print(json.dumps(res.to_dict(), indent=2))
        return 0
    if args.cmd == "bench":
        from .cord import load_sample
        docs = load_sample(args.n, args.seed, Path("data/cord"))
        vision, text = _llms(args)
        run_bench(docs, args.configs, vision, text, Path("results"))
        return 0
    if args.cmd == "report":
        build_report(Path("results"))
        print(Path("results/results.md").read_text())
        return 0
    if args.cmd == "serve":
        from .server import build_app, serve
        serve(build_app())
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
