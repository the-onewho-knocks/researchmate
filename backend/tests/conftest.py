import zipfile  # noqa: F401  (used by tests through fixtures)

import pytest

from app.schemas.document import Block, ParsedDocument
from app.schemas.sections import SectionMap, SectionSpan
from app.services.rules.primitives import EvalContext

TITLE = "Label-Free Anomaly Detection for Industrial Sensor Streams"

ABSTRACT = (
    "Anomaly detection in industrial sensor streams is difficult because labelled failures are rare and expensive to collect. "
    "Existing detectors depend on labels or on hand-tuned thresholds, which limits their use in practice. "
    "We propose a label-free detector that combines isolation trees with an adaptive scoring function and needs no failure examples for training. "
    "The detector is designed for streaming data and runs on commodity hardware. "
    "On three public datasets it reaches an average F1 score of 94.2% and outperforms five baselines by 6 percentage points. "
    "We also release a benchmark that makes future comparisons easier for the community. "
    "Our code and data are publicly available."
)

# (heading, body) in plain text; used for the .docx and .pdf fixtures
SECTIONS = [
    ("Abstract", ABSTRACT),
    (
        "Introduction",
        "Industrial sensors produce large streams of data [1], [2]. "
        "However, labels are rare, which is a major challenge for supervised detectors. "
        "We propose a label-free detector based on isolation trees. "
        "Our contributions are a novel scoring function and a public benchmark.",
    ),
    (
        "Related Work",
        "Prior work [1] relies on labelled failures. "
        "In contrast, our approach needs no labels [3]. "
        "However, no study compares streaming detectors on a common benchmark.",
    ),
    (
        "Method",
        "We follow the protocol of [2]. The dataset is split 80/20 and the learning rate is 0.01. "
        "The code is available on GitHub.",
    ),
    (
        "Results",
        "Figure 1 shows the F1 scores. Our method reaches 94.2% F1 on all datasets.\nFigure 1: F1 scores per dataset.",
    ),
    (
        "Discussion",
        "The results indicate robust behaviour across datasets. "
        "A limitation is the small number of datasets. Future work will address concept drift.",
    ),
    (
        "Conclusion",
        "In this paper we proposed a label-free detector. We conclude that it outperforms the baselines. "
        "Future research will extend it to multivariate streams.",
    ),
]
REFERENCES = [
    '[1] A. Author, "Supervised detection," Journal of Sensors, vol. 1, pp. 1-10, 2023.',
    '[2] B. Writer, "Isolation protocols," in Proceedings of the International Conference on Data, 2022.',
    '[3] C. Person, "Streaming benchmarks," IEEE Transactions on Things, vol. 5, no. 2, 2024.',
]

SAMPLE_TEX = r"""
\documentclass{article}
\title{Label-Free Anomaly Detection for Industrial Sensor Streams}
\begin{document}
\maketitle
\begin{abstract}
Anomaly detection in industrial sensor streams is difficult because labelled failures are rare and expensive to collect.
Existing detectors depend on labels or on hand-tuned thresholds, which limits their use in practice.
We propose a label-free detector that combines isolation trees with an adaptive scoring function and needs no failure examples for training.
The detector is designed for streaming data and runs on commodity hardware.
On three public datasets it reaches an average F1 score of 94.2\% and outperforms five baselines by 6 percentage points.
We also release a benchmark that makes future comparisons easier for the community.
Our code and data are publicly available.
\end{abstract}

\section{Introduction}
Industrial sensors produce large streams of data \cite{a,b}. However, labels are rare, which is a major challenge for supervised detectors.
We propose a label-free detector based on isolation trees. Our contributions are a novel scoring function and a public benchmark.

\section{Related Work}
Prior work \cite{a} relies on labelled failures. In contrast, our approach needs no labels \cite{c}.
However, no study compares streaming detectors on a common benchmark.

\section{Method}
We follow the protocol of \cite{b}. The dataset is split 80/20 and the learning rate is 0.01. The code is available on GitHub.

\section{Results}
Figure~\ref{fig:f1} shows the F1 scores. Our method reaches 94.2\% F1 on all datasets.
\begin{figure}
\caption{F1 scores per dataset.}
\end{figure}

\section{Discussion}
The results indicate robust behaviour across datasets. A limitation is the small number of datasets. Future work will address concept drift.

\section{Conclusion}
In this paper we proposed a label-free detector. We conclude that it outperforms the baselines. Future research will extend it to multivariate streams.

\begin{thebibliography}{9}
\bibitem{a} A. Author, ``Supervised detection,'' \emph{Journal of Sensors}, vol. 1, pp. 1--10, 2023.
\bibitem{b} B. Writer, ``Isolation protocols,'' in \emph{Proceedings of the International Conference on Data}, 2022.
\bibitem{c} C. Person, ``Streaming benchmarks,'' \emph{IEEE Transactions on Things}, vol. 5, no. 2, 2024.
\end{thebibliography}
\end{document}
"""


@pytest.fixture
def tex_file(tmp_path):
    p = tmp_path / "paper.tex"
    p.write_text(SAMPLE_TEX, encoding="utf-8")
    return p


@pytest.fixture
def docx_file(tmp_path):
    from docx import Document

    d = Document()
    d.add_heading(TITLE, 0)
    for heading, body in SECTIONS:
        d.add_heading(heading, 1)
        for para in body.split("\n"):
            d.add_paragraph(para)
    d.add_heading("References", 1)
    for ref in REFERENCES:
        d.add_paragraph(ref)
    p = tmp_path / "paper.docx"
    d.save(str(p))
    return p


@pytest.fixture
def pdf_file(tmp_path):
    import fitz

    pdf = fitz.open()
    state = {"page": pdf.new_page(), "y": 80}

    def add(heading: str, body: str) -> None:
        if state["y"] > 600:
            state["page"], state["y"] = pdf.new_page(), 80
        page, y = state["page"], state["y"]
        page.insert_text((72, y), heading, fontsize=12, fontname="hebo")
        rc = page.insert_textbox(fitz.Rect(72, y + 8, 523, y + 160), body, fontsize=10, fontname="helv")
        assert rc >= 0, "test PDF text did not fit its box"
        state["y"] = y + 175

    state["page"].insert_text((72, 70), TITLE, fontsize=14, fontname="hebo")
    state["y"] = 110
    for heading, body in SECTIONS:
        add(heading, body)
    add("References", "\n".join(REFERENCES))

    p = tmp_path / "paper.pdf"
    pdf.save(str(p))
    pdf.close()
    return p


@pytest.fixture
def make_ctx():
    """Build an EvalContext from {section_label: text}; one paragraph per line."""

    def _make(sections: dict[str, str], meta: dict | None = None) -> EvalContext:
        blocks: list[Block] = []
        spans: dict[str, SectionSpan] = {}
        for label, text in sections.items():
            blocks.append(Block(text=label.replace("_", " ").title(), kind="heading", level=1))
            start = len(blocks)
            for para in text.split("\n"):
                blocks.append(Block(text=para))
            spans[label] = SectionSpan(label=label, start=start, end=len(blocks))
        doc = ParsedDocument(file_type="tex", blocks=blocks, meta=meta or {})
        return EvalContext(doc, SectionMap(spans=spans))

    return _make


@pytest.fixture
def client(tmp_path, monkeypatch):
    """API client with an isolated data dir, no Gemini key and the ML layer off."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("ML_ENABLED", "false")

    from app.api.deps import get_services
    from app.core.config import get_settings

    get_settings.cache_clear()
    get_services.cache_clear()

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()
    get_services.cache_clear()
