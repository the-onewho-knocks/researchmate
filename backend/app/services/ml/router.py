"""backend/app/services/ml/router.py"""
def route(p: float, accept_t: float, reject_t: float, calibrated: bool = True) -> str:
    """Decide what to do with a probability: accept | reject | escalate.

    Uncalibrated scores (zero-shot) can accept but never reject, because a low
    similarity does not prove the criterion is missing.
    """
    if p >= accept_t:
        return "accept"
    if calibrated and p <= reject_t:
        return "reject"
    return "escalate"