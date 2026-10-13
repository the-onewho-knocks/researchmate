"""backend/tests/test_extractors.py"""
import re

from app.schemas.document import Block, ParsedDocument
from app.services.extraction.docx_extractor import DocxExtractor
from app.services.extraction.latex_extractor import LatexExtractor
from app.services.extraction.normalizer import normalize
from app.services.extraction.pdf_extractor import PdfExtractor


def test_latex_structure(tex_file):
    doc = LatexExtractor().extract(tex_file)
    assert doc.file_type == "tex"
    assert doc.num_pages is None

    heads = [b.text for b in doc.blocks if b.kind == "heading"]
    assert heads[:3] == ["Abstract", "Introduction", "Related Work"]
    assert "References" in heads

    title = [b for b in doc.blocks if b.kind == "title"]
    assert title and "Anomaly" in title[0].text

    assert doc.meta["n_figures"] == 1
    assert any(b.kind == "caption" and b.text.startswith("Figure 1") for b in doc.blocks)


def test_latex_citations_and_bibliography(tex_file):
    doc = LatexExtractor().extract(tex_file)
    assert any("[1, 2]" in b.text for b in doc.blocks)                    # \cite{a,b}
    refs = [b.text for b in doc.blocks if re.match(r"\[\d\] ", b.text)]
    assert len(refs) == 3


def test_docx_uses_heading_styles(docx_file):
    doc = DocxExtractor().extract(docx_file)
    assert doc.file_type == "docx"
    assert any(b.kind == "title" for b in doc.blocks)
    assert sum(1 for b in doc.blocks if b.kind == "heading") == 8        # 7 sections + References


def test_pdf_text_and_pages(pdf_file):
    doc = PdfExtractor().extract(pdf_file)
    assert doc.file_type == "pdf"
    assert doc.num_pages >= 1
    assert "Label-Free" in doc.full_text()
    assert len(doc.blocks) > 5


def test_normalizer_splits_run_in_abstract_and_keywords():
    doc = ParsedDocument(
        file_type="pdf",
        blocks=[Block(text="Abstract—Writing papers is hard."), Block(text="Index Terms—writing, llm")],
    )
    normalize(doc)
    assert [b.text for b in doc.blocks] == ["Abstract", "Writing papers is hard.", "Keywords", "writing, llm"]
    assert doc.blocks[0].kind == "heading" and doc.blocks[2].kind == "heading"


def test_normalizer_removes_repeating_footers():
    blocks = [Block(text="Real body text of the paper.", page=1, ypos=0.5)]
    for p in range(1, 5):
        blocks.append(Block(text=f"Downloaded on July {p}, licensed use limited", page=p, ypos=0.96))
    doc = ParsedDocument(file_type="pdf", blocks=blocks, num_pages=4)
    normalize(doc)
    assert [b.text for b in doc.blocks] == ["Real body text of the paper."]
