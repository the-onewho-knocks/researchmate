"""backend/app/services/validation/evidence_verifier.py"""
"""Code, not an LLM: a quote the model gives must really exist in the source text."""
import re
from difflib import SequenceMatcher

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(s: str) -> list[str]:
    return _TOKEN.findall(s.lower())


def verify_evidence(quote: str, source: str, min_ratio: float = 0.9) -> bool:
    q = _tokens(quote or "")
    if len(q) < 3:
        return False
    s = _tokens(source or "")
    if not s:
        return False

    if " " + " ".join(q) + " " in " " + " ".join(s) + " ":
        return True       # exact match after normalisation

    m = SequenceMatcher(None, q, s, autojunk=False).find_longest_match(0, len(q), 0, len(s))
    return m.size / len(q) >= min_ratio