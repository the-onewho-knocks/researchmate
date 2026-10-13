"""backend/app/services/ml/zero_shot.py"""
"""Cold start: similarity to example phrases, no training data needed.

The probabilities are NOT calibrated. The pipeline therefore uses zero-shot scores
only to accept a sentence, never to reject one (see router.route).
"""
import math

EXAMPLES: dict[str, list[str]] = {
    "novelty_claim": [
        "We propose a novel approach that addresses this problem.",
        "To the best of our knowledge, this is the first study of its kind.",
        "We present a new framework for this task.",
        "The main novelty of our work is a new scoring method.",
        "This paper introduces a new method.",
    ],
    "research_gap": [
        "However, existing approaches do not address this problem.",
        "There is a lack of research on this topic.",
        "Little is known about how this works in practice.",
        "Previous work has not investigated this question.",
        "This remains an open challenge.",
    ],
    "contribution": [
        "The contributions of this paper are as follows.",
        "Our main contributions are a new dataset and a new method.",
        "We make the following contributions.",
    ],
    "limitation": [
        "A limitation of our study is the small sample size.",
        "Our approach has several limitations.",
        "These results may not generalize to other domains.",
        "A threat to validity is the limited number of datasets.",
    ],
    "future_work": [
        "In future work, we plan to extend the approach.",
        "Future research should investigate this further.",
        "An open issue is how this scales to larger data.",
        "We will explore this direction in further studies.",
    ],
    "result_with_numbers": [
        "Our method achieves 94.2% accuracy and outperforms the baselines.",
        "The results show an improvement of 12% over the baseline.",
        "The model reached an F1 score of 0.91 on three datasets.",
    ],
}

MIDPOINT = 0.50   # cosine similarity that maps to p = 0.5
SLOPE = 10.0


class ZeroShotScorer:
    def __init__(self, embedder):
        self.embedder = embedder
        self._cache: dict = {}

    def _examples(self, label: str):
        if label not in self._cache:
            self._cache[label] = self.embedder.encode(EXAMPLES[label])
        return self._cache[label]

    def score(self, label: str, sentences: list[str]) -> list[float] | None:
        if label not in EXAMPLES or not sentences:
            return None
        sentence_vecs = self.embedder.encode(sentences)
        sims = (sentence_vecs @ self._examples(label).T).max(axis=1)
        return [1.0 / (1.0 + math.exp(-(float(s) - MIDPOINT) * SLOPE)) for s in sims]