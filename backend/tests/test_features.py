"""backend/tests/test_features.py -- locator, priority, suggestions, comparison, API flow."""
import json
import re

from app.core.config import get_settings
from app.schemas.report import ComponentResult, EvaluationReport
from app.schemas.verdict import Verdict
from app.services.extraction.latex_extractor import LatexExtractor
from app.services.extraction.normalizer import normalize
from app.services.framework.loader import load_framework
from app.services.llm.suggest import parse_suggestions
from app.services.report.compare import compare_reports
from app.services.report.locator import Locator, build_paragraphs
from app.services.report.priority import build_todo, priority_score
from app.services.sections.identifier import identify_sections


def _fw():
    s = get_settings()
    return load_framework(s.framework_path, s.schema_path)


def _verdict(cid, status, comp="abstract", **kw):
    return Verdict(id=cid, component=comp, name=cid, tier="B", status=status, **kw)


def _report(doc_id, statuses: dict[str, str], score=None):
    vs = [_verdict(cid, st) for cid, st in statuses.items()]
    comp = ComponentResult(key="abstract", name="Abstract", acronym="T5S", score=score, verdicts=vs)
    return EvaluationReport(document_id=doc_id, overall_score=score, components=[comp])


# ------------------------------------------------------------------ locator
def test_locator_finds_the_paragraph_with_the_evidence(tex_file):
    doc = normalize(LatexExtractor().extract(tex_file))
    smap = identify_sections(doc)
    loc = Locator(doc, smap)

    v = _verdict("W3", "pass", comp="introduction", evidence="We propose a label-free detector based on isolation trees.")
    i = loc.locate(v, "introduction")
    assert i is not None and "isolation trees" in doc.blocks[i].text
    assert i >= smap.spans["introduction"].start


def test_locator_falls_back_to_section_start_for_failures_only(tex_file):
    doc = normalize(LatexExtractor().extract(tex_file))
    smap = identify_sections(doc)
    loc = Locator(doc, smap)
    start = smap.spans["abstract"].start

    assert loc.locate(_verdict("T1", "fail", evidence="105 words (target 100-300)"), "abstract") == start
    assert loc.locate(_verdict("T1", "pass", evidence="105 words (target 100-300)"), "abstract") is None


def test_paragraphs_carry_their_sections(tex_file):
    doc = normalize(LatexExtractor().extract(tex_file))
    smap = identify_sections(doc)
    paras = build_paragraphs(doc, smap)
    assert len(paras) == len(doc.blocks)
    by_text = {p.text: p for p in paras}
    assert by_text["Introduction"].sections == ["introduction"]          # heading belongs to its section
    assert any(p.sections == ["introduction"] and p.kind == "text" for p in paras)


# ----------------------------------------------------------------- priority
def test_priority_prefers_cheap_high_impact_failures():
    assert priority_score("fail", "low", "high") > priority_score("fail", "high", "low")
    assert priority_score("fail", "medium", "medium") > priority_score("needs_review", "medium", "medium")


def test_todo_is_ranked_and_has_fallback_suggestions():
    fw = _fw()
    crit_by_id = {c.id: c for c in fw.all_criteria()}
    abstract = ComponentResult(
        key="abstract", name="Abstract", acronym="The-5-S",
        verdicts=[
            _verdict("T1", "fail"),                    # low effort, high impact
            _verdict("T3", "needs_review"),
            _verdict("T4", "pass"),
        ],
    )
    biblio = ComponentResult(
        key="bibliography", name="Bibliography", acronym="YEAR",
        verdicts=[_verdict("Y3", "fail", comp="bibliography")],   # high effort, low impact
    )
    todo = build_todo([abstract, biblio], crit_by_id)

    assert [t.id for t in todo] == ["T1", "T3", "Y3"]       # cheap + high impact first, manual checks next
    assert "T4" not in {t.id for t in todo}                       # passes are not to-dos
    assert all(t.suggestion for t in todo)

    custom = build_todo([abstract], crit_by_id, {"T1": ("Add more words.", "high")})
    assert custom[0].suggestion == "Add more words." and custom[0].effort == "high"


