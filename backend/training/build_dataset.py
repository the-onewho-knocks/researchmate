"""backend/training/build_dataset.py"""
"""Build training data from LaTeX sources (their \\section structure gives free labels).

Usage (from backend/):
    python -m training.build_dataset --tex-dir papers/ --out-dir training/data

Writes:
    section_labels.jsonl       {"text", "label", "file"}     one row per paragraph
    sentences_unlabeled.jsonl  {"text", "section", "file"}   sentences to label for the role classifier
"""
import argparse
import json
import random
from pathlib import Path

from app.services.extraction.latex_extractor import LatexExtractor
from app.services.extraction.normalizer import normalize
from app.services.rules.primitives import split_sentences
from app.services.sections.identifier import identify_sections

SECTION_LABELS = ["abstract", "introduction", "related_work", "methods", "results", "discussion", "conclusion"]
SENTENCE_SECTIONS = {"abstract", "introduction", "related_work", "discussion", "conclusion"}


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tex-dir", required=True)
    ap.add_argument("--out-dir", default="training/data")
    ap.add_argument("--max-sentences", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    section_rows: list[dict] = []
    sentence_rows: list[dict] = []
    files = sorted(Path(args.tex_dir).rglob("*.tex"))

    for path in files:
        try:
            doc = normalize(LatexExtractor().extract(path))
        except Exception as exc:
            print(f"skip {path.name}: {exc}")
            continue
        smap = identify_sections(doc)
        for label in SECTION_LABELS:
            sp = smap.spans.get(label)
            if not sp or sp.confidence < 0.9:      # only trust explicit LaTeX structure
                continue
            for b in doc.blocks[sp.start:sp.end]:
                if b.kind != "text" or len(b.text.split()) < 8:
                    continue
                section_rows.append({"text": b.text, "label": label, "file": path.name})
                if label in SENTENCE_SECTIONS:
                    for s in split_sentences(b.text):
                        if 6 <= len(s.split()) <= 60:
                            sentence_rows.append({"text": s, "section": label, "file": path.name})

    seen: set[str] = set()
    unique = []
    for r in sentence_rows:
        if r["text"] not in seen:
            seen.add(r["text"])
            unique.append(r)
    random.Random(args.seed).shuffle(unique)
    unique = unique[: args.max_sentences]

    out = Path(args.out_dir)
    write_jsonl(out / "section_labels.jsonl", section_rows)
    write_jsonl(out / "sentences_unlabeled.jsonl", unique)
    print(f"{len(files)} files -> {len(section_rows)} labelled paragraphs, {len(unique)} sentences to label")


if __name__ == "__main__":
    main()
