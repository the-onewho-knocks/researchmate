"""backend/tests/test_ml_router.py"""
import pytest

from app.services.ml.router import route
from app.services.ml.sentence_roles import SentenceRoleModel


def test_route_thresholds():
    assert route(0.90, 0.75, 0.25) == "accept"
    assert route(0.10, 0.75, 0.25) == "reject"
    assert route(0.50, 0.75, 0.25) == "escalate"
    assert route(0.75, 0.75, 0.25) == "accept"       # boundaries are inclusive
    assert route(0.25, 0.75, 0.25) == "reject"


def test_uncalibrated_scores_never_reject():
    assert route(0.01, 0.75, 0.25, calibrated=False) == "escalate"
    assert route(0.99, 0.75, 0.25, calibrated=False) == "accept"


def test_model_is_unavailable_without_embedder(tmp_path):
    m = SentenceRoleModel(None, tmp_path)
    assert not m.available
    assert m.score("novelty_claim", ["We propose a thing."]) is None


def test_zero_shot_scoring_with_fake_embedder(tmp_path, monkeypatch):
    np = pytest.importorskip("numpy")
    from app.services.ml import zero_shot

    class FakeEmbedder:
        def encode(self, texts):
            return np.array([[1.0, 0.0] if "alpha" in t else [0.0, 1.0] for t in texts])

    monkeypatch.setitem(zero_shot.EXAMPLES, "toy", ["alpha beta"])
    m = SentenceRoleModel(FakeEmbedder(), tmp_path)

    assert m.available
    assert not m.is_calibrated("toy")                # no trained model file
    high, low = m.score("toy", ["alpha gamma", "delta"])
    assert high > 0.9 and low < 0.1
    assert m.score("unknown_label", ["alpha"]) is None
