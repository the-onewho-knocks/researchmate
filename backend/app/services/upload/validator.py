"""backend/app/services/upload/validator.py"""
import io
import re
import zipfile
from pathlib import Path

from app.core.errors import CorruptFileError, FileTooLargeError, UnsupportedFileError

ALLOWED = {".pdf": "pdf", ".docx": "docx", ".tex": "tex"}

MAX_UNCOMPRESSED = 200 * 1024 * 1024   # docx zip-bomb guard
MAX_RATIO = 200
MAX_ENTRIES = 5000
_TEX_MARKERS = re.compile(r"\\(documentclass|begin\{document\}|section|title|begin\{abstract\})")


def validate_upload(filename: str, data: bytes, max_bytes: int) -> str:
    """Validate by extension AND content. Returns the file type: pdf | docx | tex."""
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise UnsupportedFileError("Only .pdf, .docx and .tex files are supported.")
    if not data:
        raise CorruptFileError("The file is empty.")
    if len(data) > max_bytes:
        raise FileTooLargeError(f"File exceeds the {max_bytes // (1024 * 1024)} MB limit.")

    ftype = ALLOWED[ext]
    if ftype == "pdf":
        _check_pdf(data)
    elif ftype == "docx":
        _check_docx(data)
    else:
        _check_tex(data)
    return ftype


def _check_pdf(data: bytes) -> None:
    if b"%PDF-" not in data[:1024]:
        raise CorruptFileError("This does not look like a valid PDF file.")


def _check_docx(data: bytes) -> None:
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise CorruptFileError("This does not look like a valid .docx file.")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ENTRIES:
                raise CorruptFileError("The .docx archive has too many entries.")
            if "word/document.xml" not in {i.filename for i in infos}:
                raise CorruptFileError("The .docx file has no document body.")
            total = 0
            for i in infos:
                total += i.file_size
                if total > MAX_UNCOMPRESSED:
                    raise CorruptFileError("The .docx file expands to an unsafe size.")
                if (
                    i.file_size > 10 * 1024 * 1024
                    and i.compress_size
                    and i.file_size / i.compress_size > MAX_RATIO
                ):
                    raise CorruptFileError("The .docx file has a suspicious compression ratio.")
    except zipfile.BadZipFile as exc:
        raise CorruptFileError("The .docx file is corrupt.") from exc


def _check_tex(data: bytes) -> None:
    if b"\x00" in data[:4096]:
        raise CorruptFileError("This does not look like a LaTeX text file.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    if not _TEX_MARKERS.search(text):
        raise CorruptFileError("This does not look like a LaTeX source file.")