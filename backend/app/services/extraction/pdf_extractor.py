"""backend/app/services/extraction/pdf_extractor.py"""
from pathlib import Path

import fitz  # PyMuPDF

from app.core.errors import CorruptFileError, ExtractionError, FileTooLargeError
from app.schemas.document import Block, ParsedDocument

from .base import Extractor
from .normalizer import join_lines

class PdfExtractor(Extractor):
    def __init__(self, max_pages: int = 60):
        self.max_pages = max_pages

    def extract(self, path: Path) -> ParsedDocument:
        try:
            pdf = fitz.open(str(path))
        except Exception as exc:
            raise CorruptFileError(f"Could not open the PDF: {exc}") from exc

        try:
            if pdf.needs_pass:
                raise CorruptFileError("The PDF is password protected.")
            page_count = pdf.page_count
            if page_count > self.max_pages:
                raise FileTooLargeError(f"The PDF has {page_count} pages (limit {self.max_pages}).")

            blocks: list[Block] = []
            n_images = 0
            for pno, page in enumerate(pdf, start=1):
                width, height = page.rect.width, page.rect.height
                items = []
                for raw in page.get_text("dict")["blocks"]:
                    if raw.get("type") != 0:      # 0 = text block
                        continue
                    blk = self._to_block(raw, pno, height)
                    if blk:
                        x0, y0, x1, y1 = raw["bbox"]
                        items.append((x0, y0, x1, y1, blk))
                blocks.extend(_order(items, width))
                n_images += len(page.get_images(full=False))
        finally:
            pdf.close()

        if not blocks:
            raise ExtractionError("No extractable text found. Scanned PDFs need OCR first.")
        return ParsedDocument(
            file_type="pdf", blocks=blocks, num_pages=page_count, meta={"n_images": n_images}
        )

    @staticmethod
    def _to_block(raw: dict, page_no: int, page_height: float) -> Block | None:
        lines: list[str] = []
        weighted_size = 0.0
        bold_chars = 0
        total = 0
        for ln in raw.get("lines", []):
            if ln.get("dir", (1.0, 0.0))[0] < 0.9:   # skip rotated text (side watermarks)
                continue
            lines.append("".join(s["text"] for s in ln["spans"]))
            for s in ln["spans"]:
                n = len(s["text"].strip())
                if n == 0:
                    continue
                total += n
                weighted_size += s["size"] * n
                if (s["flags"] & 16) or "bold" in s["font"].lower():
                    bold_chars += n
        text = join_lines(lines)
        if not text or total == 0:
            return None
        return Block(
            text=text,
            page=page_no,
            size=round(weighted_size / total, 2),
            bold=bold_chars / total > 0.6,
            ypos=raw["bbox"][1] / page_height if page_height else None,
        )


def _order(items: list, page_width: float) -> list[Block]:
    """Reading order for one- and two-column pages.

    Full-width blocks split the page into bands; inside a band the left column
    is read before the right column.
    """
    items.sort(key=lambda t: (t[1], t[0]))
    out: list = []
    band: list = []

    def flush() -> None:
        left = sorted((t for t in band if (t[0] + t[2]) / 2 < page_width / 2), key=lambda t: t[1])
        right = sorted((t for t in band if (t[0] + t[2]) / 2 >= page_width / 2), key=lambda t: t[1])
        out.extend(left + right)
        band.clear()

    for t in items:
        if t[2] - t[0] > 0.6 * page_width:
            flush()
            out.append(t)
        else:
            band.append(t)
    flush()
    return [t[4] for t in out]