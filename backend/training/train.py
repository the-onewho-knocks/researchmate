"""backend/training/train.py"""
"""Train the small models on top of frozen sentence embeddings.

Usage (from backend/):
    python -m training.train --task roles    --data training/data/sentences_prelabeled.jsonl
    python -m training.train --task sections --data training/data/section_labels.jsonl

Needs: pip install -e ".[ml]"
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer

from app.core.config import get_settings
from app.services.ml.embedder import get_embedder
from app.services.ml.zero_shot import EXAMPLES

MIN_POSITIVES = 5


def load_jsonl(path: str) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def train_roles(rows: list[dict], embedder, out: Path, test_size: float) -> None:
    texts = [r["text"] for r in rows]
    labels = [[l for l in r.get("labels", []) if l in EXAMPLES] for r in rows]
    counts = Counter(l for ls in labels for l in ls)
    keep = sorted(l for l, c in counts.items() if c >= MIN_POSITIVES)
    if not keep:
        raise SystemExit(f"Need at least {MIN_POSITIVES} examples for at least one label. Counts: {dict(counts)}")
    labels = [[l for l in ls if l in keep] for ls in labels]

    mlb = MultiLabelBinarizer(classes=keep)
    y = mlb.fit_transform(labels)
    x = embedder.encode(texts)

    xtr, xte, ytr, yte = train_test_split(x, y, test_size=test_size, random_state=0)
    clf = OneVsRestClassifier(LogisticRegression(max_iter=1000, class_weight="balanced")).fit(xtr, ytr)
    print(classification_report(yte, clf.predict(xte), target_names=keep, zero_division=0))

    final = OneVsRestClassifier(LogisticRegression(max_iter=1000, class_weight="balanced")).fit(x, y)
    joblib.dump({"clf": final, "labels": keep}, out)
    print(f"Saved {out}  (labels: {keep})")


def train_sections(rows: list[dict], embedder, out: Path, test_size: float) -> None:
    texts = [r["text"] for r in rows]
    labels = [r["label"] for r in rows]
    x = embedder.encode(texts)

    xtr, xte, ytr, yte = train_test_split(x, labels, test_size=test_size, random_state=0, stratify=labels)
    clf = LogisticRegression(max_iter=2000, class_weight="balanced").fit(xtr, ytr)
    print(classification_report(yte, clf.predict(xte), zero_division=0))

    final = LogisticRegression(max_iter=2000, class_weight="balanced").fit(x, labels)
    joblib.dump({"clf": final}, out)
    print(f"Saved {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["roles", "sections"], required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--test-size", type=float, default=0.2)
    args = ap.parse_args()

    s = get_settings()
    embedder = get_embedder(s)
    if embedder is None:
        raise SystemExit('Embedding model not available. Run: pip install -e ".[ml]"')

    s.models_dir.mkdir(parents=True, exist_ok=True)
    rows = load_jsonl(args.data)
    if args.task == "roles":
        train_roles(rows, embedder, s.models_dir / "sentence_roles.v1.joblib", args.test_size)
    else:
        train_sections(rows, embedder, s.models_dir / "section_clf.v1.joblib", args.test_size)


if __name__ == "__main__":
    main()
