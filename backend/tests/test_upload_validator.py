"""backend/tests/test_upload_validator.py"""
import io
import zipfile

import pytest

from app.core.errors import CorruptFileError, FileTooLargeError, UnsupportedFileError
from app.services.upload.validator import validate_upload

MB = 1024 * 1024


def test_accepts_all_three_formats(pdf_file, docx_file, tex_file):
    assert validate_upload("p.pdf", pdf_file.read_bytes(), 10 * MB) == "pdf"
    assert validate_upload("p.docx", docx_file.read_bytes(), 10 * MB) == "docx"
    assert validate_upload("p.tex", tex_file.read_bytes(), 10 * MB) == "tex"


def test_rejects_unsupported_extension():
    with pytest.raises(UnsupportedFileError):
        validate_upload("malware.exe", b"data", MB)


def test_rejects_empty_file():
    with pytest.raises(CorruptFileError):
        validate_upload("a.pdf", b"", MB)


def test_rejects_content_that_does_not_match_extension():
    with pytest.raises(CorruptFileError):
        validate_upload("a.pdf", b"hello world", MB)
    with pytest.raises(CorruptFileError):
        validate_upload("a.docx", b"hello world", MB)
    with pytest.raises(CorruptFileError):
        validate_upload("a.tex", b"just some plain text without any latex", MB)


def test_rejects_binary_tex():
    with pytest.raises(CorruptFileError):
        validate_upload("a.tex", b"\\documentclass{article}\x00\x01\x02", MB)


def test_rejects_docx_without_document_body():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("other.txt", "x")
    with pytest.raises(CorruptFileError):
        validate_upload("a.docx", buf.getvalue(), MB)


def test_rejects_too_large(tex_file):
    with pytest.raises(FileTooLargeError):
        validate_upload("a.tex", tex_file.read_bytes(), 10)
