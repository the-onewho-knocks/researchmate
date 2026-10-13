"""backend/training/evaluate.py"""
"""Evaluate a trained model on HELD-OUT data (papers from other fields than the training set).

Usage (from backend/):
    python -m training.evaluate --task roles    --data training/data/held_out_sentences.jsonl
    python -m training.evaluate --task sections --data training/data/held_out_sections.jsonl
"""
import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)

from app.core.config import get_settings
from app.services.ml.embedder import get_embedder


def load_jsonl(path: str) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def eval_roles(rows, embedder, s) -> None:
    bundle = joblib.load(s.models_dir / "sentence_roles.v1.joblib")
    clf, labels = bundle["clf"], bundle["labels"]
    probs = clf.predict_proba(embedder.encode([r["text"] for r in rows]))
    truth = np.array([[1 if l in r.get("labels", []) else 0 for l in labels] for r in rows])
    pred = (probs >= 0.5).astype(int)

    print(f"{'label':22}{'precision':>10}{'recall':>8}{'f1':>8}{'support':>9}{'uncertain':>11}")
    for j, label in enumerate(labels):
        p, r, f, _ = precision_recall_fscore_support(truth[:, j], pred[:, j], average="binary", zero_division=0)
        uncertain = float(((probs[:, j] > s.ml_reject_t) & (probs[:, j] < s.ml_accept_t)).mean())
        print(f"{label:22}{p:>10.2f}{r:>8.2f}{f:>8.2f}{int(truth[:, j].sum()):>9}{uncertain:>11.0%}")
    print("\n'uncertain' = share of sentences that would be escalated to the LLM with the current thresholds.")


def eval_sections(rows, embedder, s) -> None:
    clf = joblib.load(s.models_dir / "section_clf.v1.joblib")["clf"]
    texts = [r["text"] for r in rows]
    truth = [r["label"] for r in rows]
    pred = list(clf.predict(embedder.encode(texts)))
    labels = sorted(set(truth) | set(pred))

    print(f"Accuracy:          {accuracy_score(truth, pred):.1%}")
    print(f"Balanced accuracy: {balanced_accuracy_score(truth, pred):.1%}\n")
    print(classification_report(truth, pred, zero_division=0))
    print("Confusion matrix (rows = truth, columns = prediction)")
    print("labels:", labels)
    print(confusion_matrix(truth, pred, labels=labels))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["roles", "sections"], required=True)
    ap.add_argument("--data", required=True)
    args = ap.parse_args()

    s = get_settings()
    embedder = get_embedder(s)
    if embedder is None:
        raise SystemExit('Embedding model not available. Run: pip install -e ".[ml]"')
    rows = load_jsonl(args.data)
    (eval_roles if args.task == "roles" else eval_sections)(rows, embedder, s)


if __name__ == "__main__":
    main()
