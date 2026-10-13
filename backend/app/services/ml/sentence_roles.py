"""backend/app/services/ml/sentence_roles.py"""
import logging
from pathlib import Path

from .zero_shot import EXAMPLES, ZeroShotScorer

log = logging.getLogger(__name__)
MODEL_FILE = "sentence_roles.v1.joblib"


class SentenceRoleModel:
    """Scores sentences for roles such as novelty_claim, research_gap, limitation, future_work.

    Uses the trained classifier when models/sentence_roles.v1.joblib exists,
    otherwise zero-shot similarity (uncalibrated).
    """

    def __init__(self, embedder, models_dir: Path):
        self.embedder = embedder
        self.clf = None
        self.labels: list[str] = []
        self.zero = ZeroShotScorer(embedder) if embedder else None

        path = Path(models_dir) / MODEL_FILE
        if embedder and path.exists():
            try:
                import joblib

                bundle = joblib.load(path)
                self.clf = bundle["clf"]
                self.labels = list(bundle["labels"])
            except Exception as exc:
                log.warning("Could not load %s: %s", path.name, exc)

    @property
    def available(self) -> bool:
        return self.embedder is not None

    def is_calibrated(self, label: str) -> bool:
        return self.clf is not None and label in self.labels

    def score(self, label: str, sentences: list[str]) -> list[float] | None:
        """Probability per sentence that it plays `label`; None if scoring is not possible."""
        if not self.available or not sentences:
            return None
        if self.is_calibrated(label):
            probs = self.clf.predict_proba(self.embedder.encode(sentences))
            return [float(x) for x in probs[:, self.labels.index(label)]]
        if label in EXAMPLES:
            return self.zero.score(label, sentences)
        return None