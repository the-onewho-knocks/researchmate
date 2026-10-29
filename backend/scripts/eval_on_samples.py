"""backend/scripts/eval_on_samples.py"""
"""Measure accuracy against your own human labels, like the paper's Table I/II.

Usage (from backend/):
    python -m scripts.eval_on_samples samples/ labels.csv [--no-llm]

labels.csv columns:  file,criterion_id,met     (met = 1 if the paper meets the criterion, else 0)
"""
import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

from app.api.deps import get_services
from app.services.orchestrator.pipeline import evaluate_file


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("samples_dir")
    ap.add_argument("labels_csv")
    ap.add_argument("--no-llm", action="store_true", help="evaluate rules/ML only")
    args = ap.parse_args()

    svc = get_services()
    if args.no_llm:
        svc.llm.gemini.api_key = ""
        if svc.llm.local is not None:
            svc.llm.local.enabled = False

    truth: dict[str, dict[str, bool]] = defaultdict(dict)
    with open(args.labels_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            truth[row["file"]][row["criterion_id"]] = row["met"].strip().lower() in ("1", "true", "yes")

    outcomes: Counter[str] = Counter()
    by_source: dict[str, list[int]] = defaultdict(lambda: [0, 0])   # source -> [correct, total]
    unassessed = 0

    for fname, labels in truth.items():
        path = Path(args.samples_dir) / fname
        report = evaluate_file(path, path.suffix.lower().lstrip("."), svc)
        verdicts = {v.id: v for c in report.components for v in c.verdicts}
        for cid, met in labels.items():
            v = verdicts.get(cid)
            if v is None or v.status not in ("pass", "fail"):
                unassessed += 1
                continue
            pred_met = v.status == "pass"
            if met and pred_met:
                outcomes["met/pass (correct)"] += 1
            elif not met and not pred_met:
                outcomes["not met/fail (correct)"] += 1
            elif met and not pred_met:
                outcomes["met/fail (false criticism)"] += 1
            else:
                outcomes["not met/pass (missed problem)"] += 1
            by_source[v.source][1] += 1
            by_source[v.source][0] += int(met == pred_met)

    a = outcomes["met/pass (correct)"]
    b = outcomes["not met/fail (correct)"]
    c = outcomes["met/fail (false criticism)"]
    d = outcomes["not met/pass (missed problem)"]
    total = a + b + c + d
    if not total:
        print("No assessable labelled criteria.")
        return

    recall_met = a / (a + c) if (a + c) else 0.0
    recall_not = b / (b + d) if (b + d) else 0.0
    print(f"Assessed: {total}   unassessed (needs review / no verdict): {unassessed}")
    print(f"Accuracy:          {(a + b) / total:.1%}")
    print(f"Balanced accuracy: {(recall_met + recall_not) / 2:.1%}")
    print("\nConfusion matrix (rows = truth, columns = system)")
    print(f"{'':16}{'pass':>8}{'fail':>8}")
    print(f"{'criteria met':16}{a:>8}{c:>8}")
    print(f"{'criteria not met':16}{d:>8}{b:>8}")
    print("\nAccuracy by verdict source")
    for src, (ok, n) in sorted(by_source.items()):
        print(f"  {src:5} {ok}/{n} = {ok / n:.1%}")


if __name__ == "__main__":
    main()