# --------------------------------------------------------------- suggestions
def test_parse_suggestions_is_lenient():
    text = json.dumps(
        [
            {"id": "T1", "suggestion": "Add two sentences.", "effort": "Low"},
            {"id": "T2", "suggestion": "", "effort": "low"},               # empty: skipped
            {"id": "ZZ", "suggestion": "unknown id", "effort": "low"},     # unknown: skipped
            {"id": "T3", "suggestion": "Rewrite it.", "effort": "weird"},  # bad effort: dropped, text kept
        ]
    )
    out = parse_suggestions("```json\n" + text + "\n```", {"T1", "T2", "T3"})
    assert out == {"T1": ("Add two sentences.", "low"), "T3": ("Rewrite it.", None)}
    assert parse_suggestions("not json", {"T1"}) == {}


# ---------------------------------------------------------------- comparison
def test_compare_reports_directions():
    before = _report("a" * 32, {"T1": "fail", "T2": "pass", "T3": "needs_review", "T4": "fail"}, score=33.3)
    after = _report("b" * 32, {"T1": "pass", "T2": "fail", "T3": "pass", "T4": "needs_review"}, score=66.7)
    cmp = compare_reports(before, after)

    dirs = {c.id: c.direction for c in cmp.changes}
    assert dirs == {"T1": "improved", "T2": "regressed", "T3": "improved", "T4": "changed"}
    assert cmp.improved == 2 and cmp.regressed == 1 and cmp.changed == 1 and cmp.unchanged == 0
    assert set(cmp.resolved_ids) == {"T1", "T3"}
    assert cmp.overall_delta == 33.4
    assert cmp.still_failing == 1


def test_compare_identical_reports_has_no_changes():
    r = _report("a" * 32, {"T1": "pass", "T2": "fail"}, score=50.0)
    cmp = compare_reports(r, r)
    assert cmp.changes == [] and cmp.unchanged == 2 and cmp.overall_delta == 0.0


# ------------------------------------------------------------------ API flow
def _upload_text(client, text, name="paper.tex"):
    r = client.post("/api/uploads", files={"file": (name, text.encode(), "application/octet-stream")})
    assert r.status_code == 200
    return r.json()["document_id"]


def test_report_has_reading_view_and_todo(client, tex_file):
    doc_id = _upload_text(client, tex_file.read_text(encoding="utf-8"))
    report = client.post("/api/evaluations", json={"document_id": doc_id}).json()

    assert report["paragraphs"] and {"i", "text", "kind", "sections"} <= set(report["paragraphs"][0])
    verdicts = {v["id"]: v for c in report["components"] for v in c["verdicts"]}

    t4 = verdicts["T4"]                                     # passed with a quote -> exact paragraph
    assert t4["block"] is not None and "label-free" in report["paragraphs"][t4["block"]]["text"]
    assert t4["section"] == "abstract"

    ids = {t["id"] for t in report["todo"]}
    assert "SP1" in ids and "T4" not in ids                 # judgment items are to-check, passes are not
    assert all(t["suggestion"] for t in report["todo"])


def test_compare_endpoint_before_and_after(client, tex_file):
    original = tex_file.read_text(encoding="utf-8")
    weak = re.sub(r"\\begin\{abstract\}.*?\\end\{abstract\}", r"\\begin{abstract}Too short.\\end{abstract}", original, flags=re.S)

    good_id = _upload_text(client, original)
    weak_id = _upload_text(client, weak)
    good = client.post("/api/evaluations", json={"document_id": good_id}).json()
    weak_r = client.post("/api/evaluations", json={"document_id": weak_id}).json()

    weak_todo = {t["id"] for t in weak_r["todo"]}
    assert "T1" in weak_todo                                # abstract too short -> to-do
    assert good["overall_score"] > weak_r["overall_score"]

    revised = client.post("/api/evaluations/compare", json={"before_id": weak_id, "after_id": good_id}).json()
    assert "T1" in revised["resolved_ids"]
    assert revised["overall_delta"] > 0 and revised["improved"] >= 1

    worse = client.post("/api/evaluations/compare", json={"before_id": good_id, "after_id": weak_id}).json()
    assert any(c["id"] == "T1" and c["direction"] == "regressed" for c in worse["changes"])

    missing = client.post("/api/evaluations/compare", json={"before_id": "0" * 32, "after_id": good_id})
    assert missing.status_code == 404
