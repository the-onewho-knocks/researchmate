"""backend/app/services/ml/embedder.py"""
import logging

from app.core.config import Settings

log = logging.getLogger(__name__)


class Embedder:
    """Small sentence-embedding model, loaded once and shared."""

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def encode(self, texts):
        return self.model.encode(
            list(texts), normalize_embeddings=True, show_progress_bar=False, batch_size=32
        )


_instance: Embedder | None = None
_tried = False


def get_embedder(settings: Settings) -> Embedder | None:
    """Return the shared embedder, or None if ML is disabled or not installed."""
    global _instance, _tried
    if _tried:
        return _instance
    _tried = True
    if not settings.ml_enabled:
        return None
    try:
        _instance = Embedder(settings.embed_model)
    except Exception as exc:  # missing package, no internet for the first download, ...
        log.warning("ML layer disabled: could not load embedding model (%s)", exc)
        _instance = None
    return _instance