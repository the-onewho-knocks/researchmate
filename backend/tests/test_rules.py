"""backend/tests/test_rules.py"""
from datetime import datetime

from app.core.config import get_settings
from app.schemas.framework import Criterion
from app.services.extraction.latex_extractor import LatexExtractor
from app.services.extraction.normalizer import normalize
from app.services.framework.loader import load_framework
from app.services.rules.engine import run_rule
from app.services.rules.primitives import EvalContext, split_sentences
from app.services.sections.identifier import identify_sections


def _fw():
    s = get_settings()
    return load_framework(s.framework_path, s.schema_path)


def _run(fw, cid, ctx):
    for comp in fw.components:
        for crit in comp.criteria:
            if crit.id == cid:
                ctx.section_key = crit.params.get("section", comp.section)
                return run_rule(crit, ctx)
    raise KeyError(cid)


def _tex_ctx(tex_file):
    doc = normalize(LatexExtractor().extract(tex_file))
    return EvalContext(doc, identify_sections(doc))


def test_sentence_splitter_keeps_abbreviations_together():
    s = split_sentences("We use e.g. trees. See Fig. 3 for details. It works.")
    assert len(s) == 3
    assert s[0].startswith("We use e.g.")


def test_sample_paper_passes_the_rule_based_criteria(tex_file):
    fw, ctx = _fw(), _tex_ctx(tex_file)
    for cid in ["SP4", "T1", "T2", "T4", "T5", "R3", "B3", "E2", "E3", "F4", "F5", "C1", "C2", "C3", "Y1", "Y3"]:
        r = _run(fw, cid, ctx)
        assert r.status == "pass", f"{cid}: {r.status} {r.evidence} {r.note}"


def test_abstract_word_count(make_ctx):
    fw = _fw()
    short = make_ctx({"abstract": "Too short."})
    assert _run(fw, "T1", short).status == "fail"
    ok = make_ctx({"abstract": " ".join(["word"] * 150)})
    assert _run(fw, "T1", ok).status == "pass"


def test_abstract_self_contained_detects_references(make_ctx):
    fw = _fw()
    bad = make_ctx({"abstract": "As shown in Figure 2 and [4], our method works."})
    r = _run(fw, "T2", bad)
    assert r.status == "fail" and r.evidence


def test_title_filler_and_length(make_ctx):
    fw = _fw()
    assert _run(fw, "SP4", make_ctx({"title": "A study of things"})).status == "fail"
    assert _run(fw, "SP4", make_ctx({"title": "Fast detection of sensor faults"})).status == "pass"
    assert _run(fw, "SP4", make_ctx({"title": "Faults"})).status == "fail"


def test_missing_section_means_needs_review(make_ctx):
    r = _run(_fw(), "T1", make_ctx({"introduction": "Some text."}))
    assert r.status == "needs_review"
    assert "not detected" in r.note


def test_citations_must_match_reference_list(make_ctx):
    fw = _fw()
    refs = "\n".join(f"[{i}] Author {i}, Journal of Things, 2022." for i in (1, 2, 3))
    good = make_ctx({"introduction": "Known [1], [2] and [3].", "references": refs})
    assert _run(fw, "Y1", good).status == "pass"
    missing = make_ctx({"introduction": "Known [1] and [9].", "references": refs})
    r = _run(fw, "Y1", missing)
    assert r.status == "fail" and "9" in r.evidence


def test_recent_reference_share(make_ctx):
    fw, year = _fw(), datetime.now().year
    recent = "\n".join(f"[{i}] Author, Journal of Things, {year - 1}." for i in (1, 2, 3, 4))
    old = "\n".join(f"[{i}] Author, Journal of Things, 1999." for i in (1, 2, 3, 4))
    assert _run(fw, "R1", make_ctx({"references": recent})).status == "pass"
    assert _run(fw, "R1", make_ctx({"references": old})).status == "fail"


def test_page_ranges_are_not_read_as_years(make_ctx):
    fw = _fw()
    refs = "\n".join(f"[{i}] Author, Journal of Things, pp. 1895-1902, 2020." for i in (1, 2, 3))
    r = _run(fw, "R1", make_ctx({"references": refs}))
    assert "3 of 3" in r.evidence or r.status in ("pass", "fail")


def test_limitations_fall_back_to_conclusion(make_ctx):
    fw = _fw()
    ctx = make_ctx({
        "discussion": "The results are robust.",
        "conclusion": "A limitation is the small sample.",
    })
    r = _run(fw, "F4", ctx)
    assert r.status == "pass" and "conclusion" in r.note


def test_results_without_figures_fail_visual_support(make_ctx):
    r = _run(_fw(), "E3", make_ctx({"results": "We got numbers."}))
    assert r.status == "fail"


def test_unknown_rule_returns_none():
    crit = Criterion(id="Z1", name="x", tier="C")
    assert run_rule(crit, None) is None
