"""backend/app/services/ml/section_classifier.py"""
import logging
from pathlib import Path

log = logging.getLogger(__name__)
MODEL_FILE = "section_clf.v1.joblib"


class SectionClassifier:
    """Paragraph -> section label. Only used by the fallback when headings are missing."""

    def __init__(self, embedder, models_dir: Path):
        self.embedder = embedder
        self.clf = None
        path = Path(models_dir) / MODEL_FILE
        if embedder and path.exists():
            try:
                import joblib

                self.clf = joblib.load(path)["clf"]
            except Exception as exc:
                log.warning("Could not load %s: %s", path.name, exc)

    @property
    def available(self) -> bool:
        return self.clf is not None and self.embedder is not None

    def predict(self, texts: list[str]) -> list[str]:
        return [str(x) for x in self.clf.predict(self.embedder.encode(texts))]
