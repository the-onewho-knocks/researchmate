"""backend/app/services/extraction/base.py"""
from abc import ABC, abstractmethod
from pathlib import Path

from app.schemas.document import ParsedDocument


class Extractor(ABC):
    """Every extractor returns the same ParsedDocument, whatever the input format."""

    @abstractmethod
    def extract(self, path: Path) -> ParsedDocument: ...
