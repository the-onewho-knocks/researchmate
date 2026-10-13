"""backend/app/services/extraction/factory.py"""
from app.core.errors import UnsupportedFileError

from .base import Extractor
from .docx_extractor import DocxExtractor
from .latex_extractor import LatexExtractor
from .pdf_extractor import PdfExtractor


def get_extractor(file_type: str, max_pages: int = 60) -> Extractor:
    if file_type == "pdf":
        return PdfExtractor(max_pages=max_pages)
    if file_type == "docx":
        return DocxExtractor()
    if file_type == "tex":
        return LatexExtractor()
    raise UnsupportedFileError(f"Unsupported file type: {file_type}")