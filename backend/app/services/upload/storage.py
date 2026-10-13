"""backend/app/services/upload/storage.py"""
import json
import re
import time
import uuid
from pathlib import Path

from app.core.errors import DocumentNotFoundError

_ID = re.compile(r"^[0-9a-f]{32}$")

class UploadStorage:
    """Stores uploads under random names. The client's filename is never used as a path."""

    def __init__(self, base: Path, ttl_hours: int = 24):
        self.base = base
        self.ttl_seconds = ttl_hours * 3600
        self.base.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, file_type: str, original_name: str) -> str:
        doc_id = uuid.uuid4().hex
        (self.base / f"{doc_id}.{file_type}").write_bytes(data)
        meta = {
            "original_name": Path(original_name or "").name[:200],
            "file_type": file_type,
            "created": time.time(),
        }
        (self.base / f"{doc_id}.json").write_text(json.dumps(meta), encoding="utf-8")
        return doc_id

    def path_for(self, doc_id: str) -> tuple[Path, str]:
        if not _ID.match(doc_id or ""):
            raise DocumentNotFoundError("Unknown document id.")
        for ftype in ("pdf", "docx", "tex"):
            p = self.base / f"{doc_id}.{ftype}"
            if p.exists():
                return p, ftype
        raise DocumentNotFoundError("Document not found or expired.")

    def cleanup(self) -> int:
        """Delete files older than the TTL. Returns the number of deleted files."""
        now = time.time()
        removed = 0
        for p in self.base.iterdir():
            if p.is_file() and now - p.stat().st_mtime > self.ttl_seconds:
                p.unlink(missing_ok=True)
                removed += 1
        return removed