"""backend/scripts/cost_report.py"""
"""Token and cost report from data/usage.jsonl.

Usage (from backend/):
    python -m scripts.cost_report --in-price 0.30 --out-price 2.50
Prices are per 1M tokens and are YOUR numbers: look up the current price list for your model.
"""
import argparse
import json

from app.core.config import get_settings


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-price", type=float, default=None, help="price per 1M input tokens")
    ap.add_argument("--out-price", type=float, default=None, help="price per 1M output tokens")
    args = ap.parse_args()

    path = get_settings().data_dir / "usage.jsonl"
    if not path.exists():
        print(f"No usage log yet at {path}")
        return

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    n = len(rows)
    t_in = sum(r.get("input_tokens", 0) for r in rows)
    t_out = sum(r.get("output_tokens", 0) for r in rows)
    calls = sum(r.get("llm_calls", 0) for r in rows)
    by_src = {k: sum(r.get(f"n_{k}", 0) for r in rows) for k in ("rule", "ml", "llm", "unresolved")}
    decided = sum(by_src[k] for k in ("rule", "ml", "llm")) or 1

    print(f"Evaluations: {n}   LLM calls: {calls}")
    print(f"Tokens: {t_in} in / {t_out} out   (avg per evaluation: {t_in // max(n, 1)} / {t_out // max(n, 1)})")
    print("Verdicts by source:")
    for k, v in by_src.items():
        share = f" ({v / decided:.0%} of decided)" if k != "unresolved" else ""
        print(f"  {k:10} {v}{share}")

    if args.in_price is not None and args.out_price is not None:
        cost = t_in / 1e6 * args.in_price + t_out / 1e6 * args.out_price
        print(f"Estimated cost: {cost:.4f} total, {cost / max(n, 1):.4f} per evaluation")


if __name__ == "__main__":
    main()