"""backend/app/services/orchestrator/context_selector.py"""
import re

from app.schemas.framework import Criterion
from app.services.rules.primitives import split_sentences

_WORD = re.compile(r"[a-z0-9]+")


def _scores(sentences: list[str], query: str, embedder) -> list[float]:
    if embedder is not None:
        vecs = embedder.encode(sentences)
        q = embedder.encode([query])[0]
        return (vecs @ q).tolist()
    qw = set(_WORD.findall(query.lower()))
    out = []
    for s in sentences:
        words = _WORD.findall(s.lower())
        out.append(len(qw & set(words)) / (1 + len(words) ** 0.5))
    return out


def select_context(
    text: str,
    criteria: list[Criterion],
    embedder=None,
    k: int = 12,
    max_chars: int = 6000,
) -> str:
    """Whole text if it is short, otherwise the sentences most relevant to the criteria.

    The opening sentence is always kept and the original order is preserved.
    """
    if len(text) <= max_chars:
        return text
    sentences = split_sentences(text)
    if len(sentences) <= k:
        return text[:max_chars]

    query = " ".join(f"{c.name} {c.hint}" for c in criteria)
    scores = _scores(sentences, query, embedder)
    top = sorted(range(len(sentences)), key=lambda i: -scores[i])[:k]
    keep = sorted(set(top) | {0})
    return " ".join(sentences[i] for i in keep)[:max_chars]