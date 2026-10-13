"""backend/training/bootstrap_labels.py"""
"""Let Gemini pre-label sentences, then YOU spot-check them before training.

LLM labels carry LLM mistakes into your classifier, so review a sample by hand
(open the output file and fix the "labels" lists).

Usage (from backend/):
    python -m training.bootstrap_labels --limit 500
"""
import argparse
import json
from pathlib import Path

from pydantic import BaseModel

from app.core.config import get_settings
from app.services.llm.gemini_client import GeminiClient
from app.services.ml.zero_shot import EXAMPLES

SYSTEM = "You label sentences from scientific papers. Output JSON only."
DESCRIPTIONS = {
    "novelty_claim": "states what is new about the paper's own work",
    "research_gap": "points out a gap, shortcoming or open problem in existing work",
    "contribution": "lists or announces the paper's contributions",
    "limitation": "states a limitation or threat to validity of the own work",
    "future_work": "mentions future work, open issues or future research directions",
    "result_with_numbers": "reports a quantitative result",
}


class LabelItem(BaseModel):
    i: int
    labels: list[str]


def build_prompt(sentences: list[str]) -> str:
    roles = "\n".join(f"- {k}: {DESCRIPTIONS.get(k, '')}" for k in EXAMPLES)
    numbered = "\n".join(f"{n}. {s}" for n, s in enumerate(sentences))
    return (
        "Label each numbered sentence with zero or more of these roles:\n"
        f"{roles}\n\n"
        "Return a JSON array with one object per sentence, holding the sentence number as i "
        "and the list of roles as labels. Use an empty list when no role applies.\n\n"
        f"{numbered}"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="training/data/sentences_unlabeled.jsonl")
    ap.add_argument("--out", default="training/data/sentences_prelabeled.jsonl")
    ap.add_argument("--batch", type=int, default=25)
    ap.add_argument("--limit", type=int, default=500)
    args = ap.parse_args()

    s = get_settings()
    client = GeminiClient(s.gemini_api_key, s.gemini_model, s.llm_timeout_s, s.thinking_budget)
    if not client.available:
        raise SystemExit("Set GEMINI_API_KEY in .env first.")

    rows = [json.loads(l) for l in Path(args.inp).read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = rows[: args.limit]
    valid = set(EXAMPLES)
    out_rows = []

    for start in range(0, len(rows), args.batch):
        batch = rows[start:start + args.batch]
        prompt = build_prompt([r["text"] for r in batch])
        try:
            res = client.generate_json(SYSTEM, prompt, list[LabelItem], max_output_tokens=2000)
            items = [LabelItem(**x) for x in json.loads(res.text)]
        except Exception as exc:
            print(f"batch at {start} failed: {exc}")
            continue
        for it in items:
            if 0 <= it.i < len(batch):
                out_rows.append(
                    {
                        "text": batch[it.i]["text"],
                        "labels": [l for l in it.labels if l in valid],
                        "section": batch[it.i].get("section"),
                        "needs_check": True,
                    }
                )
        print(f"{len(out_rows)} labelled")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Wrote {args.out}. Review a sample by hand before training.")


if __name__ == "__main__":
    main()
