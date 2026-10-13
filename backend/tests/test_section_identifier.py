"""backend/tests/test_section_identifier.py"""
from app.schemas.document import Block, ParsedDocument
from app.services.extraction.docx_extractor import DocxExtractor
from app.services.extraction.latex_extractor import LatexExtractor
from app.services.extraction.normalizer import normalize
from app.services.extraction.pdf_extractor import PdfExtractor
from app.services.sections.heading_rules import classify_heading
from app.services.sections.identifier import identify_sections

CORE = {"introduction", "methods", "results", "conclusion", "references"}


def test_heading_synonyms_and_numbering():
    assert classify_heading("I. INTRODUCTION") == ("introduction",)
    assert classify_heading("III. METHODOLOGY") == ("methods",)
    assert classify_heading("2.1 Related Work") == ("related_work",)
    assert classify_heading("Literature Review") == ("related_work",)
    assert classify_heading("REFERENCES") == ("references",)
    assert classify_heading("Results and Discussion") == ("results", "discussion")


def test_smallcaps_headings_are_repaired():
    assert classify_heading("II. R ELATED W ORK") == ("related_work",)


def test_unknown_headings_are_not_sections():
    assert classify_heading("A. Guidelines and the STRaWBERRY framework") == ()
    assert classify_heading("B. Evaluation of STRaWBERRY-LLM") == ()


def test_latex_sections(tex_file):
    smap = identify_sections(normalize(LatexExtractor().extract(tex_file)))
    assert (CORE | {"abstract", "related_work", "discussion", "title"}) <= set(smap.spans)
    assert not smap.low_confidence


def test_docx_sections(docx_file):
    smap = identify_sections(normalize(DocxExtractor().extract(docx_file)))
    assert (CORE | {"abstract", "title"}) <= set(smap.spans)


def test_pdf_sections_from_layout(pdf_file):
    doc = normalize(PdfExtractor().extract(pdf_file))
    smap = identify_sections(doc)
    assert CORE <= set(smap.spans)
    assert "Label-Free" in smap.text("title", doc)


def test_results_and_discussion_share_one_span():
    blocks = []
    for head, body in [
        ("Introduction", "Some introduction text."),
        ("Methods", "Some methods text."),
        ("Results and Discussion", "Results and their discussion."),
        ("Conclusion", "Some conclusion text."),
        ("References", "[1] A. Author, Journal, 2020."),
    ]:
        blocks.append(Block(text=head, kind="heading", level=1))
        blocks.append(Block(text=body))
    smap = identify_sections(ParsedDocument(file_type="tex", blocks=blocks))
    assert smap.spans["results"].start == smap.spans["discussion"].start
    assert smap.spans["results"].end == smap.spans["discussion"].end


def test_document_without_headings_is_flagged_low_confidence():
    blocks = [Block(text="Just a paragraph of text that has no headings at all. " * 3) for _ in range(3)]
    smap = identify_sections(ParsedDocument(file_type="docx", blocks=blocks))
    assert smap.low_confidence
    assert smap.notes
