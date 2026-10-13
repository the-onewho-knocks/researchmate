"""backend/tests/test_evidence_verifier.py"""
from app.services.validation.evidence_verifier import verify_evidence

SOURCE = (
    "We propose a label-free detector based on isolation trees. "
    "It reaches an average F1 score of 94.2% on three datasets."
)


def test_exact_quote_is_accepted():
    assert verify_evidence("We propose a label-free detector based on isolation trees", SOURCE)


def test_case_and_punctuation_do_not_matter():
    assert verify_evidence("we PROPOSE a label free detector, based on isolation trees!", SOURCE)


def test_fabricated_quote_is_rejected():
    assert not verify_evidence("The method outperforms every known baseline by a wide margin", SOURCE)


def test_altered_quote_is_rejected():
    assert not verify_evidence("We propose a supervised detector based on random forests", SOURCE)


def test_too_short_quotes_are_rejected():
    assert not verify_evidence("label-free", SOURCE)
    assert not verify_evidence("", SOURCE)
    assert not verify_evidence("We propose a thing", "")
