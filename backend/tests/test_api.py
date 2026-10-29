"""backend/tests/test_api.py"""
import pytest

CORE = {"introduction", "methods", "results", "conclusion", "references"}


def _upload(client, path, name=None):
    with open(path, "rb") as f:
        return client.post("/api/uploads", files={"file": (name or path.name, f, "application/octet-stream")})


def _verdicts(report):
    return {v["id"]: v for c in report["components"] for v in c["verdicts"]}


def test_health_and_framework(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["llm_available"] is False
    assert h["gemini_available"] is False and h["local_available"] is False
    fw = client.get("/api/framework").json()
    assert len(fw["components"]) == 9
    assert "params" not in fw["components"][0]["criteria"][0]      # rule parameters stay server-side


def test_full_flow_for_tex_without_llm(client, tex_file):
    up = _upload(client, tex_file)
    assert up.status_code == 200
    doc_id = up.json()["document_id"]

    r = client.post("/api/evaluations", json={"document_id": doc_id})
    assert r.status_code == 200
    report = r.json()
    v = _verdicts(report)

    assert len(report["components"]) == 9
    assert CORE <= set(report["sections_detected"])
    assert v["SP4"]["status"] == "pass" and v["SP4"]["source"] == "rule"
    assert v["T1"]["status"] == "pass"
    assert v["T4"]["status"] == "pass"
    assert v["E3"]["status"] == "pass"
    assert v["Y1"]["status"] == "pass"
    assert v["SP1"]["status"] == "needs_review"          # tier C needs the LLM, which is not configured
    assert report["usage"]["calls"] == 0
    assert report["overall_score"] is not None
    assert any("AI judge" in l for l in report["limitations"])

    again = client.post("/api/evaluations", json={"document_id": doc_id}).json()
    assert again["cached"] is True

    stored = client.get(f"/api/evaluations/{doc_id}")
    assert stored.status_code == 200


@pytest.mark.parametrize("fixture_name", ["pdf_file", "docx_file"])
def test_pdf_and_docx_are_evaluated(client, request, fixture_name):
    path = request.getfixturevalue(fixture_name)
    doc_id = _upload(client, path).json()["document_id"]
    r = client.post("/api/evaluations", json={"document_id": doc_id})
    assert r.status_code == 200
    report = r.json()
    assert len(report["components"]) == 9
    assert CORE <= set(report["sections_detected"])
    assert _verdicts(report)["T1"]["status"] == "pass"


def test_upload_errors(client, tmp_path):
    exe = tmp_path / "evil.exe"
    exe.write_bytes(b"x")
    assert _upload(client, exe).status_code == 415

    fake = tmp_path / "fake.pdf"
    fake.write_bytes(b"this is not a pdf")
    assert _upload(client, fake).status_code == 422


def test_unknown_document_ids(client):
    assert client.post("/api/evaluations", json={"document_id": "0" * 32}).status_code == 404
    assert client.post("/api/evaluations", json={"document_id": "../etc/passwd"}).status_code == 404
    assert client.get("/api/evaluations/" + "0" * 32).status_code == 404
